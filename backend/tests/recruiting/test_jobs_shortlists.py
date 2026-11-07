from datetime import timedelta

import pytest
from django.utils import timezone

from apps.recruiting.models import Feedback, JobPosting, ProfileView, ShortlistEntry
from apps.recruiting.services import feedback as feedback_service
from tests.factories import JobSeekerFactory, RecruiterFactory
from tests.recruiting.helpers import make_candidate

pytestmark = pytest.mark.django_db

JOB = {
    "title": "Junior backend developer",
    "status": "open",
    "remotePolicy": "hybrid",
    "requiredSkills": [
        {"skill": "Python", "minimumLabel": "moderate", "weight": 3},
        {"skill": "drf", "minimumLabel": "emerging", "weight": 2},
        {"skill": "Docker", "minimumLabel": "moderate", "weight": 1},
    ],
}


def create_job(client, **overrides):
    return client.post("/api/v1/jobs", {**JOB, **overrides}).json()


class TestJobs:
    def test_create_resolves_aliases(self, auth_client, recruiter):
        job = create_job(auth_client(recruiter))
        assert job["company"] == recruiter.recruiter_profile.company.name
        assert job["requiredSkills"] == [
            {"skill": "Python", "minimumLabel": "moderate", "weight": 3},
            {"skill": "Django REST Framework", "minimumLabel": "emerging", "weight": 2},
            {"skill": "Docker", "minimumLabel": "moderate", "weight": 1},
        ]

    def test_create_validation(self, auth_client, recruiter, admin_user):
        client = auth_client(recruiter)
        bad = client.post("/api/v1/jobs", {**JOB, "requiredSkills": [{"skill": "COBOL"}]})
        assert bad.json()["fields"]["requiredSkills"] == ["Unknown skill: COBOL"]
        weight = client.post(
            "/api/v1/jobs", {**JOB, "requiredSkills": [{"skill": "Go", "weight": 5}]}
        )
        assert weight.status_code == 400
        assert auth_client(admin_user).post("/api/v1/jobs", JOB).json()["fields"]["companyId"]

    def test_admin_creates_for_company(self, auth_client, admin_user, recruiter):
        company = recruiter.recruiter_profile.company
        job = create_job(auth_client(admin_user), companyId=str(company.public_id))
        assert job["company"] == company.name

    def test_who_can_create(self, auth_client, job_seeker):
        assert auth_client(job_seeker).post("/api/v1/jobs", JOB).status_code == 403
        pending = RecruiterFactory(profile__approval_status="pending")
        assert (
            auth_client(pending).post("/api/v1/jobs", JOB).json()["code"]
            == "recruiter_not_approved"
        )

    def test_listing_by_role(self, auth_client, recruiter, admin_user, job_seeker):
        create_job(auth_client(recruiter))
        create_job(auth_client(recruiter), status="draft", title="Draft role")
        other = RecruiterFactory()
        create_job(auth_client(other), title="Elsewhere")
        assert auth_client(recruiter).get("/api/v1/jobs").json()["count"] == 2
        assert auth_client(admin_user).get("/api/v1/jobs").json()["count"] == 3
        seeker_titles = {
            j["title"] for j in auth_client(job_seeker).get("/api/v1/jobs").json()["results"]
        }
        assert seeker_titles == {"Junior backend developer", "Elsewhere"}
        assert auth_client(recruiter).get("/api/v1/jobs", {"status": "draft"}).json()["count"] == 1

    def test_detail_edit_delete_permissions(self, auth_client, recruiter, job_seeker):
        job = create_job(auth_client(recruiter), status="draft")
        url = f"/api/v1/jobs/{job['id']}"
        colleague = RecruiterFactory(profile__company=recruiter.recruiter_profile.company)
        stranger = RecruiterFactory()
        assert auth_client(colleague).get(url).status_code == 200  # same company can read
        assert auth_client(colleague).patch(url, {"title": "x"}).status_code == 404  # but not edit
        assert auth_client(stranger).get(url).status_code == 404
        assert auth_client(job_seeker).get(url).status_code == 404  # drafts are hidden
        edited = (
            auth_client(recruiter)
            .patch(url, {"status": "open", "requiredSkills": [{"skill": "Go"}]})
            .json()
        )
        assert edited["status"] == "open" and [s["skill"] for s in edited["requiredSkills"]] == [
            "Go"
        ]
        assert auth_client(job_seeker).get(url).status_code == 200
        assert auth_client(recruiter).delete(url).status_code == 204
        assert not JobPosting.objects.exists()

    def test_matches_ranked(self, auth_client, recruiter):
        job = create_job(auth_client(recruiter))
        make_candidate(
            "full",
            50,
            {"Python": "strong", "Django REST Framework": "moderate", "Docker": "moderate"},
        )
        make_candidate("half", 90, {"Python": "emerging", "Django REST Framework": "emerging"})
        make_candidate("none", 99, {"Go": "strong"})
        make_candidate("hidden", 99, {"Python": "strong"}, visible=False)
        body = auth_client(recruiter).get(f"/api/v1/jobs/{job['id']}/matches").json()
        assert [(c["githubLogin"], c["match"]["score"]) for c in body["results"]] == [
            ("full", 100),
            ("half", 58),
        ]
        assert body["results"][1]["match"] == {
            "score": 58,
            "met": ["Django REST Framework"],
            "partial": ["Python"],
            "missing": ["Docker"],
        }
        filtered = (
            auth_client(recruiter).get(f"/api/v1/jobs/{job['id']}/matches", {"minMatch": 60}).json()
        )
        assert filtered["count"] == 1

    def test_match_me(self, auth_client, recruiter):
        job = create_job(auth_client(recruiter))
        seeker = make_candidate("me", 60, {"Python": "moderate"}).user
        assert auth_client(seeker).get(f"/api/v1/jobs/{job['id']}/match/me").json() == {
            "score": 50,
            "met": ["Python"],
            "partial": [],
            "missing": ["Django REST Framework", "Docker"],
        }
        fresh = JobSeekerFactory()
        assert auth_client(fresh).get(f"/api/v1/jobs/{job['id']}/match/me").json()["score"] == 0
        assert auth_client(recruiter).get(f"/api/v1/jobs/{job['id']}/match/me").status_code == 403


class TestShortlists:
    def test_create_list_duplicate(self, auth_client, recruiter):
        make_candidate("ann", 70)
        client = auth_client(recruiter)
        job = create_job(client)
        entry = client.post(
            "/api/v1/shortlists", {"githubLogin": "ann", "note": "strong tests"}
        ).json()
        assert entry["stage"] == "saved" and entry["candidate"]["githubLogin"] == "ann"
        assert (
            client.post("/api/v1/shortlists", {"githubLogin": "ann"}).json()["code"]
            == "already_shortlisted"
        )
        assert (
            client.post(
                "/api/v1/shortlists", {"githubLogin": "ann", "jobPostingId": job["id"]}
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/api/v1/shortlists", {"githubLogin": "ann", "jobPostingId": job["id"]}
            ).status_code
            == 409
        )
        assert client.get("/api/v1/shortlists").json()["count"] == 2
        assert client.get("/api/v1/shortlists", {"jobPostingId": job["id"]}).json()["count"] == 1
        assert client.post("/api/v1/shortlists", {"githubLogin": "nobody"}).status_code == 404

    def test_notify_on_create(self, auth_client, recruiter):
        seeker = make_candidate("ann", 70).user
        auth_client(recruiter).post(
            "/api/v1/shortlists", {"githubLogin": "ann", "notifyCandidate": True}
        )
        note = seeker.notifications.get()
        assert note.kind == "shortlisted"
        assert "moved you to Shortlisted" in note.body

    def test_move_to_interview_with_feedback(self, auth_client, recruiter):
        seeker = make_candidate("ann", 70).user
        client = auth_client(recruiter)
        entry = client.post("/api/v1/shortlists", {"githubLogin": "ann"}).json()
        response = client.patch(
            f"/api/v1/shortlists/{entry['id']}",
            {
                "stage": "interview",
                "notifyCandidate": True,
                "feedbackMessage": "Let's talk on Thursday.",
            },
        )
        assert response.json()["stage"] == "interview"
        assert Feedback.objects.get().status == "interview"
        assert set(seeker.notifications.values_list("kind", flat=True)) == {
            "shortlisted",
            "recruiter_feedback",
        }

    def test_feedback_message_validated(self, auth_client, recruiter):
        make_candidate("ann", 70)
        client = auth_client(recruiter)
        entry = client.post("/api/v1/shortlists", {"githubLogin": "ann"}).json()
        response = client.patch(
            f"/api/v1/shortlists/{entry['id']}", {"feedbackMessage": "http://x.y"}
        )
        assert "feedbackMessage" in response.json()["fields"]

    def test_entries_are_private(self, auth_client, recruiter):
        make_candidate("ann", 70)
        entry = auth_client(recruiter).post("/api/v1/shortlists", {"githubLogin": "ann"}).json()
        other = auth_client(RecruiterFactory())
        assert (
            other.patch(f"/api/v1/shortlists/{entry['id']}", {"stage": "offer"}).status_code == 404
        )
        assert other.get("/api/v1/shortlists").json()["count"] == 0
        assert auth_client(recruiter).delete(f"/api/v1/shortlists/{entry['id']}").status_code == 204
        assert not ShortlistEntry.objects.exists()

    def test_job_seekers_cannot_shortlist(self, auth_client, job_seeker):
        assert auth_client(job_seeker).get("/api/v1/shortlists").status_code == 403


class TestFeedbackInbox:
    def setup_feedback(self, recruiter):
        seeker = make_candidate("ann", 70)
        sent = feedback_service.send_feedback(
            recruiter, seeker, status="shortlisted", message="Nice work"
        )
        held = feedback_service.send_feedback(
            recruiter, seeker, status="general", message="Code is trash"
        )
        return seeker.user, sent, held

    def test_job_seeker_sees_only_sent_messages(self, auth_client, recruiter):
        user, sent, _ = self.setup_feedback(recruiter)
        body = auth_client(user).get("/api/v1/feedback").json()
        assert [f["id"] for f in body["results"]] == [str(sent.public_id)]
        item = body["results"][0]
        assert item["recruiterName"] == recruiter.full_name and item["candidate"] is None
        read = auth_client(user).post(f"/api/v1/feedback/{sent.public_id}/read").json()
        assert read["readAt"] is not None

    def test_recruiter_sees_sent_including_held(self, auth_client, recruiter):
        self.setup_feedback(recruiter)
        results = auth_client(recruiter).get("/api/v1/feedback").json()["results"]
        assert sorted(f["moderation"] for f in results) == ["held", "sent"]
        assert results[0]["candidate"] == {"githubLogin": "ann", "name": "Ann"}

    def test_held_cannot_be_read_and_admin_403(self, auth_client, recruiter, admin_user):
        user, _, held = self.setup_feedback(recruiter)
        assert auth_client(user).post(f"/api/v1/feedback/{held.public_id}/read").status_code == 404
        assert auth_client(admin_user).get("/api/v1/feedback").status_code == 403

    def test_release_and_reject(self, recruiter, admin_user):
        user, sent, held = self.setup_feedback(recruiter)
        feedback_service.release(held, admin=admin_user)
        held.refresh_from_db()
        assert held.moderation == "sent"
        assert user.notifications.filter(kind="recruiter_feedback").count() == 2
        feedback_service.release(held, admin=admin_user)  # no-op when not held
        another = feedback_service.send_feedback(
            recruiter, sent.job_seeker, status="general", message="idiot"
        )
        feedback_service.reject(another, admin=admin_user)
        another.refresh_from_db()
        assert another.moderation == "rejected"


def test_profile_views_counts_distinct_recruiters(auth_client):
    profile = make_candidate("ann", 70)
    r1, r2 = RecruiterFactory(), RecruiterFactory()
    ProfileView.objects.create(recruiter=r1, job_seeker=profile)
    ProfileView.objects.create(recruiter=r1, job_seeker=profile)
    ProfileView.objects.create(recruiter=r2, job_seeker=profile)
    old = ProfileView.objects.create(recruiter=r2, job_seeker=profile)
    ProfileView.objects.filter(pk=old.pk).update(viewed_at=timezone.now() - timedelta(days=20))
    body = auth_client(profile.user).get("/api/v1/me/profile-views").json()
    assert body["thisWeek"] == 2
    assert sum(w["recruiters"] for w in body["weeks"]) >= 3
    assert "recruiter" not in str(body).replace("recruiters", "")


def test_profile_views_job_seekers_only(auth_client, recruiter):
    assert auth_client(recruiter).get("/api/v1/me/profile-views").status_code == 403
