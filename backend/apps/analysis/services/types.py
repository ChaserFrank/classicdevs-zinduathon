"""Plain data passed between pipeline steps. GitHub JSON is converted into these in github.py, so
every rule after that is pure Python that can be unit-tested without HTTP or a database."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Commit:
    sha: str
    date: datetime
    additions: int | None = None  # None unless this commit was in the detail sample
    deletions: int | None = None

    @property
    def sampled(self) -> bool:
        return self.additions is not None

    @property
    def size(self) -> int:
        return (self.additions or 0) + (self.deletions or 0)


@dataclass
class Repo:
    github_id: int
    owner: str
    name: str
    html_url: str
    default_branch: str = "main"
    is_fork: bool = False
    pushed_at: datetime | None = None
    languages: dict[str, int] = field(default_factory=dict)  # GitHub language → bytes
    user_commits: list[Commit] = field(default_factory=list)  # newest first, as GitHub returns
    user_commit_count: int = 0  # may exceed len(user_commits) when GitHub pages were capped
    total_commits: int = 0
    tree_paths: list[str] = field(default_factory=list)
    manifests: dict[str, str] = field(default_factory=dict)  # filename → file text
    readme_size: int = 0

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def sampled_commits(self) -> list[Commit]:
        return [c for c in self.user_commits if c.sampled]

    @property
    def first_commit_at(self) -> datetime | None:
        return min((c.date for c in self.user_commits), default=None)

    @property
    def last_commit_at(self) -> datetime | None:
        return max((c.date for c in self.user_commits), default=None)


@dataclass(frozen=True)
class SubScoreResult:
    key: str
    value: int  # 0–20
    reason: str


@dataclass(frozen=True)
class FlagResult:
    type: str
    reason: str
    repo: str | None = None  # repo full name
    claim: str | None = None  # claimed raw text, for unverified_claim


@dataclass(frozen=True)
class SkillResult:
    name: str
    evidence: float
    label: str  # strong | moderate | emerging | unverified
    repos: tuple[str, ...]  # repo full names
