"""Behaviour the hosting platform depends on (docs/DEPLOYMENT.md)."""

import json
import os
import subprocess
import sys

import pytest

pytestmark = pytest.mark.django_db


def test_health_answers_any_host_header(client, settings):
    settings.ALLOWED_HOSTS = ["api.skillproof.test"]
    response = client.get("/api/v1/health", HTTP_HOST="10.0.0.7:8080")
    assert response.status_code == 200
    assert response.json()["checks"] == {"database": "ok", "redis": "ok"}
    assert response["X-Request-ID"]


def test_other_paths_still_validate_host(client, settings):
    settings.ALLOWED_HOSTS = ["api.skillproof.test"]
    assert client.get("/api/v1/skills", HTTP_HOST="10.0.0.7").status_code == 400


def test_health_is_not_redirected_to_https(client, settings):
    settings.SECURE_SSL_REDIRECT = True
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/skills").status_code == 301


def test_health_head_and_post(client):
    assert client.head("/api/v1/health").status_code == 200
    assert client.post("/api/v1/health").status_code == 405  # falls through to the DRF view


def _prod_settings(extra_env: dict) -> dict:
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.prod",
        "DJANGO_SECRET_KEY": "x" * 60,
        "DJANGO_ALLOWED_HOSTS": "api.skillproof.app,.rumpty.app",
        "CORS_ALLOWED_ORIGINS": "https://skillproof.app",
        **extra_env,
    }
    code = (
        "import django, json; django.setup(); from django.conf import settings as s; "
        "print(json.dumps({'csrf': s.CSRF_TRUSTED_ORIGINS, 'redirect': s.SECURE_SSL_REDIRECT, "
        "'proxy': list(s.SECURE_PROXY_SSL_HEADER)}))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_prod_trusts_its_own_https_origins_for_csrf():
    result = _prod_settings({"DJANGO_CSRF_TRUSTED_ORIGINS": "https://admin.example"})
    assert result["csrf"] == [
        "https://skillproof.app",
        "https://api.skillproof.app",
        "https://*.rumpty.app",
        "https://admin.example",
    ]
    assert result["proxy"] == ["HTTP_X_FORWARDED_PROTO", "https"]
    assert result["redirect"] is True


def test_ssl_redirect_can_be_turned_off():
    assert _prod_settings({"SECURE_SSL_REDIRECT": "false"})["redirect"] is False


def test_prod_refuses_to_start_without_secret_key():
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings.prod", "DJANGO_SECRET_KEY": ""}
    result = subprocess.run(
        [sys.executable, "-c", "import django; django.setup()"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY must be set" in result.stderr


def test_health_carries_cors_headers_for_the_frontend(client, settings):
    """Regression: the health middleware once answered before CorsMiddleware, so browsers
    couldn't read /health from the frontend origin."""
    settings.CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]
    response = client.get("/api/v1/health", HTTP_ORIGIN="http://localhost:5173")
    assert response.status_code == 200
    assert response["Access-Control-Allow-Origin"] == "http://localhost:5173"
