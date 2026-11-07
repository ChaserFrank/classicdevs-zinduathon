"""Deployment checks that run with `manage.py check --deploy` (CI enforces them)."""

from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security, deploy=True)
def check_encryption_key(app_configs, **kwargs):
    from cryptography.fernet import Fernet

    key = getattr(settings, "FIELD_ENCRYPTION_KEY", "")
    try:
        Fernet(key.encode())
    except (ValueError, TypeError):
        return [
            Error(
                "FIELD_ENCRYPTION_KEY is missing or not a valid Fernet key.",
                hint='Generate one: python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"',
                id="skillproof.E001",
            )
        ]
    return []
