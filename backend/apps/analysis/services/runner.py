"""Starting analyses: who may analyse which login, reuse of recent results, one at a time."""

from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.errors import EmailNotVerified, GithubNotLinked
from apps.accounts.models import GithubAccount, JobSeekerProfile, Role
from apps.core import audit

from ..errors import AnalysisInProgress
from ..models import Analysis, AnalysisStatus

ACTIVE = (AnalysisStatus.QUEUED, AnalysisStatus.RUNNING)


def expire_stale(login: str) -> None:
    """A worker that died mid-analysis must not block the login forever."""
    cutoff = timezone.now() - timedelta(minutes=settings.ANALYSIS_STALE_MINUTES)
    Analysis.objects.filter(github_login=login, status__in=ACTIVE, updated_at__lt=cutoff).update(
        status=AnalysisStatus.FAILED,
        error_code="timeout",
        error_message="The analysis took too long and was stopped. Try again.",
        completed_at=timezone.now(),
    )


def _claims_changed(previous: Analysis, profile: JobSeekerProfile | None) -> bool:
    if profile is None:
        return False
    before = set(previous.claim_results.values_list("claimed_skill_id", flat=True))
    now = set(profile.claimed_skills.values_list("id", flat=True))
    return before != now


def resolve_target(user, github_login: str | None) -> tuple[str, JobSeekerProfile | None]:
    if user.role == Role.JOB_SEEKER:
        if not user.is_email_verified:
            raise EmailNotVerified("Verify your email address before running an analysis.")
        account = getattr(user, "github_account", None)
        if account is None:
            raise GithubNotLinked("Sign in with GitHub first: we only analyse accounts you own.")
        return account.login, user.job_seeker_profile
    # Admin: any login. Attach it to the job seeker who owns it, if there is one.
    login = (github_login or "").strip().lower()
    account = (
        GithubAccount.objects.select_related("user__job_seeker_profile").filter(login=login).first()
    )
    profile = getattr(account.user, "job_seeker_profile", None) if account else None
    return login, profile


def start(
    user, *, github_login: str | None = None, force: bool = False, request=None
) -> tuple[Analysis, bool]:
    """Returns (analysis, reused). Reused analyses are complete; new ones are queued."""
    login, profile = resolve_target(user, github_login)
    expire_stale(login)
    if Analysis.objects.filter(github_login=login, status__in=ACTIVE).exists():
        raise AnalysisInProgress()

    if not force:
        recent = (
            Analysis.objects.filter(
                github_login=login,
                job_seeker=profile,
                status=AnalysisStatus.COMPLETED,
                completed_at__gte=timezone.now() - timedelta(hours=settings.ANALYSIS_CACHE_HOURS),
            )
            .order_by("-completed_at")
            .first()
        )
        if recent and not _claims_changed(recent, profile):
            return recent, True

    try:
        with transaction.atomic():
            analysis = Analysis.objects.create(
                github_login=login, job_seeker=profile, triggered_by=user
            )
    except IntegrityError as exc:  # raced with another request (one-active-per-login constraint)
        raise AnalysisInProgress() from exc
    audit.record(
        "analysis.run",
        actor=user,
        target=analysis,
        request=request,
        metadata={"login": login, "force": force},
    )

    from ..tasks import run_analysis

    transaction.on_commit(lambda: run_analysis.delay(analysis.pk))
    return analysis, False
