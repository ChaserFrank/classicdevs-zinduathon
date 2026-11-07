"""Recruiter approval workflow. Every status change is audited (and notifies the recruiter from
Phase 4), so admins can always answer "who approved this recruiter, and why?"."""

from django.db import transaction
from django.utils import timezone

from apps.accounts.errors import EmailNotVerified
from apps.core import audit

from .models import ApprovalStatus, Company, RecruiterProfile


def get_or_create_company(name: str) -> Company:
    """Reuse a company case-insensitively ("Safaricom" == "safaricom")."""
    name = " ".join(name.split())
    company = Company.objects.filter(name__iexact=name).first()
    return company or Company.objects.create(name=name)


@transaction.atomic
def set_status(
    profile: RecruiterProfile, status: str, *, reviewer, note: str = "", request=None
) -> RecruiterProfile:
    if status == ApprovalStatus.APPROVED and not profile.user.is_email_verified:
        raise EmailNotVerified("The recruiter must verify their email before approval.")
    previous = profile.approval_status
    profile.approval_status = status
    profile.reviewed_by = reviewer
    profile.reviewed_at = timezone.now()
    profile.review_note = note[:500]
    profile.save(
        update_fields=["approval_status", "reviewed_by", "reviewed_at", "review_note", "updated_at"]
    )
    audit.record(
        f"recruiter.{status}",
        actor=reviewer,
        target=profile.user,
        request=request,
        metadata={"from": previous, "to": status, "note": note[:500]},
    )
    on_status_changed(profile)
    return profile


def on_status_changed(profile: RecruiterProfile) -> None:
    """Email (and SMS if opted in) the recruiter about approval or rejection."""
    from apps.notifications.models import Kind
    from apps.notifications.services import notify

    kind = {
        ApprovalStatus.APPROVED: Kind.RECRUITER_APPROVED,
        ApprovalStatus.REJECTED: Kind.RECRUITER_REJECTED,
    }.get(profile.approval_status)
    if kind:
        notify(
            profile.user,
            kind,
            {"company": profile.company.name, "note": profile.review_note},
            link_path="/recruiter",
        )


def approve(profile, *, reviewer, note="", request=None):
    return set_status(
        profile, ApprovalStatus.APPROVED, reviewer=reviewer, note=note, request=request
    )


def reject(profile, *, reviewer, note="", request=None):
    return set_status(
        profile, ApprovalStatus.REJECTED, reviewer=reviewer, note=note, request=request
    )


def suspend(profile, *, reviewer, note="", request=None):
    return set_status(
        profile, ApprovalStatus.SUSPENDED, reviewer=reviewer, note=note, request=request
    )
