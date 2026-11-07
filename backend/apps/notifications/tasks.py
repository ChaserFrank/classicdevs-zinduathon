"""Delivery tasks. Up to 3 attempts with exponential backoff (30 s, 60 s) on network errors and
5xx responses; 4xx-style rejections fail immediately (retrying won't fix a bad number)."""

import logging
import smtplib

from celery import shared_task
from django.utils import timezone

from .models import Delivery, DeliveryStatus
from .providers import email as email_provider
from .providers import thrivewave

logger = logging.getLogger(__name__)
BACKOFF_SECONDS = 30


class _Transient(Exception):
    pass


def _send(delivery: Delivery) -> tuple[str, str, dict]:
    """Returns (status, provider_message_id, provider_raw). Raises _Transient to retry."""
    render = (delivery.provider_response or {}).get("render", {})
    if delivery.channel == "email":
        try:
            message_id = email_provider.get_email_provider().send(
                email_provider.EmailMessage(
                    to=delivery.recipient,
                    subject=render.get("subject", ""),
                    text=render.get("text", ""),
                    html=render.get("html", ""),
                )
            )
        # Order matters: SMTPException subclasses OSError, so the specific cases come first.
        except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError) as exc:
            raise _Transient(type(exc).__name__) from exc
        except smtplib.SMTPException as exc:  # recipient refused, data rejected: permanent
            return DeliveryStatus.FAILED, "", {"error": type(exc).__name__}
        except OSError as exc:  # network down, DNS, timeout (TimeoutError is an OSError)
            raise _Transient(type(exc).__name__) from exc
        return DeliveryStatus.SENT, message_id or "", {}

    try:
        result = thrivewave.send(delivery.recipient, render.get("sms", ""))
    except thrivewave.ThrivewaveTransientError as exc:
        raise _Transient(str(exc)) from exc
    if result.dry_run:
        return DeliveryStatus.DRY_RUN, "", {"dry_run": True}
    if not result.ok:
        return DeliveryStatus.FAILED, "", {**result.raw, "error": result.error}
    return DeliveryStatus.SENT, result.provider_message_id, result.raw


@shared_task(ignore_result=True, acks_late=True)
def deliver(delivery_id: int) -> None:
    delivery = Delivery.objects.filter(pk=delivery_id).first()
    if delivery is None or delivery.status not in (DeliveryStatus.QUEUED, DeliveryStatus.FAILED):
        return
    delivery.attempts += 1
    try:
        status, message_id, raw = _send(delivery)
    except _Transient as exc:
        delivery.last_error = f"Attempt {delivery.attempts}: {exc}"[:300]
        if delivery.attempts < Delivery.MAX_ATTEMPTS:
            delivery.status = DeliveryStatus.QUEUED
            delivery.save(update_fields=["attempts", "last_error", "status", "updated_at"])
            countdown = BACKOFF_SECONDS * 2 ** (delivery.attempts - 1)
            deliver.apply_async((delivery.pk,), countdown=countdown)
        else:
            delivery.status = DeliveryStatus.FAILED
            delivery.save(update_fields=["attempts", "last_error", "status", "updated_at"])
        return
    delivery.status = status
    delivery.provider_message_id = message_id
    delivery.provider_response = {**(delivery.provider_response or {}), "provider": raw}
    if status in (DeliveryStatus.SENT, DeliveryStatus.DRY_RUN):
        delivery.sent_at = timezone.now()
        delivery.last_error = ""
    else:
        delivery.last_error = str(raw.get("error", "Rejected by provider"))[:300]
    delivery.save()
    if status == DeliveryStatus.DRY_RUN:
        logger.info(
            "Delivery dry run", extra={"delivery": delivery.pk, "channel": delivery.channel}
        )
