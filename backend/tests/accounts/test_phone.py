import pytest
from freezegun import freeze_time

from apps.accounts import phone
from apps.accounts.models import VerificationCode
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

SEND = "/api/v1/auth/phone/send-code"
VERIFY = "/api/v1/auth/phone/verify"


@pytest.mark.parametrize(
    "raw",
    ["0712345678", "0712 345 678", "+254712345678", "254712345678", "+254 712-345-678"],
)
def test_kenyan_formats_normalise_to_e164(raw):
    assert phone.normalise(raw) == "+254712345678"


def test_01_prefix_numbers():
    assert phone.normalise("0110123456") == "+254110123456"


@pytest.mark.parametrize("raw", ["", "abc", "0712", "+999123"])
def test_invalid_numbers(raw):
    with pytest.raises(phone.InvalidPhone):
        phone.normalise(raw)


def test_mask():
    assert phone.mask("+254712345678") == "+2547*****678"
    assert phone.mask("") == "***"


@pytest.fixture
def echo_codes(settings):
    settings.SMS_DEV_ECHO_CODES = True


def test_send_and_verify(auth_client, echo_codes):
    user = UserFactory(phone=None)
    client = auth_client(user)

    sent = client.post(SEND, {"phone": "0712345678"})
    assert sent.status_code == 202
    assert sent.json()["phone"] == "+254712345678"
    code = sent.json()["devCode"]
    assert len(code) == 6

    verified = client.post(VERIFY, {"code": code})
    assert verified.status_code == 200
    assert verified.json()["phoneVerified"] is True
    stored = VerificationCode.objects.get(user=user)
    assert stored.code_hash != code and code not in stored.code_hash


def test_code_not_echoed_unless_dev_setting(auth_client):
    user = UserFactory(phone="+254712345678")
    assert "devCode" not in auth_client(user).post(SEND, {}).json()


def test_code_never_logged(auth_client, echo_codes, caplog):
    user = UserFactory(phone="+254712345678")
    with caplog.at_level("DEBUG"):
        code = auth_client(user).post(SEND, {}).json()["devCode"]
    assert code not in caplog.text
    assert "+254712345678" not in caplog.text


def test_send_needs_a_phone(auth_client):
    response = auth_client(UserFactory(phone=None)).post(SEND, {})
    assert response.json()["code"] == "phone_missing"


def test_wrong_code_counts_and_locks_after_five(auth_client, echo_codes):
    user = UserFactory(phone="+254712345678")
    client = auth_client(user)
    code = client.post(SEND, {}).json()["devCode"]
    wrong = "000000" if code != "000000" else "111111"

    for _ in range(5):
        assert client.post(VERIFY, {"code": wrong}).json()["code"] == "code_invalid"
    assert VerificationCode.objects.get(user=user).attempts == 5
    response = client.post(VERIFY, {"code": code})
    assert response.status_code == 429
    assert response.json()["code"] == "code_attempts_exceeded"


def test_code_expires_after_ten_minutes(auth_client, echo_codes):
    user = UserFactory(phone="+254712345678")
    with freeze_time("2026-11-07 10:00"):
        code = auth_client(user).post(SEND, {}).json()["devCode"]
    with freeze_time("2026-11-07 10:11"):
        client = auth_client(user)
        assert client.post(VERIFY, {"code": code}).json()["code"] == "code_invalid"


def test_only_newest_code_works(auth_client, echo_codes):
    user = UserFactory(phone="+254712345678")
    client = auth_client(user)
    first = client.post(SEND, {}).json()["devCode"]
    second = client.post(SEND, {}).json()["devCode"]
    if first != second:
        assert client.post(VERIFY, {"code": first}).json()["code"] == "code_invalid"
    assert client.post(VERIFY, {"code": second}).status_code == 200


def test_changing_phone_unverifies_it(auth_client, echo_codes):
    from django.utils import timezone

    user = UserFactory(phone="+254712345678", phone_verified_at=timezone.now())
    auth_client(user).post(SEND, {"phone": "0722000111"})
    user.refresh_from_db()
    assert user.phone == "+254722000111"
    assert user.phone_verified_at is None


def test_verify_with_no_code_sent(auth_client):
    response = auth_client(UserFactory()).post(VERIFY, {"code": "123456"})
    assert response.json()["code"] == "code_invalid"


def test_code_format_validated(auth_client):
    response = auth_client(UserFactory()).post(VERIFY, {"code": "12ab"})
    assert response.json()["fields"] == {"code": ["Enter the 6-digit code."]}


def test_send_code_throttled_three_per_hour(auth_client):
    client = auth_client(UserFactory(phone="+254712345678"))
    for _ in range(3):
        assert client.post(SEND, {}).status_code == 202
    assert client.post(SEND, {}).status_code == 429


def test_sms_dry_run_status(settings):
    from apps.accounts import sms

    settings.SMS_DRY_RUN = False  # but no credentials → still dry run
    assert sms.send_sms("+254712345678", "hello") == "dry_run"
    settings.THRIVEWAVE_BASE_URL = "https://example.invalid"
    settings.THRIVEWAVE_API_KEY = "k"
    assert sms.send_sms("+254712345678", "hello") == "dry_run"
