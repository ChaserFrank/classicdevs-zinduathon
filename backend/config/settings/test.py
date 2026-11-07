"""Test settings: the same PostgreSQL engine as production (no SQLite), fast password hashing,
in-memory email and cache, tasks inline. Redis is still used by the health check tests."""

from .base import *

SECRET_KEY = "test-secret-key-not-for-production-0123456789-abcdefghijklmnop"  # noqa: S105
DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # speed; tests only
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CELERY_TASK_ALWAYS_EAGER = True

LOGGING["root"]["level"] = "WARNING"
LOGGING["loggers"]["django"]["level"] = "WARNING"

# Serve static files from app directories without running collectstatic first.
WHITENOISE_AUTOREFRESH = True
WHITENOISE_USE_FINDERS = True

FIELD_ENCRYPTION_KEY = "kY2ZpT0m2C7Qw3l3cX1H4b7mJ6eYw0b8n2nZbqk7x0A="  # test-only key
GITHUB_OAUTH_CLIENT_ID = "test-client-id"
GITHUB_OAUTH_CLIENT_SECRET = "test-client-secret"  # noqa: S105
GITHUB_OAUTH_REDIRECT_URI = "http://localhost:3000/auth/github/callback"
SMS_DRY_RUN = True
