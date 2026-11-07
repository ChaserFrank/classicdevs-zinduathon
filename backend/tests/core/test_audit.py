import pytest
from rest_framework.test import APIRequestFactory

from apps.core import audit
from apps.core.models import AuditLog

pytestmark = pytest.mark.django_db


def test_record_captures_actor_target_ip_and_agent(user):
    request = APIRequestFactory().get(
        "/", HTTP_X_FORWARDED_FOR="41.90.1.2, 10.0.0.1", HTTP_USER_AGENT="pytest"
    )

    entry = audit.record(
        "auth.sign_in", actor=user, target=user, request=request, metadata={"m": 1}
    )

    assert entry.actor == user
    assert entry.target_type == "accounts.user"
    assert entry.target_id == str(user.public_id)
    assert entry.ip_address == "41.90.1.2"
    assert entry.user_agent == "pytest"
    assert entry.metadata == {"m": 1}


def test_record_without_request_or_actor():
    entry = audit.record("system.retention_run")
    assert entry.actor is None
    assert entry.ip_address is None


def test_anonymous_actor_is_stored_as_null():
    from django.contrib.auth.models import AnonymousUser

    request = APIRequestFactory().get("/", REMOTE_ADDR="127.0.0.1")
    entry = audit.record("auth.sign_in_failed", actor=AnonymousUser(), request=request)
    assert entry.actor is None
    assert entry.ip_address == "127.0.0.1"


def test_audit_entries_are_append_only(user):
    entry = audit.record("x", actor=user)
    entry.action = "tampered"
    with pytest.raises(ValueError, match="append-only"):
        entry.save()
    assert AuditLog.objects.get(pk=entry.pk).action == "x"


def test_audit_entry_survives_actor_deletion(user):
    entry = audit.record("x", actor=user)
    user.delete()
    entry.refresh_from_db()
    assert entry.actor is None
    assert str(entry).endswith("x :")
