import re

import pytest
from django.core import mail, signing
from freezegun import freeze_time

from apps.accounts import tokens
from apps.accounts.tokens import issue_tokens
from apps.core.models import AuditLog
from tests.factories import PASSWORD, UserFactory

pytestmark = pytest.mark.django_db

NEW_PASSWORD = "a-much-better-passphrase"


def token_from(message) -> str:
    return re.search(r"token=([^\s]+)", message.body).group(1)


class TestEmailVerification:
    def test_verify_with_emailed_token(self, api_client):
        user = UserFactory(email_verified_at=None)
        response = api_client.post(
            "/api/v1/auth/email/verify", {"token": tokens.make_email_token(user)}
        )
        assert response.status_code == 200
        assert response.json()["emailVerified"] is True
        assert AuditLog.objects.filter(action="auth.email_verified").count() == 1

        # Idempotent: verifying again is fine and not re-audited.
        api_client.post("/api/v1/auth/email/verify", {"token": tokens.make_email_token(user)})
        assert AuditLog.objects.filter(action="auth.email_verified").count() == 1

    def test_token_bound_to_email_address(self, api_client):
        user = UserFactory(email_verified_at=None)
        token = tokens.make_email_token(user)
        user.email = "changed@example.com"
        user.save()
        response = api_client.post("/api/v1/auth/email/verify", {"token": token})
        assert response.status_code == 400
        assert response.json()["code"] == "token_invalid"

    def test_expired_token(self, api_client):
        user = UserFactory(email_verified_at=None)
        with freeze_time("2026-11-01"):
            token = tokens.make_email_token(user)
        with freeze_time("2026-11-05"):
            response = api_client.post("/api/v1/auth/email/verify", {"token": token})
        assert response.json()["code"] == "token_invalid"

    def test_resend_only_when_unverified(self, auth_client):
        unverified = UserFactory(email_verified_at=None)
        verified = UserFactory()
        assert auth_client(unverified).post("/api/v1/auth/email/resend").status_code == 204
        assert auth_client(verified).post("/api/v1/auth/email/resend").status_code == 204
        assert [m.to for m in mail.outbox] == [[unverified.email]]

    def test_resend_requires_sign_in(self, api_client):
        assert api_client.post("/api/v1/auth/email/resend").status_code == 401


class TestPasswordReset:
    def test_full_flow_signs_out_everywhere(self, api_client):
        user = UserFactory(email_verified_at=None)
        old_refresh = issue_tokens(user)["refresh"]

        assert (
            api_client.post(
                "/api/v1/auth/password/reset", {"email": user.email.upper()}
            ).status_code
            == 204
        )
        token = token_from(mail.outbox[0])
        response = api_client.post(
            "/api/v1/auth/password/reset/confirm", {"token": token, "newPassword": NEW_PASSWORD}
        )
        assert response.status_code == 204

        user.refresh_from_db()
        assert user.check_password(NEW_PASSWORD)
        assert user.is_email_verified  # proved control of the inbox
        assert (
            api_client.post("/api/v1/auth/token/refresh", {"refresh": old_refresh}).status_code
            == 401
        )
        assert AuditLog.objects.filter(action="auth.password_reset").exists()

    def test_link_works_once(self, api_client, user):
        token = tokens.make_reset_token(user)
        url = "/api/v1/auth/password/reset/confirm"
        assert (
            api_client.post(url, {"token": token, "newPassword": NEW_PASSWORD}).status_code == 204
        )
        again = api_client.post(url, {"token": token, "newPassword": "yet-another-passphrase"})
        assert again.json()["code"] == "token_invalid"

    def test_link_expires_after_an_hour(self, api_client, user):
        with freeze_time("2026-11-07 10:00"):
            token = tokens.make_reset_token(user)
        with freeze_time("2026-11-07 11:01"):
            response = api_client.post(
                "/api/v1/auth/password/reset/confirm", {"token": token, "newPassword": NEW_PASSWORD}
            )
        assert response.json()["code"] == "token_invalid"

    def test_unknown_email_still_204_and_no_mail(self, api_client):
        response = api_client.post("/api/v1/auth/password/reset", {"email": "ghost@example.com"})
        assert response.status_code == 204
        assert mail.outbox == []

    def test_weak_new_password(self, api_client, user):
        response = api_client.post(
            "/api/v1/auth/password/reset/confirm",
            {"token": tokens.make_reset_token(user), "newPassword": "password"},
        )
        assert response.status_code == 400
        assert "newPassword" in response.json()["fields"]

    def test_tampered_token(self, api_client, user):
        forged = signing.dumps({"u": str(user.public_id), "t": "abc-123"}, salt=tokens.RESET_SALT)
        response = api_client.post(
            "/api/v1/auth/password/reset/confirm", {"token": forged, "newPassword": NEW_PASSWORD}
        )
        assert response.json()["code"] == "token_invalid"

    def test_reset_throttled(self, api_client):
        for _ in range(5):
            api_client.post("/api/v1/auth/password/reset", {"email": "a@example.com"})
        response = api_client.post("/api/v1/auth/password/reset", {"email": "a@example.com"})
        assert response.status_code == 429


class TestPasswordChange:
    URL = "/api/v1/auth/password/change"

    def test_change_returns_new_tokens_and_revokes_old(self, api_client, auth_client, user):
        old_refresh = issue_tokens(user)["refresh"]
        response = auth_client(user).post(
            self.URL, {"currentPassword": PASSWORD, "newPassword": NEW_PASSWORD}
        )
        assert response.status_code == 200
        assert set(response.json()) == {"access", "refresh"}
        user.refresh_from_db()
        assert user.check_password(NEW_PASSWORD)
        assert (
            api_client.post("/api/v1/auth/token/refresh", {"refresh": old_refresh}).status_code
            == 401
        )

    def test_wrong_current_password(self, auth_client, user):
        response = auth_client(user).post(
            self.URL, {"currentPassword": "x", "newPassword": NEW_PASSWORD}
        )
        assert response.json()["fields"] == {"currentPassword": ["Current password is wrong."]}

    def test_github_only_account_can_set_first_password(self, auth_client):
        user = UserFactory(password=None)
        user.set_unusable_password()
        user.save()
        response = auth_client(user).post(self.URL, {"newPassword": NEW_PASSWORD})
        assert response.status_code == 200
