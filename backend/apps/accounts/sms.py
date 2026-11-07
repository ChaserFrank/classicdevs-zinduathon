"""Minimal SMS sender for phone verification codes.

Phase 4 replaces the body of `send_sms` with the Thrivewave adapter and delivery logging. The
message body is never logged: verification codes must not appear in plain text anywhere.
"""

import logging

from django.conf import settings

from .phone import mask

logger = logging.getLogger(__name__)


def send_sms(to_e164: str, message: str) -> str:
    """Send (or dry-run) an SMS. Returns the delivery status: "dry_run" or "sent"."""
    if settings.SMS_DRY_RUN or not (settings.THRIVEWAVE_BASE_URL and settings.THRIVEWAVE_API_KEY):
        logger.info("SMS dry run", extra={"to": mask(to_e164), "length": len(message)})
        return "dry_run"
    # Real sending is wired up in Phase 4 (notifications.providers.thrivewave).
    logger.warning("SMS sending not wired yet; treated as dry run", extra={"to": mask(to_e164)})
    return "dry_run"
