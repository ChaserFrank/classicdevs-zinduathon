"""The skill card JSON (brief 7.1). The frontend's `lib/types.ts` depends on this exact shape,
including the `hasCI` casing, so it is built as a plain dict here and snapshot-tested.

Display values are Title Case ("Strong", "Framework") although the database stores lowercase.
"""

from apps.accounts.models import GithubAccount

from .models import Analysis


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def build_card(analysis: Analysis) -> dict:
    repo_rows = {
        row.pk: row
        for row in analysis.repo_rows.select_related("repository").order_by("-user_commits", "id")
    }

    def repo_json(row) -> dict:
        return {
            "name": row.repository.name,
            "url": row.repository.html_url,
            "commits": row.user_commits,
            "firstCommit": _iso(row.first_commit_at),
            "lastCommit": _iso(row.last_commit_at),
            "hasTests": row.has_tests,
            "hasCI": row.has_ci,
        }

    skills = []
    for row in (
        analysis.skill_rows.select_related("skill")
        .prefetch_related("repos")
        .order_by("-evidence", "skill__name")
    ):
        repos = sorted(row.repos.all(), key=lambda r: (-r.user_commits, r.pk))
        skills.append(
            {
                "name": row.skill.name,
                "category": row.skill.get_category_display(),
                "label": row.get_label_display(),
                "evidence": float(row.evidence),
                "repos": [repo_json(repo_rows.get(r.pk, r)) for r in repos],
            }
        )

    claims = [
        {
            "skill": c.claimed_skill.skill.name
            if c.claimed_skill.skill
            else c.claimed_skill.raw_text,
            "status": c.get_status_display(),
        }
        for c in analysis.claim_results.select_related("claimed_skill__skill").order_by(
            "claimed_skill__position", "id"
        )
    ]

    flags = []
    for flag in analysis.flags.select_related("analysis_repository__repository").order_by("id"):
        item = {"type": flag.type, "reason": flag.reason}
        if flag.analysis_repository:
            item["repo"] = flag.analysis_repository.repository.name
        flags.append(item)

    login = analysis.github_login
    return {
        "username": login,
        "profile": {
            "username": login,
            "name": analysis.github_name or None,
            "avatarUrl": analysis.avatar_url or f"https://github.com/{login}.png",
            "verifiedOwner": GithubAccount.objects.filter(login=login).exists(),
        },
        "signalScore": analysis.signal_score or 0,
        "subScores": {
            s.key: {"value": s.value, "reason": s.reason} for s in analysis.subscores.order_by("id")
        },
        "skills": skills,
        "claims": claims,
        "flags": flags,
        "aiSummary": analysis.ai_summary,
        "reposAnalysed": analysis.repos_analysed,
        "commitsAnalysed": analysis.commits_analysed,
        "analysedAt": _iso(analysis.completed_at),
    }
