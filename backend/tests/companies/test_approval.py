import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory

from apps.accounts.errors import EmailNotVerified
from apps.companies import services
from apps.companies.admin import RecruiterProfileAdmin
from apps.companies.models import ApprovalStatus, RecruiterProfile
from apps.core.models import AuditLog
from tests.factories import RecruiterFactory

pytestmark = pytest.mark.django_db


def test_approve_sets_reviewer_and_audits(admin_user):
    recruiter = RecruiterFactory(profile__approval_status="pending")
    profile = services.approve(
        recruiter.recruiter_profile, reviewer=admin_user, note="Checked LinkedIn"
    )

    assert profile.approval_status == ApprovalStatus.APPROVED
    assert profile.reviewed_by == admin_user
    assert profile.reviewed_at is not None
    entry = AuditLog.objects.get(action="recruiter.approved")
    assert entry.actor == admin_user
    assert entry.metadata == {"from": "pending", "to": "approved", "note": "Checked LinkedIn"}


def test_cannot_approve_unverified_email(admin_user):
    recruiter = RecruiterFactory(profile__approval_status="pending", email_verified_at=None)
    with pytest.raises(EmailNotVerified):
        services.approve(recruiter.recruiter_profile, reviewer=admin_user)


def test_reject_and_suspend(admin_user):
    a = RecruiterFactory(profile__approval_status="pending").recruiter_profile
    b = RecruiterFactory().recruiter_profile
    assert services.reject(a, reviewer=admin_user, note="No company").approval_status == "rejected"
    assert services.suspend(b, reviewer=admin_user).approval_status == "suspended"


def test_company_reuse_normalises_whitespace_and_case():
    first = services.get_or_create_company("Acme  Kenya")
    assert services.get_or_create_company("acme kenya") == first
    assert first.name == "Acme Kenya"


def test_admin_bulk_approve_skips_unverified(admin_user):
    ok = RecruiterFactory(profile__approval_status="pending")
    unverified = RecruiterFactory(profile__approval_status="pending", email_verified_at=None)
    request = RequestFactory().post("/")
    request.user = admin_user
    request.session = {}
    request._messages = FallbackStorage(request)

    RecruiterProfileAdmin(RecruiterProfile, AdminSite()).approve_selected(
        request, RecruiterProfile.objects.all()
    )

    ok.recruiter_profile.refresh_from_db()
    unverified.recruiter_profile.refresh_from_db()
    assert ok.recruiter_profile.approval_status == "approved"
    assert unverified.recruiter_profile.approval_status == "pending"
    assert [str(m) for m in request._messages] == [
        "1 recruiter(s) set to approved.",
        "1 skipped: email not verified yet.",
    ]
