import pytest
import responses
from django.core import mail
from freezegun import freeze_time

from apps.accounts.services import record_consents
from apps.analysis.models import Analysis
from apps.analysis.services import pipeline
from apps.companies import services as company_services
from apps.notifications.models import Notification
from tests.factories import JobSeekerFactory, RecruiterFactory
from tests.fixtures.github.fake import load_persona, register_persona

pytestmark = pytest.mark.django_db


def test_completed_analysis_notifies_job_seeker(django_capture_on_commit_callbacks):
    user = JobSeekerFactory()
    record_consents(user, {"terms": True, "email_feedback": True})
    analysis = Analysis.objects.create(
        github_login="amina-demo", job_seeker=user.job_seeker_profile
    )
    with (
        freeze_time("2026-11-07 12:00"),
        responses.RequestsMock(assert_all_requests_are_fired=False) as rsps,
    ):
        register_persona(rsps, load_persona("amina-demo"))
        with django_capture_on_commit_callbacks(execute=True):
            pipeline.run(analysis)
    note = Notification.objects.get(user=user)
    assert note.kind == "analysis_completed" and note.analysis == analysis
    assert note.title == f"Your Signal Score is {Analysis.objects.get(pk=analysis.pk).signal_score}"
    assert mail.outbox[0].to == [user.email]


def test_failed_analysis_notifies(django_capture_on_commit_callbacks):
    user = JobSeekerFactory()
    analysis = Analysis.objects.create(
        github_login="forks-only", job_seeker=user.job_seeker_profile
    )
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        register_persona(rsps, load_persona("forks-only"))
        with django_capture_on_commit_callbacks(execute=True):
            pipeline.run(analysis)
    note = Notification.objects.get(user=user)
    assert note.kind == "analysis_failed"
    assert "no public" in note.body.lower()


def test_admin_run_analysis_notifies_nobody():
    analysis = Analysis.objects.create(github_login="x", status="completed")
    pipeline._on_finished(analysis)
    assert not Notification.objects.exists()


def test_recruiter_approval_emails_recruiter(admin_user, django_capture_on_commit_callbacks):
    recruiter = RecruiterFactory(profile__approval_status="pending")
    with django_capture_on_commit_callbacks(execute=True):
        company_services.approve(recruiter.recruiter_profile, reviewer=admin_user, note="Welcome")
    assert Notification.objects.get(user=recruiter).kind == "recruiter_approved"
    assert mail.outbox[0].subject == "Your SkillProof recruiter account is approved"
    assert "Welcome" in mail.outbox[0].body


def test_suspension_sends_nothing(admin_user):
    company_services.suspend(RecruiterFactory().recruiter_profile, reviewer=admin_user)
    assert not Notification.objects.exists()


def test_register_creates_default_preferences(api_client):
    api_client.post(
        "/api/v1/auth/register",
        {
            "email": "new@example.com",
            "password": "correct-horse-battery",
            "role": "job_seeker",
            "fullName": "New",
            "consents": {"terms": True, "emailFeedback": True},
        },
    )
    from apps.notifications.models import NotificationPreference

    prefs = NotificationPreference.objects.filter(user__email="new@example.com")
    assert prefs.filter(channel="email", enabled=True).exists()
    assert not prefs.filter(channel="sms", enabled=True).exists()
