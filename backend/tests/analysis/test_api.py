from datetime import timedelta

import pytest
import responses
from django.utils import timezone
from freezegun import freeze_time

from apps.analysis.models import Analysis, ClaimedSkill
from apps.core.models import AuditLog
from tests.factories import GithubAccountFactory, JobSeekerFactory, RecruiterFactory
from tests.fixtures.github.fake import load_persona, register_persona

pytestmark = pytest.mark.django_db
URL = "/api/v1/analyses"


@pytest.fixture
def seeker_with_github():
    account = GithubAccountFactory(login="amina-dev")
    return account.user


def post(client, body=None, run=None, capture=None):
    """POST /analyses with GitHub mocked; on_commit callbacks (the Celery task) executed."""
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        if run:
            register_persona(rsps, load_persona(run))
        with capture(execute=True):
            return client.post(URL, body or {})


class TestStart:
    @freeze_time("2026-11-07 12:00")
    def test_job_seeker_runs_own_analysis(
        self, auth_client, seeker_with_github, django_capture_on_commit_callbacks
    ):
        client = auth_client(seeker_with_github)
        response = post(client, run="amina-dev", capture=django_capture_on_commit_callbacks)

        assert response.status_code == 202
        assert set(response.json()) == {"id", "status"}
        analysis = Analysis.objects.get(public_id=response.json()["id"])
        assert analysis.github_login == "amina-dev"
        assert analysis.job_seeker == seeker_with_github.job_seeker_profile
        assert analysis.status == "completed"  # Celery runs eagerly in tests
        assert AuditLog.objects.filter(action="analysis.run").exists()

        detail = client.get(f"{URL}/{analysis.public_id}").json()
        assert detail["status"] == "completed"
        assert detail["card"]["username"] == "amina-dev"
        assert detail["card"]["profile"]["verifiedOwner"] is True
        assert detail["tips"]

    def test_requires_verified_email(self, auth_client):
        account = GithubAccountFactory(user__email_verified_at=None)
        response = auth_client(account.user).post(URL, {})
        assert response.status_code == 403
        assert response.json()["code"] == "email_not_verified"

    def test_requires_linked_github(self, auth_client, job_seeker):
        response = auth_client(job_seeker).post(URL, {})
        assert response.json()["code"] == "github_not_linked"

    def test_job_seeker_cannot_choose_another_login(
        self, auth_client, seeker_with_github, django_capture_on_commit_callbacks
    ):
        response = post(
            auth_client(seeker_with_github),
            {"githubLogin": "torvalds"},
            capture=django_capture_on_commit_callbacks,
        )
        assert Analysis.objects.get(public_id=response.json()["id"]).github_login == "amina-dev"

    def test_recruiters_cannot_run_analyses(self, auth_client, recruiter):
        assert auth_client(recruiter).post(URL, {}).json()["code"] == "permission_denied"

    def test_anonymous(self, api_client):
        assert api_client.post(URL, {}).status_code == 401

    def test_admin_needs_login(self, auth_client, admin_user):
        response = auth_client(admin_user).post(URL, {})
        assert response.status_code == 400

    def test_admin_login_validated(self, auth_client, admin_user):
        response = auth_client(admin_user).post(URL, {"githubLogin": "bad login!"})
        assert "githubLogin" in response.json()["fields"]

    @freeze_time("2026-11-07 12:00")
    def test_admin_runs_any_login(
        self, auth_client, admin_user, django_capture_on_commit_callbacks
    ):
        response = post(
            auth_client(admin_user),
            {"githubLogin": "Brian-Learns"},
            run="brian-learns",
            capture=django_capture_on_commit_callbacks,
        )
        analysis = Analysis.objects.get(public_id=response.json()["id"])
        assert analysis.github_login == "brian-learns"
        assert analysis.job_seeker is None
        assert analysis.status == "completed"

    def test_one_running_analysis_per_login(self, auth_client, seeker_with_github):
        Analysis.objects.create(github_login="amina-dev", status="running")
        response = auth_client(seeker_with_github).post(URL, {})
        assert response.status_code == 409
        assert response.json()["code"] == "analysis_in_progress"

    def test_stale_running_analysis_is_expired(
        self, auth_client, seeker_with_github, django_capture_on_commit_callbacks
    ):
        stale = Analysis.objects.create(github_login="amina-dev", status="running")
        Analysis.objects.filter(pk=stale.pk).update(
            updated_at=timezone.now() - timedelta(minutes=16)
        )
        assert (
            post(
                auth_client(seeker_with_github), capture=django_capture_on_commit_callbacks
            ).status_code
            == 202
        )
        stale.refresh_from_db()
        assert (stale.status, stale.error_code) == ("failed", "timeout")

    def test_database_blocks_two_active_analyses(self):
        from django.db import IntegrityError

        Analysis.objects.create(github_login="x", status="queued")
        with pytest.raises(IntegrityError):
            Analysis.objects.create(github_login="x", status="running")

    def _completed(self, user, hours_ago=1):
        return Analysis.objects.create(
            github_login="amina-dev",
            job_seeker=user.job_seeker_profile,
            status="completed",
            signal_score=50,
            completed_at=timezone.now() - timedelta(hours=hours_ago),
        )

    def test_recent_result_is_reused(self, auth_client, seeker_with_github):
        recent = self._completed(seeker_with_github)
        response = auth_client(seeker_with_github).post(URL, {})
        assert response.status_code == 200
        assert response.json()["id"] == str(recent.public_id)
        assert response.json()["card"]["signalScore"] == 50

    def test_force_runs_again(
        self, auth_client, seeker_with_github, django_capture_on_commit_callbacks
    ):
        self._completed(seeker_with_github)
        assert (
            post(
                auth_client(seeker_with_github),
                {"force": True},
                capture=django_capture_on_commit_callbacks,
            ).status_code
            == 202
        )

    def test_old_result_is_not_reused(
        self, auth_client, seeker_with_github, django_capture_on_commit_callbacks
    ):
        self._completed(seeker_with_github, hours_ago=25)
        assert (
            post(
                auth_client(seeker_with_github), capture=django_capture_on_commit_callbacks
            ).status_code
            == 202
        )

    def test_changed_claims_run_again(
        self, auth_client, seeker_with_github, django_capture_on_commit_callbacks
    ):
        self._completed(seeker_with_github)
        ClaimedSkill.objects.create(job_seeker=seeker_with_github.job_seeker_profile, raw_text="Go")
        assert (
            post(
                auth_client(seeker_with_github), capture=django_capture_on_commit_callbacks
            ).status_code
            == 202
        )

    def test_throttled_at_ten_per_hour(self, auth_client, seeker_with_github):
        self._completed(seeker_with_github)  # reuse path: cheap, but still counted
        client = auth_client(seeker_with_github)
        for _ in range(10):
            assert client.post(URL, {}).status_code == 200
        assert client.post(URL, {}).status_code == 429


class TestReadAnalyses:
    def test_others_cannot_see_an_analysis(
        self, auth_client, seeker_with_github, job_seeker, recruiter, admin_user
    ):
        analysis = Analysis.objects.create(
            github_login="amina-dev", job_seeker=seeker_with_github.job_seeker_profile
        )
        url = f"{URL}/{analysis.public_id}"
        assert auth_client(job_seeker).get(url).status_code == 404
        assert auth_client(recruiter).get(url).status_code == 404
        body = auth_client(admin_user).get(url).json()
        assert body["status"] == "queued" and body["card"] is None and body["tips"] == []

    def test_failed_analysis_shows_error(self, auth_client, seeker_with_github):
        analysis = Analysis.objects.create(
            github_login="amina-dev",
            job_seeker=seeker_with_github.job_seeker_profile,
            status="failed",
            error_code="no_public_repos",
            error_message="No repos",
        )
        body = auth_client(seeker_with_github).get(f"{URL}/{analysis.public_id}").json()
        assert (body["errorCode"], body["errorMessage"]) == ("no_public_repos", "No repos")

    def test_unknown_id(self, auth_client, job_seeker):
        assert (
            auth_client(job_seeker).get(f"{URL}/00000000-0000-0000-0000-000000000000").status_code
            == 404
        )

    def test_history_is_own_and_paginated(self, auth_client, seeker_with_github, job_seeker):
        profile = seeker_with_github.job_seeker_profile
        for score in (40, 55, 70):
            a = Analysis.objects.create(
                github_login="amina-dev",
                job_seeker=profile,
                status="completed",
                signal_score=score,
                completed_at=timezone.now(),
            )
            a.subscores.create(key="quality", value=score // 5, reason="r")
        Analysis.objects.create(
            github_login="other", job_seeker=job_seeker.job_seeker_profile, status="failed"
        )

        body = auth_client(seeker_with_github).get(URL, {"pageSize": 2}).json()
        assert body["count"] == 3
        assert len(body["results"]) == 2
        assert body["results"][0]["signalScore"] == 70
        assert body["results"][0]["subScores"] == {"quality": 14}

    def test_admin_filters(self, auth_client, admin_user):
        Analysis.objects.create(github_login="a", status="failed")
        Analysis.objects.create(github_login="b", status="failed")
        client = auth_client(admin_user)
        assert client.get(URL).json()["count"] == 2
        assert client.get(URL, {"githubLogin": "A"}).json()["count"] == 1
        assert client.get(URL, {"status": "completed"}).json()["count"] == 0

    def test_recruiters_have_no_history(self, auth_client, recruiter):
        assert auth_client(recruiter).get(URL).status_code == 403


class TestCards:
    def test_latest_completed_card_is_public(self, api_client):
        Analysis.objects.create(
            github_login="dev1",
            status="completed",
            signal_score=40,
            completed_at=timezone.now() - timedelta(days=2),
        )
        Analysis.objects.create(
            github_login="dev1", status="completed", signal_score=60, completed_at=timezone.now()
        )
        Analysis.objects.create(github_login="dev1", status="failed")
        assert api_client.get("/api/v1/cards/DEV1").json()["signalScore"] == 60

    def test_job_seeker_card_preferred_over_admin_run(self, api_client):
        profile = JobSeekerFactory().job_seeker_profile
        Analysis.objects.create(
            github_login="dev1",
            status="completed",
            signal_score=30,
            job_seeker=profile,
            completed_at=timezone.now() - timedelta(days=1),
        )
        Analysis.objects.create(
            github_login="dev1", status="completed", signal_score=90, completed_at=timezone.now()
        )
        assert api_client.get("/api/v1/cards/dev1").json()["signalScore"] == 30

    def test_no_card(self, api_client):
        response = api_client.get("/api/v1/cards/nobody")
        assert response.status_code == 404
        assert response.json()["code"] == "not_found"

    def test_recruiter_can_view_with_token(self, auth_client):
        Analysis.objects.create(
            github_login="dev1", status="completed", signal_score=1, completed_at=timezone.now()
        )
        assert auth_client(RecruiterFactory()).get("/api/v1/cards/dev1").status_code == 200


class TestClaimedSkills:
    URL = "/api/v1/me/claimed-skills"

    def test_replace_matches_aliases_and_dedupes(self, auth_client, job_seeker):
        response = auth_client(job_seeker).put(
            self.URL, {"skills": ["ReactJS", " django ", "react.js", "Kubernetes", "Django"]}
        )
        assert response.status_code == 200
        rows = response.json()["skills"]
        assert [(r["rawText"], r["skill"] and r["skill"]["name"], r["position"]) for r in rows] == [
            ("ReactJS", "React", 0),
            ("django", "Django", 1),
            ("react.js", "React", 2),
            ("Kubernetes", None, 3),
        ]

    def test_unchanged_entries_keep_their_rows(self, auth_client, job_seeker):
        client = auth_client(job_seeker)
        client.put(self.URL, {"skills": ["Go", "Rust"]})
        go_id = ClaimedSkill.objects.get(raw_text="Go").pk
        client.put(self.URL, {"skills": ["Python", "go"]})
        assert ClaimedSkill.objects.get(raw_text="go").pk == go_id
        assert not ClaimedSkill.objects.filter(raw_text="Rust").exists()
        assert [r["rawText"] for r in client.get(self.URL).json()["skills"]] == ["Python", "go"]

    def test_max_twelve(self, auth_client, job_seeker):
        response = auth_client(job_seeker).put(self.URL, {"skills": [f"s{i}" for i in range(13)]})
        assert response.status_code == 400

    def test_only_job_seekers(self, auth_client, recruiter):
        assert auth_client(recruiter).get(self.URL).status_code == 403


class TestSkillCatalogue:
    def test_search_by_alias(self, api_client):
        names = [
            s["name"] for s in api_client.get("/api/v1/skills", {"search": "js"}).json()["results"]
        ]
        assert "JavaScript" in names and "Next.js" in names

    def test_filter_by_category(self, api_client):
        body = api_client.get("/api/v1/skills", {"category": "practice", "pageSize": 100}).json()
        assert {s["name"] for s in body["results"]} == {
            "Testing",
            "CI/CD",
            "Data analysis",
            "Machine learning",
        }

    def test_seeded_catalogue(self, api_client):
        assert api_client.get("/api/v1/skills").json()["count"] == 40
