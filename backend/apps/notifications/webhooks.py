"""Thrivewave webhooks: delivery reports and inbound STOP replies.

Their format isn't public yet, so `verify_signature`, `parse_delivery_report` and `parse_inbound`
are the swappable pieces. The signature check accepts either an HMAC-SHA256 of the raw body in
`X-Thrivewave-Signature` (hex, optional `sha256=` prefix) or the shared secret itself in
`X-Thrivewave-Secret`. Without a configured secret every call is refused.
"""

import hashlib
import hmac
import json

from django.conf import settings

DELIVERED = {"delivered", "deliveredtoterminal", "success", "delivrd"}
FAILED = {"failed", "undelivered", "rejected", "expired", "undeliv", "deliveryimpossible"}


def verify_signature(raw_body: bytes, headers) -> bool:
    secret = settings.THRIVEWAVE_WEBHOOK_SECRET
    if not secret:
        return False
    signature = headers.get("X-Thrivewave-Signature", "")
    if signature:
        signature = signature.removeprefix("sha256=")
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
    shared = headers.get("X-Thrivewave-Secret", "")
    return bool(shared) and hmac.compare_digest(shared, secret)


def _load(raw_body: bytes) -> dict:
    try:
        data = json.loads(raw_body or b"{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def parse_delivery_report(raw_body: bytes) -> tuple[str, str | None]:
    """→ (provider_message_id, "delivered" | "failed" | None for interim states)."""
    data = _load(raw_body)
    message_id = str(next((data[k] for k in ("message_id", "messageId", "id") if data.get(k)), ""))
    state = str(data.get("status") or data.get("delivery_status") or "").replace(" ", "").lower()
    if state in DELIVERED:
        return message_id, "delivered"
    if state in FAILED:
        return message_id, "failed"
    return message_id, None


def parse_inbound(raw_body: bytes) -> tuple[str, str]:
    """→ (sender phone as given, message text)."""
    data = _load(raw_body)
    sender = str(data.get("from") or data.get("phone") or data.get("msisdn") or "")
    text = str(data.get("message") or data.get("text") or "")
    return sender, text
