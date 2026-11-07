"""Sending recruiter feedback: clean it, store it, notify the job seeker (or hold it)."""

from django.db import transaction
from django.utils import timezone

from apps.core import audit
from apps.notifications.models import Kind
from apps.notifications.services import notify

from ..models import Feedback, Moderation
from .moderation import clean

STAGE_LABELS = {
    "saved": "Shortlisted",
    "contacted": "Contacted",
    "interview": "Interview",
    "offer": "Offer",
    "rejected": "Not progressing",
}


def _company_name(recruiter) -> str:
    profile = getattr(recruiter, "recruiter_profile", None)
    return profile.company.name if profile else "SkillProof"


def _notify_feedback(feedback: Feedback) -> None:
    recruiter = feedback.recruiter
    notify(
        feedback.job_seeker.user,
        Kind.RECRUITER_FEEDBACK,
        {
            "company": feedback.company_name,
            "recruiter_name": (recruiter.full_name or "A recruiter")
            if recruiter
            else "A recruiter",
            "status_label": feedback.get_status_display(),
            "message": feedback.message,
        },
        actor=recruiter,
        feedback=feedback,
        link_path="/inbox",
    )


@transaction.atomic
def send_feedback(
    recruiter, job_seeker, *, status: str, message: str, job_posting=None, request=None
) -> Feedback:
    cleaned = clean(message)  # raises FeedbackRejected
    latest = job_seeker.analyses.filter(status="completed").order_by("-completed_at").first()
    feedback = Feedback.objects.create(
        recruiter=recruiter,
        job_seeker=job_seeker,
        analysis=latest,
        job_posting=job_posting,
        company_name=_company_name(recruiter),
        status=status,
        message=cleaned.message,
        moderation=Moderation.HELD if cleaned.hold_reason else Moderation.SENT,
        held_reason=cleaned.hold_reason,
    )
    audit.record(
        "feedback.held" if cleaned.hold_reason else "feedback.sent",
        actor=recruiter,
        target=feedback,
        request=request,
        metadata={"status": status, "job_seeker": str(job_seeker.user.public_id)},
    )
    if not cleaned.hold_reason:
        _notify_feedback(feedback)
    return feedback


@transaction.atomic
def release(feedback: Feedback, *, admin, request=None) -> None:
    """Admin decided a held message is fine: send it now."""
    if feedback.moderation != Moderation.HELD:
        return
    feedback.moderation = Moderation.SENT
    feedback.created_at = timezone.now()  # appears as new in the job seeker's inbox
    feedback.save(update_fields=["moderation", "created_at", "updated_at"])
    audit.record("feedback.released", actor=admin, target=feedback, request=request)
    _notify_feedback(feedback)


@transaction.atomic
def reject(feedback: Feedback, *, admin, request=None) -> None:
    if feedback.moderation != Moderation.HELD:
        return
    feedback.moderation = Moderation.REJECTED
    feedback.save(update_fields=["moderation", "updated_at"])
    audit.record("feedback.rejected", actor=admin, target=feedback, request=request)


def notify_stage(entry) -> None:
    """Tell the job seeker they moved forward in a recruiter's shortlist."""
    notify(
        entry.job_seeker.user,
        Kind.SHORTLISTED,
        {
            "company": _company_name(entry.recruiter),
            "stage_label": STAGE_LABELS[entry.stage],
            "job_title": entry.job_posting.title if entry.job_posting else "",
        },
        actor=entry.recruiter,
        link_path="/inbox",
    )
