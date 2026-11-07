"""Account workflows. Views stay thin; everything that changes data lives here and is audited."""

import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core import audit

from . import emails, sms, tokens
from .errors import (
    CodeAttemptsExceeded,
    CodeInvalid,
    GithubAlreadyLinked,
    GithubNotLinked,
    PasswordRequired,
    PhoneMissing,
    RecruiterSignupNeedsEmail,
    TermsRequired,
)
from .github_oauth import GithubIdentity, OAuthState, require_email
from .models import (
    ConsentRecord,
    ConsentType,
    GithubAccount,
    JobSeekerProfile,
    Role,
    User,
    VerificationCode,
    VerificationPurpose,
)

logger = logging.getLogger(__name__)


# --- Consent ---


def record_consents(user: User, consents: dict, request=None) -> None:
    """`consents` uses API names: terms (covers terms + privacy), emailFeedback, smsFeedback."""
    ip = audit.client_ip(request)
    rows = []
    if "terms" in consents:
        for kind in (ConsentType.TERMS, ConsentType.PRIVACY):
            rows.append((kind, bool(consents["terms"])))
    for api_name, kind in (
        ("email_feedback", ConsentType.EMAIL_FEEDBACK),
        ("sms_feedback", ConsentType.SMS_FEEDBACK),
    ):
        if api_name in consents:
            rows.append((kind, bool(consents[api_name])))
    ConsentRecord.objects.bulk_create(
        [
            ConsentRecord(
                user=user,
                consent_type=kind,
                granted=granted,
                policy_version=settings.POLICY_VERSION,
                ip_address=ip,
            )
            for kind, granted in rows
        ]
    )


def has_consent(user: User, consent_type: str) -> bool:
    latest = user.consents.filter(consent_type=consent_type).order_by("-created_at", "-id").first()
    return bool(latest and latest.granted)


# --- Registration ---


@transaction.atomic
def register(*, data: dict, request=None) -> User:
    from apps.companies.models import RecruiterProfile
    from apps.companies.services import get_or_create_company

    user = User.objects.create_user(
        data["email"],
        data["password"],
        role=data["role"],
        full_name=data.get("full_name", ""),
        phone=data.get("phone") or None,
    )
    if user.role == Role.JOB_SEEKER:
        JobSeekerProfile.objects.create(user=user)
    else:
        RecruiterProfile.objects.create(
            user=user,
            company=get_or_create_company(data["company_name"]),
            job_title=data.get("job_title", ""),
        )
    record_consents(user, data["consents"], request)
    audit.record(
        "auth.register", actor=user, target=user, request=request, metadata={"role": user.role}
    )
    transaction.on_commit(lambda: emails.send_verification_email(user))
    return user


def verify_email(user: User, request=None) -> None:
    if user.email_verified_at is None:
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at", "updated_at"])
        audit.record("auth.email_verified", actor=user, target=user, request=request)


# --- Passwords ---


def change_password(user: User, new_password: str, request=None, *, action="auth.password_changed"):
    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])
    tokens.blacklist_all(user)  # sign out other devices
    audit.record(action, actor=user, target=user, request=request)


# --- Phone verification ---


def _hash_code(user: User, code: str) -> str:
    key = settings.SECRET_KEY.encode()
    return hmac.new(key, f"{user.public_id}:{code}".encode(), hashlib.sha256).hexdigest()


def set_phone(user: User, phone: str | None) -> None:
    """Changing the number un-verifies it."""
    if phone != user.phone:
        user.phone = phone
        user.phone_verified_at = None
        user.save(update_fields=["phone", "phone_verified_at", "updated_at"])


@transaction.atomic
def send_phone_code(user: User) -> tuple[VerificationCode, str]:
    if not user.phone:
        raise PhoneMissing()
    now = timezone.now()
    # Only the newest code works.
    VerificationCode.objects.filter(
        user=user, purpose=VerificationPurpose.VERIFY_PHONE, used_at__isnull=True
    ).update(used_at=now)
    code = f"{secrets.randbelow(1_000_000):06d}"
    record = VerificationCode.objects.create(
        user=user,
        purpose=VerificationPurpose.VERIFY_PHONE,
        code_hash=_hash_code(user, code),
        expires_at=now + timedelta(minutes=settings.PHONE_CODE_TTL_MINUTES),
    )
    sms.send_sms(user.phone, f"Your SkillProof code is {code}. It expires in 10 minutes.")
    return record, code


def verify_phone_code(user: User, code: str, request=None) -> None:
    """Check a code. The attempt counter is committed before raising, so wrong guesses count even
    though the request fails (raising inside the atomic block would roll the counter back)."""
    with transaction.atomic():
        record = (
            VerificationCode.objects.select_for_update()
            .filter(user=user, purpose=VerificationPurpose.VERIFY_PHONE, used_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if record is None or record.expires_at <= timezone.now():
            outcome = "invalid"
        elif record.attempts >= VerificationCode.MAX_ATTEMPTS:
            outcome = "exceeded"
        elif not hmac.compare_digest(record.code_hash, _hash_code(user, code.strip())):
            record.attempts += 1
            record.save(update_fields=["attempts", "updated_at"])
            outcome = "invalid"
        else:
            now = timezone.now()
            record.used_at = now
            record.save(update_fields=["used_at", "updated_at"])
            user.phone_verified_at = now
            user.save(update_fields=["phone_verified_at", "updated_at"])
            audit.record("auth.phone_verified", actor=user, target=user, request=request)
            outcome = "ok"
    if outcome == "exceeded":
        raise CodeAttemptsExceeded()
    if outcome == "invalid":
        raise CodeInvalid()


# --- GitHub ---


def _store_identity(account: GithubAccount, identity: GithubIdentity) -> GithubAccount:
    account.login = identity.login
    account.avatar_url = identity.avatar_url
    account.token_scopes = identity.scopes
    account.set_token(identity.access_token)
    account.last_synced_at = timezone.now()
    account.save()
    return account


def _link(user: User, identity: GithubIdentity) -> GithubAccount:
    existing = getattr(user, "github_account", None)
    if existing is not None and existing.github_id != identity.github_id:
        raise GithubAlreadyLinked("Unlink your current GitHub account first.")
    # A login can move between GitHub ids (account renamed/deleted); free it from a stale row.
    GithubAccount.objects.filter(login=identity.login.lower()).exclude(
        github_id=identity.github_id
    ).update(login=f"~{identity.github_id}")
    account = existing or GithubAccount(user=user, github_id=identity.github_id)
    try:
        return _store_identity(account, identity)
    except IntegrityError as exc:  # pragma: no cover - race with another link of the same id
        raise GithubAlreadyLinked() from exc


@transaction.atomic
def github_sign_in(
    identity: GithubIdentity, state: OAuthState, *, current_user=None, request=None
) -> tuple[User, bool]:
    """Resolve a GitHub identity to a user. Returns (user, created).

    Order (from the brief): known github_id → sign in; signed-in linking → link; verified email
    match → link + sign in; otherwise create a job seeker.
    """
    signed_in = current_user if current_user and current_user.is_authenticated else None
    account = (
        GithubAccount.objects.select_related("user").filter(github_id=identity.github_id).first()
    )

    if account is not None:
        if signed_in and account.user_id != signed_in.pk:
            raise GithubAlreadyLinked()
        _store_identity(account, identity)
        user, created, how = account.user, False, "github_id"
    elif signed_in:
        _link(signed_in, identity)
        user, created, how = signed_in, False, "linked_signed_in"
        audit.record("auth.github_linked", actor=user, target=user, request=request)
    else:
        email = require_email(identity)
        user = User.objects.filter(email__iexact=email).first()
        if user is not None:
            if not user.is_email_verified:
                # Someone may have pre-registered this address with their own password. GitHub
                # proves the real owner, so take the account back: drop that password.
                user.set_unusable_password()
                tokens.blacklist_all(user)
                user.email_verified_at = timezone.now()
                user.save(update_fields=["password", "email_verified_at", "updated_at"])
            _link(user, identity)
            created, how = False, "linked_by_email"
            audit.record("auth.github_linked", actor=user, target=user, request=request)
        else:
            if state.role != Role.JOB_SEEKER:
                raise RecruiterSignupNeedsEmail()
            if not state.consents.get("terms"):
                raise TermsRequired()
            user = User.objects.create_user(
                email,
                None,
                role=Role.JOB_SEEKER,
                full_name=identity.name or "",
                email_verified_at=timezone.now(),  # GitHub verified it
            )
            JobSeekerProfile.objects.create(user=user)
            _link(user, identity)
            record_consents(user, state.consents, request)
            created, how = True, "created"
            audit.record(
                "auth.register",
                actor=user,
                target=user,
                request=request,
                metadata={"via": "github"},
            )

    if not user.is_active:
        from .errors import InvalidCredentials

        raise InvalidCredentials("This account is suspended.")
    audit.record(
        "auth.sign_in",
        actor=user,
        target=user,
        request=request,
        metadata={"via": "github", "how": how},
    )
    return user, created


@transaction.atomic
def unlink_github(user: User, request=None) -> None:
    account = getattr(user, "github_account", None)
    if account is None:
        raise GithubNotLinked()
    if not user.has_usable_password():
        raise PasswordRequired()
    account.delete()
    audit.record("auth.github_unlinked", actor=user, target=user, request=request)
