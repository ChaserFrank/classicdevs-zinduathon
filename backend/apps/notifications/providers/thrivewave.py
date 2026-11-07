"""Thrivewave SMS adapter.

Thrivewave Solutions (Kenya) sells bulk SMS over REST and SMPP, but its API reference is not
public. Everything that depends on their request/response format is in `build_payload` and
`parse_response`; when the organisers share the docs, only those two functions change.

Until then the adapter runs in **dry run** (no network) whenever SMS_DRY_RUN is true or a
credential is missing, so the demo never breaks because of a missing key.
"""

import logging
from dataclasses import dataclass, field

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SmsResult:
    ok: bool
    provider_message_id: str = ""
    raw: dict = field(default_factory=dict)
    error: str = ""
    dry_run: bool = False


class ThrivewaveTransientError(Exception):
    """Network error, timeout or 5xx: worth retrying."""


class ThrivewaveClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        sender_id: str,
        *,
        username: str | None = None,
        sms_path: str = "/sms/send",
        timeout: float = 10,
        session: requests.Session | None = None,
    ):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self.sender_id = sender_id
        self.username = username
        self.sms_path = sms_path if sms_path.startswith("/") else f"/{sms_path}"
        self.timeout = timeout
        self.session = session or requests.Session()

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key and self.sender_id)

    def build_payload(self, to_e164: str, message: str) -> tuple[dict, dict]:
        """Return (headers, json_body). THE ONLY PLACE THAT KNOWS THRIVEWAVE'S REQUEST FORMAT.

        Placeholder until the organisers' docs arrive: Bearer api_key header,
        body {"sender_id", "phone" (2547XXXXXXXX, no plus), "message"}."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        body = {"sender_id": self.sender_id, "phone": to_e164.lstrip("+"), "message": message}
        if self.username:
            body["username"] = self.username
        return headers, body

    def parse_response(self, status_code: int, body: dict | str) -> SmsResult:
        """SmsResult(ok, provider_message_id, raw). Treat 2xx as success unless the body says
        otherwise (placeholder: `success: false` or `status: "error"/"failed"`)."""
        raw = body if isinstance(body, dict) else {"text": str(body)[:500]}
        if not 200 <= status_code < 300:
            return SmsResult(ok=False, raw=raw, error=f"HTTP {status_code}")
        if raw.get("success") is False or str(raw.get("status", "")).lower() in {"error", "failed"}:
            return SmsResult(ok=False, raw=raw, error=str(raw.get("message") or "Rejected")[:300])
        message_id = next(
            (str(raw[k]) for k in ("message_id", "messageId", "id", "request_id") if raw.get(k)),
            "",
        )
        return SmsResult(ok=True, provider_message_id=message_id, raw=raw)

    def send_sms(self, to_e164: str, message: str) -> SmsResult:
        headers, body = self.build_payload(to_e164, message)
        try:
            response = self.session.post(
                f"{self.base_url}{self.sms_path}", json=body, headers=headers, timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise ThrivewaveTransientError(type(exc).__name__) from exc
        if response.status_code >= 500:
            raise ThrivewaveTransientError(f"HTTP {response.status_code}")
        try:
            parsed = response.json()
        except ValueError:
            parsed = response.text
        return self.parse_response(response.status_code, parsed)


def get_client() -> ThrivewaveClient:
    return ThrivewaveClient(
        settings.THRIVEWAVE_BASE_URL,
        settings.THRIVEWAVE_API_KEY,
        settings.THRIVEWAVE_SENDER_ID,
        username=settings.THRIVEWAVE_USERNAME or None,
        sms_path=settings.THRIVEWAVE_SMS_PATH,
    )


def is_dry_run(client: ThrivewaveClient | None = None) -> bool:
    return settings.SMS_DRY_RUN or not (client or get_client()).configured


def send(to_e164: str, message: str) -> SmsResult:
    """Send, or dry-run without touching the network. The message text is never logged."""
    client = get_client()
    if is_dry_run(client):
        from apps.accounts.phone import mask

        logger.info("SMS dry run", extra={"to": mask(to_e164), "length": len(message)})
        return SmsResult(ok=True, dry_run=True)
    return client.send_sms(to_e164, message)
