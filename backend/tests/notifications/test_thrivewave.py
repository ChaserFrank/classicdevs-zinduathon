import pytest
import requests
import responses

from apps.notifications.providers import thrivewave as tw

BASE = "https://sms.thrivewave.test"


def client(**kwargs):
    return tw.ThrivewaveClient(BASE, "key-123", "SKILLPROOF", **kwargs)


def test_placeholder_payload():
    headers, body = client(username="sp").build_payload("+254712345678", "Hi")
    assert headers["Authorization"] == "Bearer key-123"
    assert body == {
        "sender_id": "SKILLPROOF",
        "phone": "254712345678",
        "message": "Hi",
        "username": "sp",
    }


@pytest.mark.parametrize(
    ("status", "body", "ok", "msg_id"),
    [
        (200, {"message_id": "m1"}, True, "m1"),
        (201, {"data": 1, "id": 7}, True, "7"),
        (200, {"success": False, "message": "Bad sender"}, False, ""),
        (200, {"status": "failed"}, False, ""),
        (200, "OK", True, ""),
        (400, {"error": "invalid phone"}, False, ""),
    ],
)
def test_parse_response(status, body, ok, msg_id):
    result = client().parse_response(status, body)
    assert (result.ok, result.provider_message_id) == (ok, msg_id)


@responses.activate
def test_send_success_uses_configured_path():
    responses.post(f"{BASE}/v1/send", json={"messageId": "abc"})
    result = client(sms_path="v1/send").send_sms("+254712345678", "Hello")
    assert result.ok and result.provider_message_id == "abc"
    assert responses.calls[0].request.headers["Authorization"] == "Bearer key-123"


@responses.activate
def test_4xx_is_permanent_failure_not_exception():
    responses.post(f"{BASE}/sms/send", status=422, json={"message": "invalid phone"})
    result = client().send_sms("+254700000000", "x")
    assert not result.ok and result.error == "HTTP 422"


@responses.activate
def test_5xx_is_transient():
    responses.post(f"{BASE}/sms/send", status=503)
    with pytest.raises(tw.ThrivewaveTransientError):
        client().send_sms("+254712345678", "x")


@responses.activate
def test_timeout_is_transient():
    responses.post(f"{BASE}/sms/send", body=requests.Timeout())
    with pytest.raises(tw.ThrivewaveTransientError):
        client().send_sms("+254712345678", "x")


@responses.activate
def test_dry_run_never_touches_network(settings, caplog):
    settings.SMS_DRY_RUN = True
    settings.THRIVEWAVE_BASE_URL, settings.THRIVEWAVE_API_KEY, settings.THRIVEWAVE_SENDER_ID = (
        BASE,
        "k",
        "S",
    )
    with caplog.at_level("INFO"):
        result = tw.send("+254712345678", "secret 123456")
    assert result.dry_run and result.ok
    assert len(responses.calls) == 0
    assert "123456" not in caplog.text and "+254712345678" not in caplog.text


def test_missing_credentials_force_dry_run(settings):
    settings.SMS_DRY_RUN = False
    settings.THRIVEWAVE_API_KEY = ""
    assert tw.send("+254712345678", "x").dry_run


@responses.activate
def test_live_send_when_configured(settings):
    settings.SMS_DRY_RUN = False
    settings.THRIVEWAVE_BASE_URL, settings.THRIVEWAVE_API_KEY, settings.THRIVEWAVE_SENDER_ID = (
        BASE,
        "k",
        "S",
    )
    settings.THRIVEWAVE_SMS_PATH = "/sms/send"
    responses.post(f"{BASE}/sms/send", json={"id": "x1"})
    assert tw.send("+254712345678", "x").provider_message_id == "x1"
