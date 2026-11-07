"""Step 2 and 3: which skills each repo shows, and how confident we are (brief 8.2–8.3).

Pure. Catalogue data (language aliases, dependency mappings) is passed in as plain dicts, so the
rules can be tested without a database and admins can still change mappings at runtime.

    span(repo)     = 1.0 if ≥ 30 days between the user's first and last commit; 0.6 if ≥ 7; else 0.3
    evidence(repo) = min(1, user_commits / 20) × span(repo)
    evidence(skill)= Σ evidence(repo) over repos showing the skill (2 dp)
    label          = strong ≥ 2.0 · moderate ≥ 0.8 · emerging > 0 · unverified = 0
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from . import manifests
from .types import Repo, SkillResult

LANGUAGE_MIN_SHARE = 0.05
COMMITS_FOR_FULL_EVIDENCE = 20
STRONG, MODERATE = 2.0, 0.8

TESTING, CI_CD, DOCKER, NODE = "Testing", "CI/CD", "Docker", "Node.js"
IMPLIES = {"Express": (NODE,), "NestJS": (NODE,)}

_TEST_PATTERNS = [
    re.compile(p)
    for p in (
        r"(^|/)tests?/",
        r"(^|/)__tests__/",
        r"(^|/)test_[^/]+\.py$",
        r"(^|/)[^/]+_test\.(py|go)$",
        r"\.test\.[jt]sx?$",
        r"\.spec\.[jt]sx?$",
    )
]
_DOCKER_FILES = {
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yaml",
    "compose.yml",
}


@dataclass(frozen=True)
class Catalogue:
    """language_aliases: lowercase GitHub language name → skill name.
    dependencies: (ecosystem, normalised package) → skill name."""

    language_aliases: Mapping[str, str]
    dependencies: Mapping[tuple[str, str], str]


# --- Repo-level facts ---


def has_tests(repo: Repo) -> bool:
    return any(p.search(path) for path in repo.tree_paths for p in _TEST_PATTERNS)


def has_ci(repo: Repo) -> bool:
    return any(
        path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml"))
        for path in repo.tree_paths
    )


def has_docker(repo: Repo) -> bool:
    return any(path.rsplit("/", 1)[-1].lower() in _DOCKER_FILES for path in repo.tree_paths)


def has_env_example(repo: Repo) -> bool:
    return any(path.rsplit("/", 1)[-1] == ".env.example" for path in repo.tree_paths)


def span_factor(repo: Repo) -> float:
    first, last = repo.first_commit_at, repo.last_commit_at
    if first is None or last is None:
        return 0.3
    days = (last - first).days
    if days >= 30:
        return 1.0
    if days >= 7:
        return 0.6
    return 0.3


def repo_evidence(repo: Repo) -> float:
    commits = repo.user_commit_count or len(repo.user_commits)
    return min(1.0, commits / COMMITS_FOR_FULL_EVIDENCE) * span_factor(repo)


def label_for(evidence: float) -> str:
    if evidence >= STRONG:
        return "strong"
    if evidence >= MODERATE:
        return "moderate"
    if evidence > 0:
        return "emerging"
    return "unverified"


def round_evidence(value: float) -> float:
    """2 dp, half up (0.015 → 0.02), like the sub-scores. Python's round() would give 0.01:
    it rounds halves to even and 0.015 is stored as 0.01499…"""
    return float(Decimal(repr(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# --- Detection ---


def skills_in_repo(repo: Repo, catalogue: Catalogue) -> set[str]:
    found: set[str] = set()
    total_bytes = sum(repo.languages.values())
    for language, size in repo.languages.items():
        if total_bytes and size / total_bytes >= LANGUAGE_MIN_SHARE:
            skill = catalogue.language_aliases.get(language.lower())
            if skill:
                found.add(skill)
    for ecosystem, names in manifests.dependencies(repo.manifests).items():
        for name in names:
            skill = catalogue.dependencies.get((ecosystem, name))
            if skill:
                found.add(skill)
    for skill in list(found):
        found.update(IMPLIES.get(skill, ()))
    if has_tests(repo):
        found.add(TESTING)
    if has_ci(repo):
        found.add(CI_CD)
    if has_docker(repo):
        found.add(DOCKER)
    return found


def detect(repos: Iterable[Repo], catalogue: Catalogue) -> list[SkillResult]:
    """Skills across all original repos, strongest first. Forks never count."""
    evidence: dict[str, float] = {}
    repos_for: dict[str, list[str]] = {}
    for repo in repos:
        if repo.is_fork:
            continue
        weight = repo_evidence(repo)
        for skill in skills_in_repo(repo, catalogue):
            evidence[skill] = evidence.get(skill, 0.0) + weight
            repos_for.setdefault(skill, []).append(repo.full_name)
    results = [
        SkillResult(
            name=name,
            evidence=round_evidence(value),
            label=label_for(round_evidence(value)),
            repos=tuple(repos_for[name]),
        )
        for name, value in evidence.items()
    ]
    return sorted(results, key=lambda s: (-s.evidence, s.name))
