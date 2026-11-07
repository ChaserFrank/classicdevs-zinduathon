import smtplib
from unittest import mock

import pytest
import responses
from django.core import mail
from django.utils import timezone

from apps.accounts.services import record_consents
from apps.notifications import services
from apps.notifications.models import Delivery, Kind, NotificationPreference
from apps.notifications.providers import thrivewave as tw
from tests.factories import JobSeekerFactory, RecruiterFactory

pytestmark = pytest.mark.django_db
CTX = {
    "score": 72,
    "top_skills": ["TypeScript"],
    "tips": ["Add tests to shop-app"],
    "login": "amina",
}


def seeker(email=True, sms=True, phone_verified=True):
    user = JobSeekerFactory(
        phone="+254712345678", phone_verified_at=timezone.now() if phone_verified else None
    )
    record_consents(user, {"terms": True, "email_feedback": email, "sms_feedback": sms})
    services.ensure_defaults(user)
    return user


def send(user, kind=Kind.ANALYSIS_COMPLETED, capture=None, **ctx):
    with capture(execute=True):
        return services.notify(user, kind, {**CTX, **ctx}, link_path="/u/amina")


def statuses(notification):
    return dict(notification.deliveries.values_list("channel", "status"))


def test_all_channels(django_capture_on_commit_callbacks):
    user = seeker()
    note = send(user, capture=django_capture_on_commit_callbacks)
    assert note.title == "Your Signal Score is 72"
    assert "Top skills: TypeScript" in note.body
    assert note.link_path == "/u/amina"
    assert statuses(note) == {"email": "sent", "sms": "dry_run"}
    assert mail.outbox[0].subject == "Your Signal Score is 72"
    assert "http://localhost:3000/u/amina" in mail.outbox[0].body
    html = mail.outbox[0].alternatives[0][0]
    assert "Add tests to shop-app" in html and "See your skill card" in html


def test_preferences_respected(django_capture_on_commit_callbacks):
    user = seeker()
    NotificationPreference.objects.filter(user=user, channel="email").update(enabled=False)
    note = send(user, capture=django_capture_on_commit_callbacks)
    email = note.deliveries.get(channel="email")
    assert (email.status, email.last_error) == ("skipped", "turned off in preferences")
    assert mail.outbox == []


def test_consent_respected_even_if_preference_on(django_capture_on_commit_callbacks):
    user = seeker(email=False, sms=False)
    NotificationPreference.objects.filter(user=user).update(enabled=True)
    note = send(user, capture=django_capture_on_commit_callbacks)
    assert dict(note.deliveries.values_list("channel", "last_error")) == {
        "email": "no email consent",
        "sms": "no SMS consent",
    }


def test_sms_needs_verified_phone(django_capture_on_commit_callbacks):
    note = send(seeker(phone_verified=False), capture=django_capture_on_commit_callbacks)
    assert note.deliveries.get(channel="sms").last_error == "phone not verified"


def test_transactional_email_without_feedback_consent(django_capture_on_commit_callbacks):
    note = send(
        seeker(email=False),
        Kind.ANALYSIS_FAILED,
        capture=django_capture_on_commit_callbacks,
        reason="No repos",
    )
    assert statuses(note) == {"email": "sent"}  # no SMS channel for failures


def test_inactive_user(django_capture_on_commit_callbacks):
    user = seeker()
    user.is_active = False
    user.save()
    assert set(statuses(send(user, capture=django_capture_on_commit_callbacks)).values()) == {
        "skipped"
    }


def test_defaults_from_consents():
    user = seeker(email=True, sms=False)
    matrix = services.matrix(user)
    assert matrix["recruiter_feedback"] == {"in_app": True, "email": True, "sms": False}
    assert matrix["analysis_failed"] == {"in_app": True, "email": True}
    assert "recruiter_approved" not in matrix


def test_recruiter_matrix():
    assert set(services.matrix(RecruiterFactory())) == {"recruiter_approved", "recruiter_rejected"}


@responses.activate
def test_live_sms_sent_and_logged(settings, django_capture_on_commit_callbacks):
    settings.SMS_DRY_RUN = False
    settings.THRIVEWAVE_BASE_URL, settings.THRIVEWAVE_API_KEY, settings.THRIVEWAVE_SENDER_ID = (
        "https://tw.test",
        "k",
        "S",
    )
    responses.post("https://tw.test/sms/send", json={"message_id": "tw-1"})
    note = send(seeker(), capture=django_capture_on_commit_callbacks)
    sms = note.deliveries.get(channel="sms")
    assert (sms.status, sms.provider_message_id, sms.attempts) == ("sent", "tw-1", 1)
    assert sms.provider_response["provider"] == {"message_id": "tw-1"}
    sent_body = responses.calls[0].request.body.decode()
    assert "Reply STOP to opt out" in sent_body


def test_transient_errors_retry_three_times_then_fail(django_capture_on_commit_callbacks):
    with mock.patch.object(tw, "send", side_effect=tw.ThrivewaveTransientError("HTTP 503")) as fake:
        note = send(seeker(email=False), capture=django_capture_on_commit_callbacks)
    sms = note.deliveries.get(channel="sms")
    assert fake.call_count == 3
    assert (sms.status, sms.attempts) == ("failed", 3)
    assert sms.last_error == "Attempt 3: HTTP 503"


def test_transient_then_success(django_capture_on_commit_callbacks):
    results = [
        tw.ThrivewaveTransientError("timeout"),
        tw.SmsResult(ok=True, provider_message_id="ok"),
    ]
    with mock.patch.object(tw, "send", side_effect=results):
        note = send(seeker(email=False), capture=django_capture_on_commit_callbacks)
    sms = note.deliveries.get(channel="sms")
    assert (sms.status, sms.attempts, sms.last_error) == ("sent", 2, "")


def test_permanent_rejection_is_not_retried(django_capture_on_commit_callbacks):
    rejected = tw.SmsResult(ok=False, error="HTTP 400", raw={"message": "bad number"})
    with mock.patch.object(tw, "send", return_value=rejected) as fake:
        note = send(seeker(email=False), capture=django_capture_on_commit_callbacks)
    sms = note.deliveries.get(channel="sms")
    assert fake.call_count == 1
    assert (sms.status, sms.last_error) == ("failed", "HTTP 400")


@pytest.mark.parametrize(
    ("exc", "attempts", "status"),
    [
        (smtplib.SMTPRecipientsRefused({}), 1, "failed"),
        (smtplib.SMTPServerDisconnected(), 3, "failed"),
        (ConnectionRefusedError(), 3, "failed"),
    ],
)
def test_email_errors(exc, attempts, status, django_capture_on_commit_callbacks):
    with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=exc) as fake:
        note = send(seeker(sms=False), capture=django_capture_on_commit_callbacks)
    email = note.deliveries.get(channel="email")
    assert (fake.call_count, email.status) == (attempts, status)


def test_retry_resends_identical_text(django_capture_on_commit_callbacks):
    note = send(seeker(sms=False), capture=django_capture_on_commit_callbacks)
    delivery = note.deliveries.get(channel="email")
    Delivery.objects.filter(pk=delivery.pk).update(status="failed")
    from apps.notifications.tasks import deliver

    deliver(delivery.pk)
    assert mail.outbox[0].body == mail.outbox[1].body


def test_finished_delivery_is_not_resent(django_capture_on_commit_callbacks):
    note = send(seeker(sms=False), capture=django_capture_on_commit_callbacks)
    from apps.notifications.tasks import deliver

    deliver(note.deliveries.get(channel="email").pk)
    deliver(999999)
    assert len(mail.outbox) == 1
