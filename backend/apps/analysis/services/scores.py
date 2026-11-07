"""Step 4: the Signal Score (brief 8.4). Five integer sub-scores, 0–20 each; the score is their sum.

Pure. `now` is passed in so tests (and re-runs) are deterministic. Rounding is half-up
(`_round`), so 10.5 → 11, and every value is clamped to 0–20.
"""

import math
import statistics
from collections.abc import Sequence
from datetime import datetime, timedelta

from . import skills as skill_rules
from .types import Repo, SkillResult, SubScoreResult

MAX = 20
KEYS = ("consistency", "iteration", "quality", "breadth", "ownership")


def _round(value: float) -> int:
    return max(0, min(MAX, math.floor(value + 0.5)))


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def original_repos(repos: Sequence[Repo]) -> list[Repo]:
    return [r for r in repos if not r.is_fork]


def dominant_commit_share(repo: Repo) -> float:
    """Largest share of the repo's sampled added lines held by one commit (0 if none sampled)."""
    added = [c.additions or 0 for c in repo.sampled_commits]
    total = sum(added)
    return max(added) / total if total else 0.0


# --- Sub-scores ---


def consistency(repos: Sequence[Repo], now: datetime) -> SubScoreResult:
    """20 × min(1, active ISO weeks in the last 365 days / 26)."""
    since = now - timedelta(days=365)
    weeks = {
        c.date.isocalendar()[:2]
        for r in original_repos(repos)
        for c in r.user_commits
        if since <= c.date <= now
    }
    value = _round(MAX * min(1.0, len(weeks) / 26))
    return SubScoreResult("consistency", value, f"Active in {len(weeks)} of the last 52 weeks")


def iteration(repos: Sequence[Repo]) -> SubScoreResult:
    """Median sampled commit size: ≤200 → 8, ≤500 → 5, else 2 (0 if nothing sampled)
    + 12 × share of repos with 10+ user commits
    − 6 × share of repos where one commit holds > 50% of sampled added lines."""
    originals = original_repos(repos)
    if not originals:
        return SubScoreResult("iteration", 0, "No original repositories to assess")
    sizes = [c.size for r in originals for c in r.sampled_commits]
    if not sizes:
        size_points, median = 0, None
    else:
        median = statistics.median(sizes)
        size_points = 8 if median <= 200 else 5 if median <= 500 else 2
    sustained = sum(1 for r in originals if (r.user_commit_count or len(r.user_commits)) >= 10)
    dominated = sum(1 for r in originals if dominant_commit_share(r) > 0.5)
    n = len(originals)
    value = _round(size_points + 12 * sustained / n - 6 * dominated / n)
    median_text = (
        f"median commit {int(median)} lines" if median is not None else "no commits sampled"
    )
    reason = (
        f"{median_text.capitalize()}; {sustained} of {_plural(n, 'repo')} with 10+ commits; "
        f"{dominated} mostly arrived in one commit"
    )
    return SubScoreResult("iteration", value, reason)


def quality(repos: Sequence[Repo]) -> SubScoreResult:
    """+8 tests, +6 CI, +3 a README over 300 bytes, +3 a Dockerfile or .env.example (any repo)."""
    originals = original_repos(repos)
    parts: list[tuple[str, int, bool]] = [
        ("tests", 8, any(skill_rules.has_tests(r) for r in originals)),
        ("CI", 6, any(skill_rules.has_ci(r) for r in originals)),
        ("a README", 3, any(r.readme_size > 300 for r in originals)),
        (
            "Docker or .env.example",
            3,
            any(skill_rules.has_docker(r) or skill_rules.has_env_example(r) for r in originals),
        ),
    ]
    value = sum(points for _, points, present in parts if present)
    have = [name for name, _, present in parts if present]
    missing = [name for name, _, present in parts if not present]
    if not have:
        reason = "No tests, CI, README or Docker setup found"
    elif not missing:
        reason = "Has tests, CI, a README and Docker or .env.example"
    else:
        reason = f"Has {', '.join(have)}; missing {', '.join(missing)}"
    return SubScoreResult("quality", _round(value), reason)


def breadth(skills: Sequence[SkillResult]) -> SubScoreResult:
    """4 per Strong skill + 2 per Moderate, max 20."""
    strong = sum(1 for s in skills if s.label == "strong")
    moderate = sum(1 for s in skills if s.label == "moderate")
    value = _round(4 * strong + 2 * moderate)
    return SubScoreResult(
        "breadth", value, f"{_plural(strong, 'strong skill')}, {moderate} moderate"
    )


def ownership(repos: Sequence[Repo]) -> SubScoreResult:
    """20 × share of original repos where the user wrote ≥ 70% of the commits."""
    originals = original_repos(repos)
    if not originals:
        return SubScoreResult("ownership", 0, "No original repositories to assess")
    owned = 0
    for r in originals:
        mine = r.user_commit_count or len(r.user_commits)
        total = max(r.total_commits, mine)
        if total and mine / total >= 0.7:
            owned += 1
    value = _round(MAX * owned / len(originals))
    return SubScoreResult(
        "ownership",
        value,
        f"Wrote most of the commits in {owned} of {_plural(len(originals), 'original repo')}",
    )


def score(
    repos: Sequence[Repo], skills: Sequence[SkillResult], now: datetime
) -> tuple[int, list[SubScoreResult]]:
    subs = [
        consistency(repos, now),
        iteration(repos),
        quality(repos),
        breadth(skills),
        ownership(repos),
    ]
    return sum(s.value for s in subs), subs
