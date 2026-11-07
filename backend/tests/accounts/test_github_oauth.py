from urllib.parse import parse_qs, urlparse

import pytest
import requests
import responses
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts import github_oauth
from apps.accounts.models import ConsentRecord, GithubAccount, User
from apps.accounts.tokens import issue_tokens
from apps.core.models import AuditLog
from tests.factories import PASSWORD, GithubAccountFactory, JobSeekerFactory, UserFactory

pytestmark = pytest.mark.django_db

CALLBACK = "/api/v1/auth/github/callback"
AUTHORIZE = "/api/v1/auth/github/authorize"
GH_TOKEN = "gho_secret_token_value"


def mock_github(
    *,
    github_id=42,
    login="Wanjiru-Dev",
    email="wanjiru@example.com",
    verified=True,
    token_error=False,
):
    if token_error:
        responses.post(github_oauth.TOKEN_URL, json={"error": "bad_verification_code"})
    else:
        responses.post(
            github_oauth.TOKEN_URL,
            json={
                "access_token": GH_TOKEN,
                "scope": "read:user,user:email",
                "token_type": "bearer",
            },
        )
    responses.get(
        f"{github_oauth.API_URL}/user",
        json={
            "id": github_id,
            "login": login,
            "name": "Wanjiru Kamau",
            "avatar_url": "https://a/1.png",
        },
    )
    responses.get(
        f"{github_oauth.API_URL}/user/emails",
        json=[
            {"email": "other@example.com", "primary": False, "verified": True},
            {"email": email, "primary": True, "verified": verified},
        ],
    )


def state(**kwargs):
    kwargs.setdefault("consents", {"terms": True, "email_feedback": True, "sms_feedback": False})
    return github_oauth.make_state(github_oauth.OAuthState(**kwargs))


def test_authorize_returns_url_with_signed_state(api_client):
    response = api_client.get(AUTHORIZE, {"role": "job_seeker", "acceptTerms": "true"})
    assert response.status_code == 200
    body = response.json()
    query = parse_qs(urlparse(body["authorizeUrl"]).query)
    assert query["client_id"] == ["test-client-id"]
    assert query["scope"] == ["read:user user:email"]
    assert query["redirect_uri"] == ["http://localhost:3000/auth/github/callback"]
    assert query["state"] == [body["state"]]
    assert github_oauth.read_state(body["state"]).consents["terms"] is True


def test_authorize_without_config(api_client, settings):
    settings.GITHUB_OAUTH_CLIENT_ID = ""
    response = api_client.get(AUTHORIZE)
    assert response.status_code == 503
    assert response.json()["code"] == "github_not_configured"


@responses.activate
def test_new_user_is_created_as_verified_job_seeker(api_client):
    mock_github()
    response = api_client.post(CALLBACK, {"code": "abc", "state": state()})

    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["created"] is True
    assert body["user"]["role"] == "job_seeker"
    assert body["user"]["emailVerified"] is True
    assert body["user"]["hasPassword"] is False
    assert body["user"]["github"]["login"] == "wanjiru-dev"
    assert AccessToken(body["access"])["githubLogin"] == "wanjiru-dev"

    account = GithubAccount.objects.get(github_id=42)
    assert account.access_token_encrypted != GH_TOKEN  # encrypted at rest
    assert account.get_token() == GH_TOKEN
    assert ConsentRecord.objects.filter(
        user=account.user, consent_type="terms", granted=True
    ).exists()
    assert AuditLog.objects.filter(action="auth.sign_in", actor=account.user).exists()
    # The token exchange sent the secret and the same redirect URI.
    assert "client_secret=test-client-secret" in responses.calls[0].request.body
    assert "redirect_uri=" in responses.calls[0].request.body


@responses.activate
def test_existing_github_id_signs_in_and_refreshes_login_and_token(api_client):
    account = GithubAccountFactory(github_id=42, login="old-name")
    mock_github(login="New-Name")

    body = api_client.post(CALLBACK, {"code": "abc", "state": state()}).json()

    assert body["created"] is False
    assert body["user"]["id"] == str(account.user.public_id)
    account.refresh_from_db()
    assert account.login == "new-name"
    assert account.get_token() == GH_TOKEN


@responses.activate
def test_links_by_verified_email_to_existing_user(api_client):
    user = JobSeekerFactory(email="wanjiru@example.com")
    mock_github()

    body = api_client.post(CALLBACK, {"code": "abc", "state": state()}).json()

    assert body["created"] is False
    assert body["user"]["id"] == str(user.public_id)
    assert GithubAccount.objects.get(user=user).github_id == 42
    user.refresh_from_db()
    assert user.check_password(PASSWORD)  # verified account keeps its password


@responses.activate
def test_email_match_on_unverified_account_drops_the_squatters_password(api_client):
    squatter = JobSeekerFactory(email="wanjiru@example.com", email_verified_at=None)
    mock_github()

    api_client.post(CALLBACK, {"code": "abc", "state": state()})

    squatter.refresh_from_db()
    assert not squatter.has_usable_password()
    assert squatter.is_email_verified


@responses.activate
def test_links_to_signed_in_user(auth_client):
    user = JobSeekerFactory(email="different@example.com")
    mock_github()

    body = auth_client(user).post(CALLBACK, {"code": "abc", "state": state(link=True)}).json()

    assert body["user"]["id"] == str(user.public_id)
    assert body["user"]["github"]["login"] == "wanjiru-dev"
    assert AuditLog.objects.filter(action="auth.github_linked", actor=user).exists()


@responses.activate
def test_signed_in_user_cannot_take_someone_elses_github(auth_client):
    GithubAccountFactory(github_id=42)
    me = JobSeekerFactory()
    mock_github()
    response = auth_client(me).post(CALLBACK, {"code": "abc", "state": state()})
    assert response.status_code == 409
    assert response.json()["code"] == "github_already_linked"


@responses.activate
def test_signed_in_user_with_other_github_must_unlink_first(auth_client):
    account = GithubAccountFactory(github_id=7)
    mock_github(github_id=42)
    response = auth_client(account.user).post(CALLBACK, {"code": "abc", "state": state()})
    assert response.status_code == 409


def test_bad_state(api_client):
    response = api_client.post(CALLBACK, {"code": "abc", "state": "forged"})
    assert response.status_code == 400
    assert response.json()["code"] == "state_invalid"


def test_expired_state(api_client):
    from freezegun import freeze_time

    with freeze_time("2026-11-07 10:00"):
        old = state()
    with freeze_time("2026-11-07 10:11"):
        response = api_client.post(CALLBACK, {"code": "abc", "state": old})
    assert response.json()["code"] == "state_invalid"


@responses.activate
def test_bad_code(api_client):
    mock_github(token_error=True)
    response = api_client.post(CALLBACK, {"code": "used", "state": state()})
    assert response.status_code == 400
    assert response.json()["code"] == "github_oauth_failed"


@responses.activate
def test_github_down(api_client):
    responses.post(github_oauth.TOKEN_URL, body=requests.ConnectionError("down"))
    response = api_client.post(CALLBACK, {"code": "abc", "state": state()})
    assert response.json()["code"] == "github_oauth_failed"


@responses.activate
def test_unverified_github_email(api_client):
    mock_github(verified=False)
    response = api_client.post(CALLBACK, {"code": "abc", "state": state()})
    assert response.json()["code"] == "github_email_unverified"
    assert not User.objects.exists()


@responses.activate
def test_new_signup_without_terms(api_client):
    mock_github()
    response = api_client.post(CALLBACK, {"code": "abc", "state": state(consents={})})
    assert response.json()["code"] == "terms_required"


@responses.activate
def test_recruiters_cannot_sign_up_through_github(api_client):
    mock_github()
    response = api_client.post(CALLBACK, {"code": "abc", "state": state(role="recruiter")})
    assert response.json()["code"] == "recruiter_signup_requires_email"


@responses.activate
def test_suspended_user_cannot_sign_in_with_github(api_client):
    account = GithubAccountFactory(github_id=42)
    account.user.is_active = False
    account.user.save()
    mock_github()
    response = api_client.post(CALLBACK, {"code": "abc", "state": state()})
    assert response.status_code == 401


@responses.activate
def test_login_moved_to_new_github_id_frees_the_stale_row(api_client):
    stale = GithubAccountFactory(github_id=7, login="wanjiru-dev")
    mock_github(github_id=42, login="wanjiru-dev")
    assert api_client.post(CALLBACK, {"code": "abc", "state": state()}).status_code == 200
    stale.refresh_from_db()
    assert stale.login == "~42"


class TestUnlink:
    URL = "/api/v1/auth/github"

    def test_unlink(self, auth_client):
        account = GithubAccountFactory()
        assert auth_client(account.user).delete(self.URL).status_code == 204
        assert not GithubAccount.objects.exists()

    def test_refused_without_password(self, auth_client):
        account = GithubAccountFactory()
        account.user.set_unusable_password()
        account.user.save()
        response = auth_client(account.user).delete(self.URL)
        assert response.status_code == 409
        assert response.json()["code"] == "password_required"

    def test_nothing_linked(self, auth_client):
        response = auth_client(UserFactory()).delete(self.URL)
        assert response.json()["code"] == "github_not_linked"


def test_token_scope_and_claims_with_issue_tokens():
    account = GithubAccountFactory(login="Dev-1")
    assert AccessToken(issue_tokens(account.user)["access"])["githubLogin"] == "dev-1"
