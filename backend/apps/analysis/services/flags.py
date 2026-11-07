"""Step 5: noise flags (brief 8.5). Worded as prompts to check, never accusations.

At most one flag per repo, in this priority: one_shot_dump, unexplained_bulk, tutorial_clone.
"""

import re
from collections.abc import Iterable, Sequence

from .types import FlagResult, Repo

ONE_SHOT_MIN_ADDED = 200
ONE_SHOT_SHARE = 0.8
BULK_MIN_ADDED = 2000
BULK_MIN_FOLLOW_UPS = 3
TUTORIAL_MAX_COMMITS = 5

TUTORIAL_PATTERN = re.compile(
    r"(todo|to-do|calculator|weather|tic-?tac-?toe|hello-?world|"
    r"(netflix|amazon|spotify|youtube|twitter|instagram|airbnb|uber|facebook|whatsapp)[-_ ]?clone|"
    r"portfolio-template|landing-page-tutorial|crud-tutorial)",
    re.IGNORECASE,
)


def one_shot_dump(repo: Repo) -> FlagResult | None:
    added = [c.additions or 0 for c in repo.sampled_commits]
    total = sum(added)
    if total >= ONE_SHOT_MIN_ADDED and max(added) / total > ONE_SHOT_SHARE:
        share = round(100 * max(added) / total)
        return FlagResult(
            "one_shot_dump",
            f"{share}% of the sampled code in {repo.name} arrived in a single commit. Worth asking "
            "how it was built.",
            repo=repo.full_name,
        )
    return None


def unexplained_bulk(repo: Repo) -> FlagResult | None:
    for commit in repo.sampled_commits:
        if (commit.additions or 0) >= BULK_MIN_ADDED:
            later = sum(1 for c in repo.user_commits if c.date > commit.date)
            if later < BULK_MIN_FOLLOW_UPS:
                return FlagResult(
                    "unexplained_bulk",
                    f"One commit in {repo.name} added {commit.additions:,} lines with "
                    f"{later} commit{'s' if later != 1 else ''} after it. Check whether it was "
                    "imported or generated.",
                    repo=repo.full_name,
                )
    return None


def tutorial_clone(repo: Repo) -> FlagResult | None:
    commits = repo.user_commit_count or len(repo.user_commits)
    if TUTORIAL_PATTERN.search(repo.name) and commits < TUTORIAL_MAX_COMMITS:
        return FlagResult(
            "tutorial_clone",
            f"{repo.name} looks like a common tutorial project with {commits} "
            f"commit{'s' if commits != 1 else ''}. Ask what was changed from the tutorial.",
            repo=repo.full_name,
        )
    return None


def repo_flags(repos: Iterable[Repo]) -> list[FlagResult]:
    flags = []
    for repo in repos:
        if repo.is_fork:
            continue
        flag = one_shot_dump(repo) or unexplained_bulk(repo) or tutorial_clone(repo)
        if flag:
            flags.append(flag)
    return flags


def claim_flags(unverified_claims: Sequence[str]) -> list[FlagResult]:
    return [
        FlagResult(
            "unverified_claim",
            f"{claim} is listed on the CV but no public code shows it yet. It may be private "
            "work; ask for an example.",
            claim=claim,
        )
        for claim in unverified_claims
    ]
