import logging

import pytest

from apps.core.logging import RequestIdFilter
from apps.core.request_context import request_id_var

pytestmark = pytest.mark.django_db
URL = "/api/v1/health"


def test_generates_request_id_when_missing(api_client):
    response = api_client.get(URL)
    assert len(response["X-Request-ID"]) == 32


def test_reuses_safe_incoming_request_id(api_client):
    response = api_client.get(URL, HTTP_X_REQUEST_ID="frontend-req-12345")
    assert response["X-Request-ID"] == "frontend-req-12345"


@pytest.mark.parametrize("bad", ["short", "has spaces in it", "x" * 129, "evil\nlog-line-123"])
def test_replaces_unsafe_incoming_request_id(api_client, bad):
    response = api_client.get(URL, HTTP_X_REQUEST_ID=bad)
    assert response["X-Request-ID"] != bad
    assert len(response["X-Request-ID"]) == 32


def test_log_filter_stamps_current_request_id():
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "msg", None, None)
    token = request_id_var.set("abc12345")
    try:
        RequestIdFilter().filter(record)
    finally:
        request_id_var.reset(token)
    assert record.request_id == "abc12345"


def test_log_filter_uses_dash_outside_requests():
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "msg", None, None)
    RequestIdFilter().filter(record)
    assert record.request_id == "-"


def test_log_filter_prefers_request_attached_to_record():
    record = logging.LogRecord("django.request", logging.WARNING, __file__, 1, "msg", None, None)
    record.request = type("Req", (), {"request_id": "from-request-1"})()
    RequestIdFilter().filter(record)
    assert record.request_id == "from-request-1"
