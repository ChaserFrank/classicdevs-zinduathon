"""Dependency checks for /health. Kept separate from the view so tests can patch each check."""

import redis
from django.conf import settings
from django.db import connection


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
