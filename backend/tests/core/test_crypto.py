import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import SystemCheckError

from apps.core import crypto


def test_round_trip():
    secret = crypto.encrypt("gho_abc")
    assert secret != "gho_abc"
    assert crypto.decrypt(secret) == "gho_abc"


def test_empty_values():
    assert crypto.encrypt("") == ""
    assert crypto.decrypt("") == ""


def test_value_from_other_key_decrypts_to_empty(settings):
    secret = crypto.encrypt("gho_abc")
    settings.FIELD_ENCRYPTION_KEY = crypto.derive_dev_key("another secret")
    assert crypto.decrypt(secret) == ""


def test_missing_key(settings):
    settings.FIELD_ENCRYPTION_KEY = ""
    with pytest.raises(ImproperlyConfigured):
        crypto.encrypt("x")


def test_invalid_key(settings):
    settings.FIELD_ENCRYPTION_KEY = "not-a-key"
    with pytest.raises(ImproperlyConfigured):
        crypto.encrypt("x")


def test_derived_dev_key_is_stable_and_valid():
    key = crypto.derive_dev_key("s")
    assert key == crypto.derive_dev_key("s")
    from cryptography.fernet import Fernet

    Fernet(key.encode())


def test_deploy_check_flags_missing_key(settings):
    settings.FIELD_ENCRYPTION_KEY = ""
    with pytest.raises(SystemCheckError, match=r"skillproof\.E001"):
        call_command("check", "--deploy", "--tag", "security", "--fail-level", "ERROR")
