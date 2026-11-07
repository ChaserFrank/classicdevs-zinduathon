"""JWT issuing and the signed tokens used in email links.

JWT claims (role, approvalStatus, githubLogin) let the frontend route without an extra request.
They are rebuilt from the database on every refresh, so a role or approval change shows up within
one access-token lifetime (15 minutes) without the user signing out.
"""

from django.conf import settings
from django.contrib.auth.models import update_last_login
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User

EMAIL_SALT = "skillproof.verify-email"
RESET_SALT = "skillproof.password-reset"


def _claims(user: User) -> dict:
    claims = {"role": user.role}
    profile = getattr(user, "recruiter_profile", None)
    if profile is not None:
        claims["approvalStatus"] = profile.approval_status
    github = getattr(user, "github_account", None)
    if github is not None:
        claims["githubLogin"] = github.login
    return claims


def issue_tokens(user: User, *, update_login: bool = True) -> dict[str, str]:
    refresh = RefreshToken.for_user(user)
    for key, value in _claims(user).items():
        refresh[key] = value  # copied into the access token too
    if update_login:
        update_last_login(None, user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def blacklist_all(user: User) -> None:
    """Sign the user out everywhere (password change/reset, suspension, deletion)."""
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)


# --- Email verification links -------------------------------------------------------------------


def make_email_token(user: User) -> str:
    # Bound to the email: changing the address invalidates old links.
    return signing.dumps({"u": str(user.public_id), "e": user.email}, salt=EMAIL_SALT)


def read_email_token(token: str) -> User | None:
    try:
        data = signing.loads(token, salt=EMAIL_SALT, max_age=settings.EMAIL_VERIFICATION_MAX_AGE)
    except signing.BadSignature:
        return None
    return User.objects.filter(public_id=data.get("u"), email=data.get("e")).first()


# --- Password reset links -----------------------------------------------------------------------


def make_reset_token(user: User) -> str:
    """Django's generator makes the token single-use: it hashes the password and last login, so it
    stops working as soon as the password changes. We sign it together with the user id so the
    link carries one opaque string."""
    return signing.dumps(
        {"u": str(user.public_id), "t": default_token_generator.make_token(user)}, salt=RESET_SALT
    )


def read_reset_token(token: str) -> User | None:
    try:
        data = signing.loads(token, salt=RESET_SALT, max_age=settings.PASSWORD_RESET_TIMEOUT)
    except signing.BadSignature:
        return None
    user = User.objects.filter(public_id=data.get("u"), is_active=True).first()
    if user and default_token_generator.check_token(user, data.get("t", "")):
        return user
    return None
