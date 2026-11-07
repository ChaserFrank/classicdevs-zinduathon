from urllib.parse import parse_qs, urlparse

import pytest

pytestmark = pytest.mark.django_db


def test_dev_pages_hidden_by_default(client):
    assert client.get("/api/v1/auth/github/dev-login").status_code == 404
    assert client.get("/api/v1/auth/github/dev-callback?code=a&state=b").status_code == 404


@pytest.fixture
def dev_enabled(settings):
    settings.GITHUB_DEV_CALLBACK_ENABLED = True


def test_dev_login_redirects_to_github_with_state_cookie(client, dev_enabled):
    response = client.get("/api/v1/auth/github/dev-login")
    assert response.status_code == 302
    url = urlparse(response["Location"])
    assert url.netloc == "github.com"
    state = parse_qs(url.query)["state"][0]
    assert response.cookies["sp_oauth_state"].value == state


def test_dev_callback_renders_code_safely(client, dev_enabled):
    response = client.get(
        "/api/v1/auth/github/dev-callback", {"code": "</script><b>x", "state": "s"}
    )
    assert response.status_code == 200
    html = response.content.decode()
    assert "</script><b>x" not in html  # escaped by json_script
    assert "/api/v1/auth/github/callback" in html


def test_dev_callback_not_in_schema(client):
    schema = client.get("/api/v1/schema/", HTTP_ACCEPT="application/vnd.oai.openapi+json").json()
    assert not any("dev-" in p for p in schema["paths"])


def test_dev_login_explains_missing_oauth_config(client, dev_enabled, settings):
    settings.GITHUB_OAUTH_CLIENT_ID = ""
    response = client.get("/api/v1/auth/github/dev-login")
    assert response.status_code == 503
    assert "GITHUB_OAUTH_CLIENT_ID" in response.content.decode()
