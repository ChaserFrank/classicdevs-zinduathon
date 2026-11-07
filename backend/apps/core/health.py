"""Dependency checks for /health. Kept separate from the view so tests can patch each check."""

import redis
from django.conf import settings
from django.db import connection
from django.utils import timezone


def check_database() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            return cursor.fetchone() == (1,)
    except Exception:
        return False


def check_redis() -> bool:
    """Ping the broker directly: if Redis is down, analyses and notifications can't be queued."""
    try:
        client = redis.Redis.from_url(
            settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2
        )
        return bool(client.ping())
    except Exception:
        return False


def report() -> tuple[dict, int]:
    """(body in camelCase, HTTP status). Shared by the view and HealthCheckMiddleware."""
    checks = {
        "database": "ok" if check_database() else "down",
        "redis": "ok" if check_redis() else "down",
    }
    healthy = all(value == "ok" for value in checks.values())
    body = {
        "status": "ok" if healthy else "degraded",
        "checks": checks,
        "version": settings.APP_VERSION,
        "commitSha": settings.GIT_COMMIT_SHA,
        "time": timezone.localtime().isoformat(),
    }
    return body, 200 if healthy else 503
