"""Kenya Data Protection Act 2019 rights: access (export) and erasure (account deletion).

Export: everything we hold about the user, as one JSON document. Tokens, password hashes and
verification codes are excluded (they are secrets, not personal information about the user).

Deletion: removes the user and everything that is only about them (profiles, analyses, claimed
skills, consents, notifications). Feedback a recruiter wrote stays with the job seeker who
received it, with the author anonymised. Every session is revoked first.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.core import audit

from . import tokens
from .models import Role, User

RECENT_SIGN_IN = timedelta(minutes=10)


def _iso(value):
    return value.isoformat() if value else None


def export(user: User) -> dict:
    from apps.analysis.cards import build_card
    from apps.notifications.services import matrix
    from apps.recruiting.models import Feedback, JobPosting, ShortlistEntry

    data: dict = {
        "exportedAt": timezone.now().isoformat(),
        "account": {
            "id": str(user.public_id),
            "email": user.email,
            "fullName": user.full_name,
            "role": user.role,
            "phone": user.phone,
            "emailVerifiedAt": _iso(user.email_verified_at),
            "phoneVerifiedAt": _iso(user.phone_verified_at),
            "dateJoined": _iso(user.date_joined),
            "lastLogin": _iso(user.last_login),
        },
        "consents": [
            {
                "type": c.consent_type,
                "granted": c.granted,
                "policyVersion": c.policy_version,
                "at": _iso(c.created_at),
                "ip": c.ip_address,
            }
            for c in user.consents.order_by("created_at")
        ],
        "notificationPreferences": matrix(user),
        "notifications": [
            {
                "kind": n.kind,
                "title": n.title,
                "body": n.body,
                "readAt": _iso(n.read_at),
                "createdAt": _iso(n.created_at),
            }
            for n in user.notifications.order_by("created_at")
        ],
    }
    if account := getattr(user, "github_account", None):
        data["github"] = {
            "login": account.login,
            "githubId": account.github_id,
            "connectedAt": _iso(account.connected_at),
            "scopes": account.token_scopes,
        }
    if profile := getattr(user, "job_seeker_profile", None):
        data["jobSeekerProfile"] = {
            "headline": profile.headline,
            "location": profile.location,
            "cardVisible": profile.card_visible,
            "openToWork": profile.open_to_work,
        }
        data["claimedSkills"] = list(profile.claimed_skills.values_list("raw_text", flat=True))
        data["analyses"] = [
            build_card(a)
            if a.status == "completed"
            else {"status": a.status, "createdAt": _iso(a.created_at), "error": a.error_code}
            for a in profile.analyses.order_by("created_at")
        ]
        data["feedbackReceived"] = [
            {
                "company": f.company_name,
                "status": f.status,
                "message": f.message,
                "readAt": _iso(f.read_at),
                "createdAt": _iso(f.created_at),
            }
            for f in profile.feedback_received.filter(moderation="sent").order_by("created_at")
        ]
        data["profileViews"] = profile.views.count()
    if recruiter := getattr(user, "recruiter_profile", None):
        data["recruiterProfile"] = {
            "company": recruiter.company.name,
            "jobTitle": recruiter.job_title,
            "approvalStatus": recruiter.approval_status,
            "reviewedAt": _iso(recruiter.reviewed_at),
        }
        data["feedbackSent"] = [
            {
                "to": f.job_seeker.user.full_name,
                "status": f.status,
                "message": f.message,
                "moderation": f.moderation,
                "createdAt": _iso(f.created_at),
            }
            for f in Feedback.objects.filter(recruiter=user)
            .select_related("job_seeker__user")
            .order_by("created_at")
        ]
        data["shortlist"] = [
            {
                "candidate": e.job_seeker.user.full_name,
                "stage": e.stage,
                "note": e.note,
                "createdAt": _iso(e.created_at),
            }
            for e in ShortlistEntry.objects.filter(recruiter=user).select_related(
                "job_seeker__user"
            )
        ]
        data["jobPostings"] = list(
            JobPosting.objects.filter(created_by=user).values("title", "status", "created_at")
        )
        for job in data["jobPostings"]:
            job["created_at"] = _iso(job["created_at"])
    return data


def can_delete_without_password(user: User) -> bool:
    """GitHub-only accounts confirm by having signed in within the last 10 minutes."""
    return (
        not user.has_usable_password()
        and user.last_login is not None
        and timezone.now() - user.last_login <= RECENT_SIGN_IN
    )


@transaction.atomic
def delete_account(user: User, request=None) -> None:
    role = user.role
    tokens.blacklist_all(user)
    # Outstanding tokens point at the user; keep the blacklist rows but drop the link.
    from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

    OutstandingToken.objects.filter(user=user).update(user=None)
    audit.record("privacy.account_deleted", request=request, metadata={"role": role})
    user.delete()  # cascades; Feedback.recruiter is SET_NULL (anonymised)


def is_deletable_role(user: User) -> bool:
    return user.role in (Role.JOB_SEEKER, Role.RECRUITER)
