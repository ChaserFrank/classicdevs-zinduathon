"""Brief 8.2–8.3: detection, span, evidence, labels. Pure."""

from datetime import timedelta

import pytest

from apps.analysis.services import skills as s
from apps.analysis.services.types import Commit
from tests.analysis.builders import NOW, commits, repo

CATALOGUE = s.Catalogue(
    language_aliases={
        "python": "Python",
        "typescript": "TypeScript",
        "javascript": "JavaScript",
        "jupyter notebook": "Python",
        "css": "CSS",
    },
    dependencies={
        ("npm", "react"): "React",
        ("npm", "express"): "Express",
        ("npm", "@nestjs/core"): "NestJS",
        ("npm", "jest"): "Testing",
        ("pypi", "django"): "Django",
        ("pypi", "psycopg2-binary"): "PostgreSQL",
    },
)


def span_repo(days: int):
    return repo(user_commits=[Commit("a", NOW - timedelta(days=days)), Commit("b", NOW)])


@pytest.mark.parametrize(
    ("days", "expected"),
    [(0, 0.3), (6, 0.3), (7, 0.6), (29, 0.6), (30, 1.0), (400, 1.0)],
)
def test_span_thresholds(days, expected):
    assert s.span_factor(span_repo(days)) == expected


def test_span_with_no_commits():
    assert s.span_factor(repo()) == 0.3


@pytest.mark.parametrize(
    ("n", "every", "expected"),
    [
        (0, 1, 0.0),  # no commits → no evidence
        (10, 5, 0.5 * 1.0),  # 45 days span
        (20, 2, 1.0 * 1.0),  # exactly 20 commits, 38 days
        (40, 1, 1.0 * 1.0),  # capped at 1
        (20, 0.1, 1.0 * 0.3),  # one-week sprint (1.9 days)
        (10, 1, 0.5 * 0.6),  # 9 days → 0.6
    ],
)
def test_repo_evidence(n, every, expected):
    assert s.repo_evidence(repo(user_commits=commits(n, every_days=every))) == pytest.approx(
        expected
    )


@pytest.mark.parametrize(
    ("evidence", "label"),
    [
        (0, "unverified"),
        (0.01, "emerging"),
        (0.79, "emerging"),
        (0.8, "moderate"),
        (1.99, "moderate"),
        (2.0, "strong"),
        (5, "strong"),
    ],
)
def test_labels_on_thresholds(evidence, label):
    assert s.label_for(evidence) == label


def test_language_under_five_percent_ignored():
    r = repo(languages={"Python": 951, "CSS": 49}, user_commits=commits(20, every_days=3))
    assert s.skills_in_repo(r, CATALOGUE) == {"Python"}


def test_language_exactly_five_percent_counts():
    r = repo(languages={"Python": 95, "CSS": 5})
    assert "CSS" in s.skills_in_repo(r, CATALOGUE)


def test_unknown_language_ignored():
    assert s.skills_in_repo(repo(languages={"Makefile": 100}), CATALOGUE) == set()


def test_github_language_alias():
    assert s.skills_in_repo(repo(languages={"Jupyter Notebook": 10}), CATALOGUE) == {"Python"}


def test_manifest_dependencies_and_implied_node():
    r = repo(
        manifests={
            "package.json": '{"dependencies": {"react": "18", "express": "4"}, "devDependencies": {"jest": "29"}}'
        }
    )
    assert s.skills_in_repo(r, CATALOGUE) == {"React", "Express", "Node.js", "Testing"}


def test_nestjs_implies_node():
    r = repo(manifests={"api/package.json": '{"dependencies": {"@nestjs/core": "10"}}'})
    assert s.skills_in_repo(r, CATALOGUE) == {"NestJS", "Node.js"}


def test_pypi_names_are_normalised():
    r = repo(manifests={"requirements.txt": "Django==5\npsycopg2_binary\n"})
    assert s.skills_in_repo(r, CATALOGUE) == {"Django", "PostgreSQL"}


@pytest.mark.parametrize(
    "path",
    [
        "tests/test_x.py",
        "test/a.js",
        "src/__tests__/a.js",
        "pkg/test_models.py",
        "pkg/models_test.py",
        "handler_test.go",
        "src/a.test.ts",
        "src/a.test.tsx",
        "src/a.spec.ts",
        "a.test.js",
    ],
)
def test_testing_practice_paths(path):
    assert s.has_tests(repo(tree=[path]))


@pytest.mark.parametrize("path", ["src/testing.py", "contest/a.py", "latest/a.py", "attest.ts"])
def test_not_test_paths(path):
    assert not s.has_tests(repo(tree=[path]))


def test_ci_and_docker_practices():
    r = repo(tree=[".github/workflows/ci.yml", "deploy/Dockerfile", "compose.yaml"])
    assert s.skills_in_repo(r, CATALOGUE) == {"CI/CD", "Docker"}
    assert not s.has_ci(repo(tree=[".github/workflows/README.md"]))
    assert s.has_env_example(repo(tree=["backend/.env.example"]))


def test_detect_sums_evidence_rounds_and_sorts():
    a = repo("a", languages={"Python": 1}, user_commits=commits(20, every_days=2))  # 1.0
    b = repo(
        "b", languages={"Python": 1}, user_commits=commits(13, every_days=1)
    )  # 0.65 × 0.6 = 0.39
    c = repo("c", languages={"TypeScript": 1}, user_commits=commits(1))  # 0.05 × 0.3 = 0.015
    result = s.detect([c, a, b], CATALOGUE)
    assert [(r.name, r.evidence, r.label) for r in result] == [
        ("Python", 1.39, "moderate"),
        ("TypeScript", 0.02, "emerging"),
    ]
    assert result[0].repos == ("dev/a", "dev/b")


def test_forks_never_count():
    fork = repo("f", languages={"Python": 1}, user_commits=commits(40, every_days=2), fork=True)
    assert s.detect([fork], CATALOGUE) == []


def test_skill_in_repo_without_user_commits_is_unverified():
    result = s.detect([repo(languages={"Python": 1})], CATALOGUE)
    assert result[0].label == "unverified"
    assert result[0].evidence == 0


def test_capped_commit_count_used_for_evidence():
    r = repo(languages={"Python": 1}, user_commits=commits(5, every_days=10))
    r.user_commit_count = 300  # more commits than were fetched
    assert s.repo_evidence(r) == 1.0
