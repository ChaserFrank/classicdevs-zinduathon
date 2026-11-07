import pytest
from django.core import mail

from apps.accounts.services import record_consents
from apps.recruiting.models import Feedback, ProfileView
from tests.factories import JobSeekerFactory, RecruiterFactory
from tests.recruiting.helpers import add_analysis, make_candidate

pytestmark = pytest.mark.django_db
URL = "/api/v1/candidates"


@pytest.fixture
def pool():
    return {
        "ann": make_candidate(
            "ann",
            80,
            {"Python": "strong", "Django": "moderate", "React": "emerging"},
            headline="Backend dev",
        ),
        "ben": make_candidate(
            "ben",
            55,
            {"Python": "moderate", "React": "strong"},
            open_to_work=False,
            name="Ben Mwangi",
        ),
        "cy": make_candidate("cy", 70, {"Go": "strong"}),
        "hidden": make_candidate("hidden", 99, {"Python": "strong"}, visible=False),
    }


def logins(response):
    return [c["githubLogin"] for c in response.json()["results"]]


class TestSearch:
    def test_visible_only_ordered_by_score(self, auth_client, recruiter, pool):
        JobSeekerFactory()  # no analysis → not a candidate
        response = auth_client(recruiter).get(URL)
        assert logins(response) == ["ann", "cy", "ben"]
        item = response.json()["results"][0]
        assert set(item) == {
            "githubLogin",
            "name",
            "headline",
            "location",
            "avatarUrl",
            "openToWork",
            "signalScore",
            "analysedAt",
            "topSkills",
        }
        assert item["topSkills"][0] == {"name": "Python", "label": "Strong"}
        assert "email" not in str(response.json()) and "phone" not in str(response.json())

    def test_skills_and_min_label(self, auth_client, recruiter, pool):
        client = auth_client(recruiter)
        assert logins(client.get(URL, {"skills": "python"})) == ["ann", "ben"]
        assert logins(client.get(URL, {"skills": "python", "minLabel": "strong"})) == ["ann"]
        assert logins(client.get(URL, {"skills": "python,reactjs"})) == ["ann", "ben"]  # alias, AND
        assert logins(client.get(URL, {"skills": "python,reactjs", "minLabel": "moderate"})) == [
            "ben"
        ]

    def test_unknown_skill(self, auth_client, recruiter, pool):
        response = auth_client(recruiter).get(URL, {"skills": "python,cobol"})
        assert response.status_code == 400
        assert response.json()["fields"]["skills"] == ["Unknown skill: cobol"]

    def test_filters_and_ordering(self, auth_client, recruiter, pool):
        client = auth_client(recruiter)
        assert logins(client.get(URL, {"minScore": 60})) == ["ann", "cy"]
        assert logins(client.get(URL, {"openToWork": "false"})) == ["ben"]
        assert logins(client.get(URL, {"search": "mwangi"})) == ["ben"]
        assert logins(client.get(URL, {"search": "backend"})) == ["ann"]
        assert logins(client.get(URL, {"ordering": "signalScore"})) == ["ben", "cy", "ann"]
        assert client.get(URL, {"pageSize": 2}).json()["count"] == 3

    def test_latest_analysis_counts(self, auth_client, recruiter, pool):
        add_analysis(pool["cy"], "cy", 10, {"Python": "strong"})  # newer, lower score
        results = auth_client(recruiter).get(URL, {"skills": "python"}).json()["results"]
        assert [(c["githubLogin"], c["signalScore"]) for c in results] == [
            ("ann", 80),
            ("ben", 55),
            ("cy", 10),
        ]

    def test_permissions(self, auth_client, job_seeker, admin_user, api_client, pool):
        assert auth_client(job_seeker).get(URL).status_code == 403
        assert api_client.get(URL).status_code == 401
        pending = auth_client(RecruiterFactory(profile__approval_status="pending")).get(URL)
        assert pending.json()["code"] == "recruiter_not_approved"
        assert auth_client(admin_user).get(URL).status_code == 200


class TestDetail:
    def test_detail_records_view(self, auth_client, recruiter, pool):
        body = auth_client(recruiter).get(f"{URL}/ANN").json()
        assert body["candidate"]["githubLogin"] == "ann"
        assert body["card"]["signalScore"] == 80
        assert body["shortlist"] == [] and body["feedbackSent"] == []
        auth_client(recruiter).get(f"{URL}/ann")  # second view within the hour isn't double counted
        assert ProfileView.objects.filter(job_seeker=pool["ann"]).count() == 1

    def test_hidden_card(self, auth_client, recruiter, admin_user, pool):
        assert auth_client(recruiter).get(f"{URL}/hidden").status_code == 404
        assert auth_client(admin_user).get(f"{URL}/hidden").status_code == 200
        assert not ProfileView.objects.exists()  # admins aren't counted

    def test_public_card_counts_recruiter_views(self, auth_client, api_client, recruiter, pool):
        api_client.get("/api/v1/cards/ann")
        auth_client(JobSeekerFactory()).get("/api/v1/cards/ann")
        auth_client(recruiter).get("/api/v1/cards/ann")
        assert ProfileView.objects.count() == 1


class TestSendFeedback:
    def post(self, client, login="ann", **body):
        return client.post(
            f"{URL}/{login}/feedback", {"status": "interview", "message": "Loved duka-api.", **body}
        )

    def test_feedback_notifies_job_seeker(
        self, auth_client, recruiter, pool, django_capture_on_commit_callbacks
    ):
        record_consents(pool["ann"].user, {"terms": True, "email_feedback": True})
        with django_capture_on_commit_callbacks(execute=True):
            response = self.post(auth_client(recruiter), message="<b>Loved</b> duka-api.")
        assert response.status_code == 201
        body = response.json()
        assert body["message"] == "Loved duka-api."
        assert body["company"] == recruiter.recruiter_profile.company.name
        assert body["moderation"] == "sent"
        feedback = Feedback.objects.get()
        assert feedback.analysis is not None
        note = pool["ann"].user.notifications.get()
        assert note.kind == "recruiter_feedback" and note.feedback == feedback
        assert mail.outbox[0].subject == f"{feedback.company_name} sent you feedback"
        assert "Loved duka-api." in mail.outbox[0].body

    def test_abusive_message_held(self, auth_client, recruiter, pool):
        body = self.post(auth_client(recruiter), message="This is garbage").json()
        assert body["moderation"] == "held"
        assert not pool["ann"].user.notifications.exists()

    def test_validation(self, auth_client, recruiter, pool):
        client = auth_client(recruiter)
        assert self.post(client, message="see http://x.y").json()["fields"]["message"] == [
            "Only https:// links are allowed."
        ]
        assert self.post(client, status="hired").status_code == 400
        assert self.post(client, login="hidden").status_code == 404
        assert self.post(client, jobPostingId="00000000-0000-0000-0000-000000000000").json()[
            "fields"
        ]["jobPostingId"]

    def test_job_from_other_company_rejected(self, auth_client, recruiter, pool):
        from apps.recruiting.models import JobPosting

        other = RecruiterFactory()
        job = JobPosting.objects.create(company=other.recruiter_profile.company, title="x")
        response = self.post(auth_client(recruiter), jobPostingId=str(job.public_id))
        assert response.status_code == 400

    def test_throttled_30_per_hour(self, auth_client, recruiter, pool):
        client = auth_client(recruiter)
        for _ in range(30):
            assert self.post(client).status_code == 201
        assert self.post(client).status_code == 429
