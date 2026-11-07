"""Improvement tips (brief 8.9): at most 3, from the lowest sub-scores and the flags. Pure.

Tips name a real repo where possible ("Add tests to shop-app"), because specific advice is what
gets acted on.
"""

from collections.abc import Sequence

from . import skills as skill_rules
from .types import FlagResult, Repo, SubScoreResult

MAX_TIPS = 3


def _most_active(repos: Sequence[Repo], predicate) -> Repo | None:
    candidates = [r for r in repos if not r.is_fork and predicate(r)]
    return max(
        candidates, key=lambda r: (r.user_commit_count or len(r.user_commits), r.name), default=None
    )


def _quality_tips(repos: Sequence[Repo]) -> list[str]:
    tips = []
    originals = [r for r in repos if not r.is_fork]
    busiest = _most_active(repos, lambda r: True)
    if busiest and not any(skill_rules.has_tests(r) for r in originals):
        tips.append(f"Add tests to {busiest.name}")
    if busiest and not any(skill_rules.has_ci(r) for r in originals):
        repo = busiest
        tips.append(f"Add a GitHub Actions workflow to run {repo.name}'s checks on every push")
    if repo := _most_active(repos, lambda r: r.readme_size <= 300):
        tips.append(f"Add a README to {repo.name} explaining what it does and how to run it")
    return tips


def tips_for(
    repos: Sequence[Repo], subscores: Sequence[SubScoreResult], flags: Sequence[FlagResult]
) -> list[str]:
    by_key = {s.key: s for s in subscores}
    candidates: list[tuple[int, str]] = []  # (sub-score value, tip) — lowest first

    dumps = [f for f in flags if f.type in ("one_shot_dump", "unexplained_bulk")]
    if dumps:
        n = len(dumps)
        candidates.append(
            (
                by_key["iteration"].value if "iteration" in by_key else 0,
                f"Commit in smaller steps: {n} repo{'s' if n != 1 else ''} arrived mostly in one "
                "commit",
            )
        )
    if "quality" in by_key and by_key["quality"].value < 20:
        candidates.extend((by_key["quality"].value, tip) for tip in _quality_tips(repos))
    if "consistency" in by_key and by_key["consistency"].value < 15:
        candidates.append(
            (
                by_key["consistency"].value,
                f"Commit regularly: {by_key['consistency'].reason.lower()}",
            )
        )
    if "ownership" in by_key and by_key["ownership"].value < 10:
        candidates.append(
            (by_key["ownership"].value, "Build a project of your own from scratch and push it")
        )
    if any(f.type == "tutorial_clone" for f in flags):
        candidates.append(
            (
                by_key.get("breadth", SubScoreResult("breadth", 0, "")).value,
                "Extend a tutorial project with your own feature and explain it in the README",
            )
        )
    if any(f.type == "unverified_claim" for f in flags):
        claim = next(f.claim for f in flags if f.type == "unverified_claim")
        candidates.append((10, f"Publish a small project that uses {claim}"))

    seen, tips = set(), []
    for _, tip in sorted(candidates, key=lambda c: c[0]):
        if tip not in seen:
            seen.add(tip)
            tips.append(tip)
    return tips[:MAX_TIPS]
