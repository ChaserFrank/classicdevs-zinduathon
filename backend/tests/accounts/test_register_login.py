import pytest
from django.core import mail
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.models import ConsentRecord, Role, User
from apps.companies.models import Company
from apps.core.models import AuditLog
from tests.factories import PASSWORD, CompanyFactory, UserFactory

pytestmark = pytest.mark.django_db

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"


def job_seeker_body(**overrides):
    body = {
        "email": "Wanjiru@Example.com",
        "password": PASSWORD,
        "role": "job_seeker",
        "fullName": "Wanjiru Kamau",
        "phone": "0712 345 678",
        "consents": {"terms": True, "emailFeedback": True, "smsFeedback": True},
    }
    body.update(overrides)
    return body


class TestRegister:
    def test_job_seeker_gets_tokens_profile_consents_and_email(
        self, api_client, django_capture_on_commit_callbacks
    ):
        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(REGISTER, job_seeker_body())

        assert response.status_code == 201, response.json()
        body = response.json()
        assert set(body) == {"access", "refresh", "user"}
        me = body["user"]
        assert me["email"] == "wanjiru@example.com"
        assert me["role"] == "job_seeker"
        assert me["phone"] == "+254712345678"
        assert me["emailVerified"] is False
        assert me["jobSeekerProfile"] == {
            "headline": "",
            "location": "",
            "cardVisible": True,
            "openToWork": True,
        }
        assert me["recruiterProfile"] is None

        user = User.objects.get(email="wanjiru@example.com")
        consents = dict(
            ConsentRecord.objects.filter(user=user).values_list("consent_type", "granted")
        )
        assert consents == {
            "terms": True,
            "privacy": True,
            "email_feedback": True,
            "sms_feedback": True,
        }
        assert len(mail.outbox) == 1
        assert "verify-email?token=" in mail.outbox[0].body
        assert AuditLog.objects.filter(action="auth.register", actor=user).exists()

    def test_access_token_carries_role_claim(self, api_client):
        access = api_client.post(REGISTER, job_seeker_body()).json()["access"]
        token = AccessToken(access)
        assert token["role"] == "job_seeker"
        assert "approvalStatus" not in token

    def test_recruiter_is_pending_and_company_reused_case_insensitively(self, api_client):
        CompanyFactory(name="Acme Kenya")
        response = api_client.post(
            REGISTER,
            {
                "email": "otieno@acme.co.ke",
                "password": PASSWORD,
                "role": "recruiter",
                "fullName": "Brian Otieno",
                "companyName": "  acme   kenya ",
                "consents": {"terms": True},
            },
        )
        assert response.status_code == 201, response.json()
        profile = response.json()["user"]["recruiterProfile"]
        assert profile["approvalStatus"] == "pending"
        assert profile["company"]["name"] == "Acme Kenya"
        assert Company.objects.count() == 1
        assert AccessToken(response.json()["access"])["approvalStatus"] == "pending"

    def test_recruiter_needs_company(self, api_client):
        response = api_client.post(
            REGISTER, job_seeker_body(role="recruiter", consents={"terms": True})
        )
        assert response.status_code == 400
        assert "companyName" in response.json()["fields"]

    def test_admin_role_cannot_self_register(self, api_client):
        response = api_client.post(REGISTER, job_seeker_body(role="admin"))
        assert response.status_code == 400
        assert "role" in response.json()["fields"]

    def test_terms_must_be_accepted(self, api_client):
        response = api_client.post(REGISTER, job_seeker_body(consents={"terms": False}))
        assert response.status_code == 400
        assert "consents.terms" in response.json()["fields"]

    def test_sms_consent_requires_phone(self, api_client):
        response = api_client.post(
            REGISTER,
            job_seeker_body(phone="", consents={"terms": True, "smsFeedback": True}),
        )
        assert response.json()["fields"]["phone"] == [
            "Add a phone number to receive feedback by SMS."
        ]

    def test_duplicate_email_case_insensitive(self, api_client):
        UserFactory(email="wanjiru@example.com")
        response = api_client.post(REGISTER, job_seeker_body())
        assert response.status_code == 400
        assert "email" in response.json()["fields"]

    def test_weak_password_rejected(self, api_client):
        response = api_client.post(REGISTER, job_seeker_body(password="12345678"))
        assert response.status_code == 400
        assert "password" in response.json()["fields"]

    @pytest.mark.parametrize("phone", ["12345", "+2547123", "07123"])
    def test_invalid_phone(self, api_client, phone):
        response = api_client.post(REGISTER, job_seeker_body(phone=phone))
        assert response.status_code == 400
        assert "phone" in response.json()["fields"]

    def test_phone_already_used(self, api_client):
        UserFactory(phone="+254712345678")
        response = api_client.post(REGISTER, job_seeker_body(phone="254712345678"))
        assert response.json()["fields"]["phone"] == [
            "This phone number is used by another account."
        ]


class TestLogin:
    def test_success_returns_tokens_and_user(self, api_client, job_seeker):
        response = api_client.post(LOGIN, {"email": job_seeker.email.upper(), "password": PASSWORD})
        assert response.status_code == 200
        assert response.json()["user"]["email"] == job_seeker.email
        job_seeker.refresh_from_db()
        assert job_seeker.last_login is not None
        assert AuditLog.objects.filter(action="auth.sign_in", actor=job_seeker).exists()

    def test_wrong_password_is_audited(self, api_client, job_seeker):
        response = api_client.post(LOGIN, {"email": job_seeker.email, "password": "nope"})
        assert response.status_code == 401
        assert response.json()["code"] == "invalid_credentials"
        entry = AuditLog.objects.get(action="auth.sign_in_failed")
        assert entry.metadata == {"email": job_seeker.email}
        assert "password" not in str(entry.metadata)

    def test_suspended_user_cannot_sign_in(self, api_client, job_seeker):
        job_seeker.is_active = False
        job_seeker.save()
        response = api_client.post(LOGIN, {"email": job_seeker.email, "password": PASSWORD})
        assert response.json()["code"] == "invalid_credentials"

    def test_throttled_after_five_attempts_per_ip_and_email(self, api_client, job_seeker):
        for _ in range(5):
            api_client.post(LOGIN, {"email": job_seeker.email, "password": "wrong"})
        response = api_client.post(LOGIN, {"email": job_seeker.email, "password": PASSWORD})
        assert response.status_code == 429
        assert response.json()["code"] == "rate_limited"
        # Another email from the same IP is not locked out.
        other = UserFactory()
        assert (
            api_client.post(LOGIN, {"email": other.email, "password": PASSWORD}).status_code == 200
        )

    def test_recruiter_token_has_approval_status(self, api_client, pending_recruiter):
        access = api_client.post(
            LOGIN, {"email": pending_recruiter.email, "password": PASSWORD}
        ).json()["access"]
        assert AccessToken(access)["approvalStatus"] == "pending"
        assert AccessToken(access)["role"] == Role.RECRUITER
