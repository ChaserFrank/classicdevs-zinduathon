from unittest import mock

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

URL = "/api/v1/health"


def test_url_name_resolves():
    assert reverse("health") == URL


def test_healthy_when_database_and_redis_answer(api_client, settings):
    settings.APP_VERSION = "1.2.3"
    settings.GIT_COMMIT_SHA = "abc1234"

    response = api_client.get(URL)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"database": "ok", "redis": "ok"}
    assert body["version"] == "1.2.3"
    assert body["commitSha"] == "abc1234"  # camelCase in JSON
    assert "time" in body


def test_degraded_when_redis_is_down(api_client, settings):
    settings.REDIS_URL = "redis://localhost:1/0"  # nothing listens on port 1

    response = api_client.get(URL)

    assert response.status_code == 503
    assert response.json()["checks"] == {"database": "ok", "redis": "down"}
    assert response.json()["status"] == "degraded"


def test_degraded_when_database_is_down(api_client):
    with mock.patch("apps.core.health.connection") as conn:
        conn.cursor.side_effect = Exception("db down")
        response = api_client.get(URL)

    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "down"


def test_health_needs_no_authentication_and_ignores_bad_tokens(api_client):
    api_client.credentials(HTTP_AUTHORIZATION="Bearer not-a-token")
    assert api_client.get(URL).status_code == 200
