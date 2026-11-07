"""Tiny builders for pure-rule tests."""

from datetime import UTC, datetime, timedelta

from apps.analysis.services.types import Commit, Repo

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


def commits(
    n: int, *, start: datetime | None = None, every_days: float = 1, additions=None, deletions=0
):
    """n commits, oldest at `start`; additions=None means not sampled."""
    start = start or NOW - timedelta(days=n * every_days)
    return [
        Commit(
            sha=f"c{i}",
            date=start + timedelta(days=i * every_days),
            additions=additions,
            deletions=deletions if additions is not None else None,
        )
        for i in range(n)
    ]


def repo(
    name="app",
    *,
    user_commits=None,
    total=None,
    tree=(),
    languages=None,
    manifests=None,
    readme=0,
    fork=False,
    gid=None,
):
    user_commits = list(user_commits or [])
    return Repo(
        github_id=gid if gid is not None else abs(hash(name)) % 10_000_000,
        owner="dev",
        name=name,
        html_url=f"https://github.com/dev/{name}",
        is_fork=fork,
        languages=languages or {},
        user_commits=user_commits,
        user_commit_count=len(user_commits),
        total_commits=total if total is not None else len(user_commits),
        tree_paths=list(tree),
        manifests=manifests or {},
        readme_size=readme,
    )
