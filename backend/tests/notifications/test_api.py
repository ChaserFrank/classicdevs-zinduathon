import hashlib
import hmac
import json

import pytest
from django.utils import timezone

from apps.accounts.models import ConsentRecord
from apps.accounts.services import record_consents
from apps.notifications import services
from apps.notifications.models import Delivery, Notification, NotificationPreference
from tests.factories import JobSeekerFactory

pytestmark = pytest.mark.django_db
SECRET = "whsec-test"


class TestPreferences:
    URL = "/api/v1/me/notification-preferences"

    def test_get_matrix_camel_cased(self, auth_client):
        user = JobSeekerFactory()
        record_consents(user, {"terms": True, "email_feedback": True})
        body = auth_client(user).get(self.URL).json()
        assert body["matrix"]["recruiterFeedback"] == {"inApp": True, "email": True, "sms": False}
        assert body["smsReady"] is False

    def test_put_updates_and_records_consent(self, auth_client):
        user = JobSeekerFactory(phone="+254712345678", phone_verified_at=timezone.now())
        record_consents(user, {"terms": True})
        response = auth_client(user).put(
            self.URL,
            {"preferences": [{"kind": "recruiter_feedback", "channel": "sms", "enabled": True}]},
        )
        assert response.status_code == 200
        assert response.json()["matrix"]["recruiterFeedback"]["sms"] is True
        assert response.json()["smsReady"] is True
        latest = ConsentRecord.objects.filter(user=user, consent_type="sms_feedback").latest(
            "created_at"
        )
        assert latest.granted is True

    def test_turning_off_all_sms_withdraws_consent(self, auth_client):
        user = JobSeekerFactory()
        record_consents(user, {"terms": True, "sms_feedback": True})
        changes = [
            {"kind": k, "channel": "sms", "enabled": False}
            for k in ("analysis_completed", "recruiter_feedback", "shortlisted")
        ]
        auth_client(user).put(self.URL, {"preferences": changes})
        latest = (
            ConsentRecord.objects.filter(user=user, consent_type="sms_feedback")
            .order_by("-id")
            .first()
        )
        assert latest.granted is False

    def test_unavailable_cell_rejected(self, auth_client):
        response = auth_client(JobSeekerFactory()).put(
            self.URL,
            {"preferences": [{"kind": "analysis_failed", "channel": "sms", "enabled": True}]},
        )
        assert response.status_code == 400

    def test_other_roles_kinds_rejected(self, auth_client, recruiter):
        response = auth_client(recruiter).put(
            self.URL,
            {"preferences": [{"kind": "recruiter_feedback", "channel": "email", "enabled": True}]},
        )
        assert response.status_code == 400

    def test_requires_sign_in(self, api_client):
        assert api_client.get(self.URL).status_code == 401


class TestInbox:
    def make(self, user, n=3):
        return [
            Notification.objects.create(user=user, kind="analysis_completed", title=f"t{i}")
            for i in range(n)
        ]

    def test_list_unread_and_read(self, auth_client):
        user = JobSeekerFactory()
        notes = self.make(user)
        self.make(JobSeekerFactory(), 2)  # someone else's
        client = auth_client(user)
        assert client.get("/api/v1/notifications").json()["count"] == 3
        read = client.post(f"/api/v1/notifications/{notes[0].public_id}/read").json()
        assert read["readAt"] is not None
        assert client.get("/api/v1/notifications", {"unread": "true"}).json()["count"] == 2
        assert client.post("/api/v1/notifications/read-all").json() == {"updated": 2}
        assert client.get("/api/v1/notifications", {"unread": "true"}).json()["count"] == 0

    def test_cannot_read_others(self, auth_client):
        [note] = self.make(JobSeekerFactory(), 1)
        assert (
            auth_client(JobSeekerFactory())
            .post(f"/api/v1/notifications/{note.public_id}/read")
            .status_code
            == 404
        )

    def test_shape(self, auth_client):
        user = JobSeekerFactory()
        self.make(user, 1)
        item = auth_client(user).get("/api/v1/notifications").json()["results"][0]
        assert set(item) == {"id", "kind", "title", "body", "linkPath", "readAt", "createdAt"}


@pytest.fixture
def webhook_secret(settings):
    settings.THRIVEWAVE_WEBHOOK_SECRET = SECRET


def signed(client, url, payload, *, secret=SECRET, header="sig"):
    raw = json.dumps(payload).encode()
    headers = {}
    if header == "sig":
        headers["HTTP_X_THRIVEWAVE_SIGNATURE"] = (
            "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        )
    elif header == "shared":
        headers["HTTP_X_THRIVEWAVE_SECRET"] = secret
    return client.post(url, raw, content_type="application/json", **headers)


@pytest.fixture
def sms_delivery():
    user = JobSeekerFactory()
    note = Notification.objects.create(user=user, kind="recruiter_feedback", title="t")
    return Delivery.objects.create(
        notification=note,
        channel="sms",
        recipient="+254712345678",
        provider="thrivewave",
        status="sent",
        provider_message_id="tw-9",
    )


class TestDeliveryWebhook:
    URL = "/api/v1/webhooks/thrivewave/delivery"

    def test_valid_signature_marks_delivered(self, client, webhook_secret, sms_delivery):
        response = signed(client, self.URL, {"message_id": "tw-9", "status": "DELIVERED"})
        assert response.json() == {"ok": True, "updated": True}
        sms_delivery.refresh_from_db()
        assert sms_delivery.status == "delivered" and sms_delivery.delivered_at

    def test_shared_secret_header_and_failure(self, client, webhook_secret, sms_delivery):
        signed(client, self.URL, {"messageId": "tw-9", "status": "undelivered"}, header="shared")
        sms_delivery.refresh_from_db()
        assert sms_delivery.status == "failed"

    def test_invalid_signature(self, client, webhook_secret, sms_delivery):
        response = signed(
            client, self.URL, {"message_id": "tw-9", "status": "delivered"}, secret="wrong"
        )
        assert response.status_code == 403
        sms_delivery.refresh_from_db()
        assert sms_delivery.status == "sent"

    def test_refused_when_no_secret_configured(self, client, settings, sms_delivery):
        settings.THRIVEWAVE_WEBHOOK_SECRET = ""
        assert signed(client, self.URL, {"message_id": "tw-9"}, header="shared").status_code == 403

    def test_duplicate_is_idempotent(self, client, webhook_secret, sms_delivery):
        payload = {"message_id": "tw-9", "status": "delivered"}
        signed(client, self.URL, payload)
        assert signed(client, self.URL, payload).json() == {"ok": True, "updated": False}
        # A late "failed" after "delivered" doesn't overwrite it.
        signed(client, self.URL, {"message_id": "tw-9", "status": "failed"})
        sms_delivery.refresh_from_db()
        assert sms_delivery.status == "delivered"

    def test_unknown_id_and_interim_status(self, client, webhook_secret, sms_delivery):
        assert (
            signed(client, self.URL, {"message_id": "nope", "status": "delivered"}).json()[
                "updated"
            ]
            is False
        )
        assert (
            signed(client, self.URL, {"message_id": "tw-9", "status": "queued"}).json()["updated"]
            is False
        )
        assert signed(client, self.URL, {"garbage": True}).status_code == 200

    def test_malformed_body(self, client, webhook_secret):
        raw = b"not json"
        sig = hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
        response = client.post(
            self.URL, raw, content_type="application/json", HTTP_X_THRIVEWAVE_SIGNATURE=sig
        )
        assert response.json() == {"ok": True, "updated": False}


class TestInboundStop:
    URL = "/api/v1/webhooks/thrivewave/inbound"

    def test_stop_disables_sms_and_withdraws_consent(self, client, webhook_secret):
        user = JobSeekerFactory(phone="+254712345678")
        record_consents(user, {"terms": True, "sms_feedback": True})
        services.ensure_defaults(user)
        response = signed(client, self.URL, {"from": "254712345678", "message": " Stop "})
        assert response.json() == {"ok": True, "updated": True}
        assert not NotificationPreference.objects.filter(
            user=user, channel="sms", enabled=True
        ).exists()
        assert services._consents(user)["sms_feedback"] is False

    @pytest.mark.parametrize(
        ("sender", "text"),
        [("254712345678", "hello"), ("garbage", "STOP"), ("254799999999", "STOP")],
    )
    def test_ignored(self, client, webhook_secret, sender, text):
        JobSeekerFactory(phone="+254712345678")
        assert (
            signed(client, self.URL, {"from": sender, "message": text}).json()["updated"] is False
        )

    def test_signature_required(self, client, webhook_secret):
        assert (
            signed(client, self.URL, {"from": "1", "message": "STOP"}, header="none").status_code
            == 403
        )
