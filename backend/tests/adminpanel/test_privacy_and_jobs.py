import json
from datetime import timedelta

import pytest
import responses
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import User
from apps.analysis.models import Analysis, GithubCache
from apps.core.models import AuditLog
from apps.core.tasks import apply_retention
from apps.notifications.models import Delivery, Notification
from apps.notifications.services import outbound_muted
from apps.notifications.tasks import send_profile_view_digest
from apps.recruiting.models import Feedback, ProfileView
from apps.recruiting.services import feedback as feedback_service
from tests.factories import PASSWORD, GithubAccountFactory, RecruiterFactory
from tests.fixtures.github.fake import load_persona, register_persona
from tests.recruiting.helpers import make_candidate

pytestmark = pytest.mark.django_db


class TestExport:
    def test_job_seeker_export(self, auth_client):
        profile = make_candidate("ann", 70, {"Python": "strong"})
        recruiter = RecruiterFactory()
        feedback_service.send_feedback(recruiter, profile, status="interview", message="Hello")
        response = auth_client(profile.user).get("/api/v1/me/export")
        assert response.status_code == 200
        assert response["Content-Disposition"].startswith(
            'attachment; filename="skillproof-export-'
        )
        data = json.loads(response.content)
        assert data["account"]["email"] == profile.user.email
        assert data["github"]["login"] == "ann"
        assert data["analyses"][0]["signalScore"] == 70
        assert data["feedbackReceived"][0]["message"] == "Hello"
        assert (
            "access_token" not in response.content.decode()
            and "password" not in response.content.decode()
        )
        assert AuditLog.objects.filter(action="privacy.export").exists()

    def test_recruiter_export(self, auth_client, recruiter):
        feedback_service.send_feedback(
            recruiter, make_candidate("ann", 70), status="general", message="Hi"
        )
        data = json.loads(auth_client(recruiter).get("/api/v1/me/export").content)
        assert data["recruiterProfile"]["approvalStatus"] == "approved"
        assert data["feedbackSent"][0]["message"] == "Hi"


class TestDelete:
    def test_requires_password_and_deletes(self, auth_client, api_client):
        from apps.accounts.tokens import issue_tokens

        profile = make_candidate("ann", 70)
        user = profile.user
        refresh = issue_tokens(user)["refresh"]
        client = auth_client(user)
        assert client.delete("/api/v1/me", {"password": "wrong"}).status_code == 400
        assert client.delete("/api/v1/me", {"password": PASSWORD}).status_code == 204
        assert not User.objects.filter(pk=user.pk).exists()
        assert not Analysis.objects.filter(github_login="ann").exists()
        assert (
            api_client.post("/api/v1/auth/token/refresh", {"refresh": refresh}).status_code == 401
        )
        entry = AuditLog.objects.get(action="privacy.account_deleted")
        assert entry.actor is None and entry.metadata == {"role": "job_seeker"}

    def test_recruiter_feedback_kept_anonymised(self, auth_client, recruiter):
        profile = make_candidate("ann", 70)
        feedback_service.send_feedback(recruiter, profile, status="general", message="Kept")
        auth_client(recruiter).delete("/api/v1/me", {"password": PASSWORD})
        feedback = Feedback.objects.get()
        assert feedback.recruiter is None and feedback.company_name
        assert (
            auth_client(profile.user).get("/api/v1/feedback").json()["results"][0]["recruiterName"]
            == "A recruiter"
        )

    def test_github_only_account_needs_recent_sign_in(self, auth_client):
        account = GithubAccountFactory()
        user = account.user
        user.set_unusable_password()
        client = auth_client(user)  # issuing a token updates last_login…
        user.last_login = timezone.now() - timedelta(hours=1)  # …so make the sign-in old after
        user.save()
        assert client.delete("/api/v1/me", {}).status_code == 400
        user.last_login = timezone.now()
        user.save()
        assert auth_client(user).delete("/api/v1/me", {}).status_code == 204

    def test_admins_cannot_self_delete(self, auth_client, admin_user):
        assert (
            auth_client(admin_user).delete("/api/v1/me", {"password": PASSWORD}).status_code == 403
        )


def test_retention():
    user = make_candidate("ann", 70).user
    old = Notification.objects.create(
        user=user, kind="analysis_completed", title="t", body="secret body"
    )
    Notification.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=181))
    new = Notification.objects.create(user=user, kind="analysis_completed", title="t", body="keep")
    d = Delivery.objects.create(
        notification=old,
        channel="email",
        provider="smtp",
        provider_response={"render": {"text": "x"}},
    )
    Delivery.objects.filter(pk=d.pk).update(created_at=timezone.now() - timedelta(days=181))
    GithubCache.objects.create(url="a", payload={}, fetched_at=timezone.now() - timedelta(days=8))
    GithubCache.objects.create(url="b", payload={}, fetched_at=timezone.now())
    assert apply_retention() == {"notification_bodies_cleared": 1, "github_cache_deleted": 1}
    old.refresh_from_db(), new.refresh_from_db(), d.refresh_from_db()
    assert (old.body, new.body, d.provider_response) == ("", "keep", {})
    assert AuditLog.objects.filter(action="system.retention").exists()


def test_weekly_digest_only_for_viewed_cards(django_capture_on_commit_callbacks):
    viewed = make_candidate("ann", 70)
    make_candidate("ben", 50)
    r1, r2 = RecruiterFactory(), RecruiterFactory()
    for r in (r1, r1, r2):
        ProfileView.objects.create(recruiter=r, job_seeker=viewed)
    stale = ProfileView.objects.create(recruiter=RecruiterFactory(), job_seeker=viewed)
    ProfileView.objects.filter(pk=stale.pk).update(viewed_at=timezone.now() - timedelta(days=9))
    with django_capture_on_commit_callbacks(execute=True):
        assert send_profile_view_digest() == 1
    note = Notification.objects.get(kind="profile_viewed_digest")
    assert note.user == viewed.user and note.title == "2 recruiters viewed your card this week"


def test_beat_schedule_configured(settings):
    schedule = settings.CELERY_BEAT_SCHEDULE
    assert schedule["weekly-profile-view-digest"]["schedule"].day_of_week == {1}
    assert schedule["weekly-profile-view-digest"]["schedule"].hour == {8}
    assert settings.CELERY_TIMEZONE == "Africa/Nairobi"


def test_outbound_muted_skips_email_and_sms():
    from apps.notifications.services import notify

    user = make_candidate("ann", 70).user
    with outbound_muted():
        note = notify(user, "analysis_failed", {"reason": "x", "login": "ann"})
    assert set(note.deliveries.values_list("status", "last_error")) == {
        ("skipped", "outbound muted (demo data)")
    }


def test_seed_demo_is_idempotent(capsys):
    call_command("seed_demo")
    first = capsys.readouterr().out
    assert "Demo data ready" in first and "grace@savanna.demo" in first
    counts = (
        User.objects.count(),
        Analysis.objects.count(),
        Feedback.objects.count(),
        ProfileView.objects.count(),
    )
    assert Analysis.objects.filter(status="completed").count() == 6
    call_command("seed_demo")
    assert (
        User.objects.count(),
        Analysis.objects.count(),
        Feedback.objects.count(),
        ProfileView.objects.count(),
    ) == counts
    assert not Delivery.objects.exclude(status="skipped").exists()
    assert (
        User.objects.get(email="pending@mawingu.demo").recruiter_profile.approval_status
        == "pending"
    )


def test_warm_demo(capsys):
    from django.core.management.base import CommandError

    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        register_persona(rsps, load_persona("brian-demo"))
        register_persona(rsps, load_persona("forks-only"))
        call_command("warm_demo", "--logins", "brian-demo")
        assert "brian-demo: Signal Score" in capsys.readouterr().out
        call_command("warm_demo", "--logins", "brian-demo")
        assert "fresh card exists" in capsys.readouterr().out
        with pytest.raises(CommandError, match="1 analysis"):
            call_command("warm_demo", "--logins", "forks-only")
