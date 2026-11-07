"""Local development: debug on, tasks run inline, email goes to Mailpit, SMS is dry-run."""

from .base import *
from .env import env_bool, env_int, env_str

DEBUG = env_bool("DJANGO_DEBUG", True)
# A throwaway key so `make dev` works before anyone creates a .env. Never used outside dev.
SECRET_KEY = SECRET_KEY or "dev-only-insecure-key-change-me-0123456789-abcdefghijklmnop"
ALLOWED_HOSTS = [*ALLOWED_HOSTS, "0.0.0.0", "web"]  # noqa: S104 - docker-compose service name

CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", True)

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env_str("EMAIL_HOST", "localhost")
EMAIL_PORT = env_int("EMAIL_PORT", 1025)
DEFAULT_FROM_EMAIL = env_str("DEFAULT_FROM_EMAIL", "SkillProof <no-reply@skillproof.app>")

LOGGING["handlers"]["console"]["formatter"] = env_str("LOG_FORMAT", "text")

# Serve static files from app directories without running collectstatic first.
WHITENOISE_AUTOREFRESH = True
WHITENOISE_USE_FINDERS = True
