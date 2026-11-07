"""Symmetric encryption for secrets we must store (GitHub access tokens).

Why Fernet: authenticated encryption (tampering is detected), a single key from the environment,
and part of `cryptography`, which is widely audited. If the database leaks without the key, the
tokens are useless.
"""

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


@lru_cache(maxsize=4)
def _fernet(key: str) -> Fernet:
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY is not a valid Fernet key.") from exc


def get_fernet() -> Fernet:
    key = settings.FIELD_ENCRYPTION_KEY
    if not key:
        raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY must be set to store GitHub tokens.")
    return _fernet(key)


def encrypt(value: str) -> str:
    return get_fernet().encrypt(value.encode()).decode() if value else ""


def decrypt(value: str) -> str:
    """Return the plaintext, or "" if the value is empty or was encrypted with another key."""
    if not value:
        return ""
    try:
        return get_fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        return ""


def derive_dev_key(secret: str) -> str:
    """Dev-only convenience: a stable Fernet key derived from SECRET_KEY, so `make dev` works
    without generating one. Production must set FIELD_ENCRYPTION_KEY explicitly (deploy check)."""
    return base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()).decode()
