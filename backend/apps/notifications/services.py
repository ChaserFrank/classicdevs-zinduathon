"""One entry point for every notification: `notify(user, kind, context)`.

1. Creates the in-app Notification.
2. For email and SMS, checks the user's preference, consent and (SMS) verified phone, and creates
   a Delivery row: `queued`, or `skipped` with the reason.
3. Queues one Celery task per queued delivery after the transaction commits.
"""

import logging
from contextlib import contextmanager
from contextvars import ContextVar

from django.conf import settings
from django.db import transaction
from django.template.loader import render_to_string

from apps.accounts.models import ConsentType, Role

from .models import Channel, Delivery, DeliveryStatus, Kind, Notification, NotificationPreference

logger = logging.getLogger(__name__)

# Which channels exist for each kind (brief 9.2). In-app is always available.
CHANNELS: dict[str, tuple[str, ...]] = {
    Kind.ANALYSIS_COMPLETED: ("in_app", "email", "sms"),
    Kind.ANALYSIS_FAILED: ("in_app", "email"),
    Kind.RECRUITER_FEEDBACK: ("in_app", "email", "sms"),
    Kind.SHORTLISTED: ("in_app", "email", "sms"),
    Kind.RECRUITER_APPROVED: ("in_app", "email", "sms"),
    Kind.RECRUITER_REJECTED: ("in_app", "email", "sms"),
    Kind.PROFILE_VIEWED_DIGEST: ("in_app", "email"),
}
KINDS_BY_ROLE: dict[str, tuple[str, ...]] = {
    Role.JOB_SEEKER: (
        Kind.ANALYSIS_COMPLETED,
        Kind.ANALYSIS_FAILED,
        Kind.RECRUITER_FEEDBACK,
        Kind.SHORTLISTED,
        Kind.PROFILE_VIEWED_DIGEST,
    ),
    Role.RECRUITER: (Kind.RECRUITER_APPROVED, Kind.RECRUITER_REJECTED),
    Role.ADMIN: (),
}
# Account/status messages a user needs regardless of marketing-style consent.
TRANSACTIONAL_EMAIL = {Kind.ANALYSIS_FAILED, Kind.RECRUITER_APPROVED, Kind.RECRUITER_REJECTED}
SMS_FOOTER = "Reply STOP to opt out"


def _consents(user) -> dict[str, bool]:
    latest: dict[str, bool] = {}
    for consent_type, granted in user.consents.order_by("created_at", "id").values_list(
        "consent_type", "granted"
    ):
        latest[consent_type] = granted
    return latest


def default_enabled(kind: str, channel: str, consents: dict[str, bool]) -> bool:
    if channel not in CHANNELS[kind]:
        return False
    if channel == Channel.IN_APP:
        return True
    if channel == Channel.EMAIL:
        return kind in TRANSACTIONAL_EMAIL or consents.get(ConsentType.EMAIL_FEEDBACK, False)
    return consents.get(ConsentType.SMS_FEEDBACK, False)


def ensure_defaults(user) -> None:
    """Create preference rows from the user's consent choices (sign-up, or first read)."""
    consents = _consents(user)
    existing = set(user.notification_preferences.values_list("kind", "channel"))
    NotificationPreference.objects.bulk_create(
        [
            NotificationPreference(
                user=user,
                kind=kind,
                channel=channel,
                enabled=default_enabled(kind, channel, consents),
            )
            for kind in KINDS_BY_ROLE.get(user.role, ())
            for channel in CHANNELS[kind]
            if (kind, channel) not in existing
        ]
    )


def matrix(user) -> dict[str, dict[str, bool]]:
    ensure_defaults(user)
    rows = {(p.kind, p.channel): p.enabled for p in user.notification_preferences.all()}
    return {
        kind: {channel: rows.get((kind, channel), False) for channel in CHANNELS[kind]}
        for kind in KINDS_BY_ROLE.get(user.role, ())
    }


def _preference(user, kind: str, channel: str) -> bool:
    row = user.notification_preferences.filter(kind=kind, channel=channel).first()
    if row is not None:
        return row.enabled
    return default_enabled(kind, channel, _consents(user))


_muted: ContextVar[bool] = ContextVar("notifications_muted", default=False)


@contextmanager
def outbound_muted():
    """In-app notifications only; email/SMS deliveries are recorded as skipped. Used by
    seed_demo so demo data never emails or texts made-up addresses."""
    token = _muted.set(True)
    try:
        yield
    finally:
        _muted.reset(token)


def _skip_reason(user, kind: str, channel: str) -> str | None:
    if _muted.get():
        return "outbound muted (demo data)"
    if channel not in CHANNELS[kind]:
        return "channel not used for this kind"
    if not _preference(user, kind, channel):
        return "turned off in preferences"
    consents = _consents(user)
    if channel == Channel.EMAIL:
        if kind not in TRANSACTIONAL_EMAIL and not consents.get(ConsentType.EMAIL_FEEDBACK):
            return "no email consent"
        if not user.email:
            return "no email address"
    if channel == Channel.SMS:
        if not consents.get(ConsentType.SMS_FEEDBACK):
            return "no SMS consent"
        if not user.phone or not user.is_phone_verified:
            return "phone not verified"
    if not user.is_active:
        return "account inactive"
    return None


def _render(kind: str, name: str, context: dict) -> str:
    return render_to_string(f"notifications/{kind}/{name}", context).strip()


def render_sms(kind: str, context: dict) -> str:
    from .sms_text import compose

    return compose(
        _render(kind, "sms.txt", context), link=context.get("link", ""), footer=SMS_FOOTER
    )


def link_for(path: str) -> str:
    return f"{settings.FRONTEND_URL}{path}"


@transaction.atomic
def notify(
    user, kind: str, context: dict, *, actor=None, analysis=None, link_path: str = "", **extra
):
    """Create the in-app notification and email/SMS deliveries. Returns the Notification."""
    context = {
        "user": user,
        "actor": actor,
        "link": link_for(link_path) if link_path else "",
        **context,
    }
    notification = Notification.objects.create(
        user=user,
        kind=kind,
        title=_render(kind, "subject.txt", context)[:200],
        body=_render(kind, "inapp.txt", context),
        link_path=link_path,
        analysis=analysis,
        **extra,
    )
    for channel in (Channel.EMAIL, Channel.SMS):
        if channel not in CHANNELS[kind]:
            continue
        reason = _skip_reason(user, kind, channel)
        delivery = Delivery.objects.create(
            notification=notification,
            channel=channel,
            recipient=(user.email if channel == Channel.EMAIL else user.phone or "") or "",
            provider="smtp" if channel == Channel.EMAIL else "thrivewave",
            status=DeliveryStatus.SKIPPED if reason else DeliveryStatus.QUEUED,
            last_error=reason or "",
            # Rendered now so retries send exactly the same text.
            provider_response={"render": _render_payload(kind, channel, context)}
            if not reason
            else {},
        )
        if not reason:
            from .tasks import deliver

            transaction.on_commit(lambda pk=delivery.pk: deliver.delay(pk))
    return notification


def _render_payload(kind: str, channel: str, context: dict) -> dict:
    if channel == Channel.SMS:
        return {"sms": render_sms(kind, context)}
    return {
        "subject": _render(kind, "subject.txt", context),
        "text": render_to_string(f"notifications/{kind}/body.txt", context),
        "html": render_to_string(f"notifications/{kind}/body.html", context),
    }
