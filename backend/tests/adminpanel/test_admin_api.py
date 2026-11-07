import pytest

from apps.analysis.models import Analysis
from apps.core.models import AuditLog
from apps.notifications.models import Delivery, Notification
from apps.recruiting.models import Feedback
from apps.recruiting.services import feedback as feedback_service
from apps.skills.models import DependencyMapping, Skill
from tests.factories import JobSeekerFactory, RecruiterFactory
from tests.recruiting.helpers import make_candidate

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin(auth_client, admin_user):
    return auth_client(admin_user)


@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/admin/stats",
        "/api/v1/admin/recruiters",
        "/api/v1/admin/users",
        "/api/v1/admin/notification-deliveries",
        "/api/v1/admin/audit-log",
        "/api/v1/admin/feedback/held",
        "/api/v1/admin/skills",
        "/api/v1/admin/dependency-mappings",
    ],
)
def test_admin_only(auth_client, api_client, job_seeker, recruiter, url):
    assert api_client.get(url).status_code == 401
    assert auth_client(job_seeker).get(url).status_code == 403
    assert auth_client(recruiter).get(url).status_code == 403


def test_stats(admin):
    RecruiterFactory(profile__approval_status="pending")
    make_candidate("ann", 80)
    make_candidate("ben", 60)
    Analysis.objects.create(github_login="x", status="failed")
    note = Notification.objects.create(
        user=JobSeekerFactory(), kind="analysis_completed", title="t"
    )
    for status in ("sent", "failed", "skipped", "dry_run"):
        Delivery.objects.create(
            notification=note, channel="sms", provider="thrivewave", status=status
        )
    body = admin.get("/api/v1/admin/stats").json()
    assert body["pendingRecruiters"] == 1
    assert body["averageSignalScore"] == 70.0
    assert body["usersByRole"]["jobSeeker"] >= 3
    assert body["analysesPerDay"][-1]["total"] == 3 and body["analysesPerDay"][-1]["completed"] == 2
    assert body["deliveryRates"]["sms"] == {
        "total": 3,
        "ok": 2,
        "failed": 1,
        "skipped": 1,
        "rate": 0.667,
    }
    assert body["deliveryRates"]["email"]["rate"] is None


def test_recruiter_queue_and_review(admin, admin_user):
    pending = RecruiterFactory(profile__approval_status="pending")
    unverified = RecruiterFactory(profile__approval_status="pending", email_verified_at=None)
    RecruiterFactory()
    queue = admin.get("/api/v1/admin/recruiters", {"status": "pending"}).json()
    assert queue["count"] == 2
    approved = admin.post(
        f"/api/v1/admin/recruiters/{pending.public_id}/approve", {"note": "Checked"}
    ).json()
    assert approved["approvalStatus"] == "approved" and approved["reviewNote"] == "Checked"
    assert pending.notifications.get().kind == "recruiter_approved"
    blocked = admin.post(f"/api/v1/admin/recruiters/{unverified.public_id}/approve", {})
    assert blocked.json()["code"] == "email_not_verified"
    assert (
        admin.post(
            f"/api/v1/admin/recruiters/{unverified.public_id}/reject", {"note": "No company"}
        ).json()["approvalStatus"]
        == "rejected"
    )
    assert (
        admin.post(
            "/api/v1/admin/recruiters/00000000-0000-0000-0000-000000000000/approve", {}
        ).status_code
        == 404
    )


def test_users_search_suspend_and_role(admin, admin_user, api_client):
    from apps.accounts.tokens import issue_tokens

    seeker = make_candidate("ann", 70, name="Ann Wairimu").user
    assert (
        admin.get("/api/v1/admin/users", {"search": "wairimu"}).json()["results"][0]["githubLogin"]
        == "ann"
    )
    assert admin.get("/api/v1/admin/users", {"role": "admin"}).json()["count"] == 1
    refresh = issue_tokens(seeker)["refresh"]
    body = admin.patch(f"/api/v1/admin/users/{seeker.public_id}", {"isActive": False}).json()
    assert body["isActive"] is False
    assert api_client.post("/api/v1/auth/token/refresh", {"refresh": refresh}).status_code == 401
    assert AuditLog.objects.filter(action="admin.user_suspended").exists()
    assert admin.get("/api/v1/admin/users", {"isActive": "false"}).json()["count"] == 1
    assert (
        admin.patch(f"/api/v1/admin/users/{seeker.public_id}", {"role": "recruiter"}).status_code
        == 400
    )
    promoted = admin.patch(
        f"/api/v1/admin/users/{seeker.public_id}", {"role": "admin", "isActive": True}
    ).json()
    assert promoted["role"] == "admin"
    assert (
        admin.patch(f"/api/v1/admin/users/{admin_user.public_id}", {"isActive": False}).status_code
        == 400
    )
    assert admin.get(f"/api/v1/admin/users/{seeker.public_id}").json()["role"] == "admin"


def test_deliveries_filter_and_retry(admin, django_capture_on_commit_callbacks):
    note = Notification.objects.create(user=JobSeekerFactory(), kind="analysis_failed", title="t")
    failed = Delivery.objects.create(
        notification=note,
        channel="email",
        provider="smtp",
        status="failed",
        attempts=3,
        recipient="a@b.co",
        provider_response={"render": {"subject": "S", "text": "T", "html": "<p>T</p>"}},
    )
    Delivery.objects.create(notification=note, channel="sms", provider="thrivewave", status="sent")
    assert (
        admin.get("/api/v1/admin/notification-deliveries", {"status": "failed"}).json()["count"]
        == 1
    )
    assert (
        admin.get("/api/v1/admin/notification-deliveries", {"provider": "thrivewave"}).json()[
            "count"
        ]
        == 1
    )
    with django_capture_on_commit_callbacks(execute=True):
        response = admin.post(f"/api/v1/admin/notification-deliveries/{failed.public_id}/retry")
    assert response.json()["status"] == "queued"
    failed.refresh_from_db()
    assert (failed.status, failed.attempts) == ("sent", 1)
    again = admin.post(f"/api/v1/admin/notification-deliveries/{failed.public_id}/retry")
    assert again.status_code == 400


def test_audit_log_filters(admin, admin_user):
    from apps.core import audit

    audit.record("auth.sign_in", actor=admin_user)
    audit.record("auth.sign_out", actor=admin_user)
    audit.record("feedback.sent")
    assert admin.get("/api/v1/admin/audit-log", {"action": "auth."}).json()["count"] == 2
    assert admin.get("/api/v1/admin/audit-log", {"action": "auth.sign_in"}).json()["count"] == 1
    assert admin.get("/api/v1/admin/audit-log", {"actor": admin_user.email}).json()["count"] == 2
    assert (
        admin.get("/api/v1/admin/audit-log", {"since": "2999-01-01T00:00:00Z"}).json()["count"] == 0
    )
    assert admin.get("/api/v1/admin/audit-log", {"until": "nonsense"}).status_code == 400
    assert "id" not in admin.get("/api/v1/admin/audit-log").json()["results"][0]


def test_held_feedback_release_and_reject(admin, recruiter):
    seeker = make_candidate("ann", 70)
    held = feedback_service.send_feedback(
        recruiter, seeker, status="general", message="garbage code"
    )
    other = feedback_service.send_feedback(recruiter, seeker, status="general", message="idiot")
    assert admin.get("/api/v1/admin/feedback/held").json()["count"] == 2
    assert admin.post(f"/api/v1/admin/feedback/{held.public_id}/release").status_code == 200
    assert seeker.user.notifications.filter(kind="recruiter_feedback").count() == 1
    assert admin.post(f"/api/v1/admin/feedback/{other.public_id}/reject").status_code == 200
    assert Feedback.objects.get(pk=other.pk).moderation == "rejected"
    assert admin.post(f"/api/v1/admin/feedback/{held.public_id}/release").status_code == 404


def test_skills_and_mappings_change_detection(admin):
    created = admin.post(
        "/api/v1/admin/skills",
        {"name": "Svelte", "category": "framework", "aliases": ["SvelteKit", "svelte"]},
    )
    assert created.status_code == 201
    assert created.json() == {
        "name": "Svelte",
        "slug": "svelte",
        "category": "framework",
        "aliases": ["svelte", "sveltekit"],
    }
    clash = admin.patch("/api/v1/admin/skills/svelte", {"aliases": ["js"]})
    assert clash.status_code == 400
    assert (
        admin.patch("/api/v1/admin/skills/svelte", {"category": "tool"}).json()["category"]
        == "tool"
    )
    mapping = admin.post(
        "/api/v1/admin/dependency-mappings",
        {"ecosystem": "npm", "packageName": "Svelte", "skill": "Svelte"},
    )
    assert mapping.json() == {"ecosystem": "npm", "packageName": "svelte", "skill": "Svelte"}
    moved = admin.patch("/api/v1/admin/dependency-mappings/npm/@nestjs/core", {"skill": "Node.js"})
    assert moved.json()["skill"] == "Node.js"
    assert (
        admin.patch("/api/v1/admin/dependency-mappings/npm/nope", {"skill": "Go"}).status_code
        == 404
    )
    assert admin.get("/api/v1/admin/dependency-mappings", {"ecosystem": "go"}).json()["count"] == 1

    from apps.analysis.services import skills
    from apps.analysis.services.pipeline import load_catalogue
    from tests.analysis.builders import repo

    catalogue, _ = load_catalogue()
    found = skills.skills_in_repo(
        repo(manifests={"package.json": '{"dependencies": {"svelte": "4"}}'}), catalogue
    )
    assert found == {"Svelte"}
    assert (
        Skill.objects.filter(name="Svelte").exists()
        and DependencyMapping.objects.filter(package_name="svelte").exists()
    )
