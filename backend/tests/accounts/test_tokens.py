import pytest
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.tokens import issue_tokens
from apps.companies.models import ApprovalStatus
from tests.factories import GithubAccountFactory

pytestmark = pytest.mark.django_db

REFRESH = "/api/v1/auth/token/refresh"
LOGOUT = "/api/v1/auth/logout"


def test_tokens_use_public_id_not_internal_id(job_seeker):
    access = AccessToken(issue_tokens(job_seeker)["access"])
    assert access["user_id"] == str(job_seeker.public_id)


def test_refresh_rotates_and_blacklists_old_token(api_client, job_seeker):
    pair = issue_tokens(job_seeker)

    first = api_client.post(REFRESH, {"refresh": pair["refresh"]})
    assert first.status_code == 200
    assert set(first.json()) == {"access", "refresh"}
    assert first.json()["refresh"] != pair["refresh"]

    reused = api_client.post(REFRESH, {"refresh": pair["refresh"]})
    assert reused.status_code == 401
    assert reused.json()["code"] == "token_invalid"

    assert api_client.post(REFRESH, {"refresh": first.json()["refresh"]}).status_code == 200


def test_refresh_reloads_claims_from_database(api_client, pending_recruiter):
    pair = issue_tokens(pending_recruiter)
    profile = pending_recruiter.recruiter_profile
    profile.approval_status = ApprovalStatus.APPROVED
    profile.save()
    GithubAccountFactory(user=pending_recruiter, login="Otieno-Dev")

    access = AccessToken(api_client.post(REFRESH, {"refresh": pair["refresh"]}).json()["access"])

    assert access["approvalStatus"] == "approved"
    assert access["githubLogin"] == "otieno-dev"


def test_refresh_refused_for_suspended_user(api_client, job_seeker):
    pair = issue_tokens(job_seeker)
    job_seeker.is_active = False
    job_seeker.save()
    assert api_client.post(REFRESH, {"refresh": pair["refresh"]}).status_code == 401


def test_refresh_with_garbage(api_client):
    response = api_client.post(REFRESH, {"refresh": "garbage"})
    assert response.status_code == 401
    assert response.json()["code"] == "token_invalid"


def test_access_token_cannot_be_used_as_refresh(api_client, job_seeker):
    pair = issue_tokens(job_seeker)
    assert api_client.post(REFRESH, {"refresh": pair["access"]}).status_code == 401


def test_logout_blacklists_refresh_token(api_client, auth_client, job_seeker):
    pair = issue_tokens(job_seeker)
    client = auth_client(job_seeker)

    assert client.post(LOGOUT, {"refresh": pair["refresh"]}).status_code == 204
    assert api_client.post(REFRESH, {"refresh": pair["refresh"]}).status_code == 401


def test_logout_requires_authentication(api_client, job_seeker):
    response = api_client.post(LOGOUT, {"refresh": issue_tokens(job_seeker)["refresh"]})
    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_cannot_log_out_someone_elses_token(auth_client, job_seeker, recruiter):
    other_refresh = issue_tokens(recruiter)["refresh"]
    response = auth_client(job_seeker).post(LOGOUT, {"refresh": other_refresh})
    assert response.status_code == 401


def test_logout_with_invalid_token(auth_client, job_seeker):
    assert auth_client(job_seeker).post(LOGOUT, {"refresh": "nope"}).status_code == 401


def test_expired_or_tampered_access_token_gets_token_invalid(api_client, job_seeker):
    access = issue_tokens(job_seeker)["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access[:-2]}xx")
    response = api_client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.json()["code"] == "token_invalid"
    assert response["WWW-Authenticate"].startswith("Bearer")
