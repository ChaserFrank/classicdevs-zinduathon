"""Orchestrates one analysis: fetch → detect → score → flag → summarise → persist.

This is the only analysis module that touches the database (besides the GitHub ETag cache). The
rules it calls are pure, so what's tested in isolation is exactly what runs here.
"""

import logging
from datetime import UTC, datetime
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import GithubAccount
from apps.skills.models import Skill, SkillAlias

from . import claims as claim_rules
from . import flags as flag_rules
from . import scores, summary, tips
from . import skills as skill_rules
from .github import DbCache, GithubClient, GithubError, fetch_profile

logger = logging.getLogger(__name__)


def load_catalogue() -> tuple[skill_rules.Catalogue, dict[str, str]]:
    """(Catalogue for detection, lookup for claims). Names and aliases, lowercase → skill name."""
    from apps.skills.models import DependencyMapping

    lookup = {name.lower(): name for name in Skill.objects.values_list("name", flat=True)}
    lookup.update(dict(SkillAlias.objects.values_list("alias", "skill__name")))
    deps = {
        (eco, pkg): name
        for eco, pkg, name in DependencyMapping.objects.values_list(
            "ecosystem", "package_name", "skill__name"
        )
    }
    return skill_rules.Catalogue(language_aliases=lookup, dependencies=deps), lookup


def _token_for(analysis) -> str:
    """The job seeker's own GitHub token when it belongs to the analysed login (5,000 req/h)."""
    account = GithubAccount.objects.filter(login=analysis.github_login).first()
    token = account.get_token() if account else ""
    return token or settings.GITHUB_TOKEN


def _set_progress(analysis, step: int) -> None:
    analysis.progress_step = step
    analysis.save(update_fields=["progress_step", "updated_at"])


def run(analysis) -> None:
    """Run an analysis to completion or failure. Never raises for expected GitHub errors."""
    from apps.analysis.models import AnalysisStatus

    analysis.status = AnalysisStatus.RUNNING
    analysis.started_at = timezone.now()
    analysis.progress_step = 1
    analysis.save(update_fields=["status", "started_at", "progress_step", "updated_at"])
    try:
        client = GithubClient(
            _token_for(analysis),
            base_url=settings.GITHUB_API_URL,
            cache=DbCache(settings.GITHUB_CACHE_TTL_HOURS),
        )
        profile, repos = fetch_profile(
            client,
            analysis.github_login,
            max_repos=settings.ANALYSIS_MAX_REPOS,
            commit_sample=settings.ANALYSIS_COMMIT_SAMPLE,
            workers=settings.ANALYSIS_FETCH_WORKERS,
            on_repos_listed=lambda: _set_progress(analysis, 2),
        )
        _set_progress(analysis, 3)
        catalogue, lookup = load_catalogue()
        detected = skill_rules.detect(repos, catalogue)

        _set_progress(analysis, 4)
        now = datetime.now(UTC)
        signal, subscores = scores.score(repos, detected, now)
        labels = {s.name: s.label for s in detected}
        claimed = (
            list(analysis.job_seeker.claimed_skills.select_related("skill"))
            if analysis.job_seeker
            else []
        )
        claim_statuses = claim_rules.check(
            [(c.raw_text, c.skill.name if c.skill else None) for c in claimed], labels
        )
        unverified = [raw for raw, status in claim_statuses if status == "unverified"]
        all_flags = flag_rules.repo_flags(repos) + flag_rules.claim_flags(unverified)
        tip_list = tips.tips_for(repos, subscores, all_flags)
        payload = summary.build_payload(
            skills=detected, subscores=subscores, flags=all_flags, repos_analysed=len(repos)
        )
        text, source = summary.summarise(payload, lookup.values())

        _persist(
            analysis,
            profile=profile,
            repos=repos,
            detected=detected,
            signal=signal,
            subscores=subscores,
            claimed=claimed,
            claim_statuses=claim_statuses,
            flags=all_flags,
            tip_list=tip_list,
            summary_text=text,
            summary_source=source,
        )
    except GithubError as exc:
        _fail(analysis, exc.code, exc.message)
    except Exception:
        logger.exception("Analysis crashed", extra={"analysis": str(analysis.public_id)})
        _fail(analysis, "server_error", "Something went wrong while analysing. Try again.")
    _on_finished(analysis)


def _fail(analysis, code: str, message: str) -> None:
    from apps.analysis.models import AnalysisStatus

    analysis.status = AnalysisStatus.FAILED
    analysis.error_code = code
    analysis.error_message = message[:300]
    analysis.completed_at = timezone.now()
    analysis.save(
        update_fields=["status", "error_code", "error_message", "completed_at", "updated_at"]
    )


def _on_finished(analysis) -> None:
    """Hook for notifications (wired up in Phase 4)."""


@transaction.atomic
def _persist(
    analysis,
    *,
    profile,
    repos,
    detected,
    signal,
    subscores,
    claimed,
    claim_statuses,
    flags,
    tip_list,
    summary_text,
    summary_source,
) -> None:
    from apps.analysis import models as m

    rows: dict[str, m.AnalysisRepository] = {}
    for repo in repos:
        repository, _ = m.Repository.objects.update_or_create(
            github_id=repo.github_id,
            defaults={
                "owner_login": repo.owner.lower(),
                "name": repo.name,
                "html_url": repo.html_url,
                "is_fork": repo.is_fork,
                "default_branch": repo.default_branch,
                "pushed_at": repo.pushed_at,
            },
        )
        sampled = repo.sampled_commits
        rows[repo.full_name] = m.AnalysisRepository.objects.create(
            analysis=analysis,
            repository=repository,
            user_commits=repo.user_commit_count,
            total_commits=repo.total_commits,
            first_commit_at=repo.first_commit_at,
            last_commit_at=repo.last_commit_at,
            has_tests=skill_rules.has_tests(repo),
            has_ci=skill_rules.has_ci(repo),
            readme_length=repo.readme_size,
            sampled_additions=sum(c.additions or 0 for c in sampled),
            sampled_deletions=sum(c.deletions or 0 for c in sampled),
        )

    skills_by_name = Skill.objects.in_bulk([s.name for s in detected], field_name="name")
    for result in detected:
        skill = skills_by_name.get(result.name)
        if skill is None:  # a practice skill an admin deleted; nothing to attach evidence to
            continue
        row = m.AnalysisSkill.objects.create(
            analysis=analysis,
            skill=skill,
            evidence=Decimal(str(result.evidence)),
            label=result.label,
        )
        m.SkillEvidence.objects.bulk_create(
            [
                m.SkillEvidence(analysis_skill=row, analysis_repository=rows[name])
                for name in result.repos
            ]
        )

    m.SubScore.objects.bulk_create(
        [
            m.SubScore(analysis=analysis, key=s.key, value=s.value, reason=s.reason[:300])
            for s in subscores
        ]
    )
    by_raw = {c.raw_text: c for c in claimed}
    m.ClaimResult.objects.bulk_create(
        [
            m.ClaimResult(analysis=analysis, claimed_skill=by_raw[raw], status=status)
            for raw, status in claim_statuses
        ]
    )
    m.Flag.objects.bulk_create(
        [
            m.Flag(
                analysis=analysis,
                type=f.type,
                reason=f.reason[:300],
                analysis_repository=rows.get(f.repo) if f.repo else None,
                claimed_skill=by_raw.get(f.claim) if f.claim else None,
            )
            for f in flags
        ]
    )
    analysis.status = m.AnalysisStatus.COMPLETED
    analysis.github_name = profile.name or ""
    analysis.avatar_url = profile.avatar_url
    analysis.signal_score = signal
    analysis.ai_summary = summary_text
    analysis.summary_source = summary_source
    analysis.tips = tip_list
    analysis.repos_analysed = len(repos)
    analysis.commits_analysed = sum(r.user_commit_count for r in repos)
    analysis.completed_at = timezone.now()
    analysis.error_code = ""
    analysis.error_message = ""
    analysis.save()
