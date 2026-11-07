"""Brief 8.4: the five sub-scores and the Signal Score. Pure."""

from datetime import timedelta

import pytest

from apps.analysis.services import scores
from apps.analysis.services.types import Commit, SkillResult
from tests.analysis.builders import NOW, commits, repo


def weekly(n_weeks: int, start_days_ago: int = 364):
    start = NOW - timedelta(days=start_days_ago)
    return [Commit(f"w{i}", start + timedelta(weeks=i)) for i in range(n_weeks)]


class TestRounding:
    @pytest.mark.parametrize(
        ("value", "expected"), [(10.5, 11), (10.49, 10), (-3, 0), (25, 20), (0, 0)]
    )
    def test_round_half_up_and_clamp(self, value, expected):
        assert scores._round(value) == expected


class TestConsistency:
    @pytest.mark.parametrize(("weeks", "value"), [(0, 0), (13, 10), (26, 20), (40, 20), (1, 1)])
    def test_weeks(self, weeks, value):
        result = scores.consistency([repo(user_commits=weekly(weeks))], NOW)
        assert result.value == value
        assert result.reason == f"Active in {weeks} of the last 52 weeks"

    def test_commits_older_than_a_year_ignored(self):
        old = [Commit("o", NOW - timedelta(days=400))]
        assert scores.consistency([repo(user_commits=old)], NOW).value == 0

    def test_same_week_across_repos_counts_once(self):
        c = [Commit("a", NOW - timedelta(days=3))]
        assert (
            "Active in 1 "
            in scores.consistency(
                [repo("a", user_commits=c), repo("b", user_commits=c)], NOW
            ).reason
        )

    def test_forks_ignored(self):
        assert scores.consistency([repo(user_commits=weekly(30), fork=True)], NOW).value == 0


class TestIteration:
    def test_no_original_repos(self):
        assert scores.iteration([]).value == 0

    @pytest.mark.parametrize(("size", "points"), [(200, 8), (201, 5), (500, 5), (501, 2)])
    def test_median_commit_size_bands(self, size, points):
        # 3 commits per repo: no repo has 10+ commits; equal sizes → no single commit dominates
        r = repo(user_commits=commits(3, additions=size, deletions=0))
        assert scores.iteration([r]).value == points

    def test_nothing_sampled_gives_zero_size_points(self):
        assert scores.iteration([repo(user_commits=commits(3))]).value == 0

    def test_sustained_repos_add_up_to_twelve(self):
        busy = repo("a", user_commits=commits(10, additions=50))
        quiet = repo("b", user_commits=commits(2, additions=50))
        # median 50 → 8; 12 × 1/2 = 6 → 14
        assert scores.iteration([busy, quiet]).value == 14

    def test_dominated_repos_subtract(self):
        dumped = repo("d", user_commits=[Commit("x", NOW, 900, 0), Commit("y", NOW, 100, 0)])
        assert scores.dominant_commit_share(dumped) == 0.9
        # median 500 → 5; 0 sustained; − 6 × 1/1 → clamp 0
        assert scores.iteration([dumped]).value == 0

    def test_exactly_half_is_not_dominated(self):
        r = repo(user_commits=[Commit("x", NOW, 100, 0), Commit("y", NOW, 100, 0)])
        assert scores.dominant_commit_share(r) == 0.5
        assert scores.iteration([r]).value == 8

    def test_capped_at_twenty(self):
        r = repo(user_commits=commits(30, additions=10))
        assert scores.iteration([r]).value == 20

    def test_reason_mentions_counts(self):
        reason = scores.iteration([repo(user_commits=commits(10, additions=40))]).reason
        assert reason.startswith("Median commit 40 lines; 1 of 1 repo with 10+ commits")


class TestQuality:
    def test_nothing(self):
        result = scores.quality([repo()])
        assert (result.value, result.reason) == (0, "No tests, CI, README or Docker setup found")

    def test_each_part(self):
        assert scores.quality([repo(tree=["tests/test_a.py"])]).value == 8
        assert scores.quality([repo(tree=[".github/workflows/ci.yml"])]).value == 6
        assert scores.quality([repo(readme=301)]).value == 3
        assert scores.quality([repo(readme=300)]).value == 0
        assert scores.quality([repo(tree=["Dockerfile"])]).value == 3
        assert scores.quality([repo(tree=[".env.example"])]).value == 3

    def test_parts_can_come_from_different_repos(self):
        result = scores.quality(
            [
                repo("a", tree=["tests/t.py"]),
                repo("b", tree=[".github/workflows/x.yaml", "Dockerfile"], readme=900),
            ]
        )
        assert result.value == 20
        assert result.reason == "Has tests, CI, a README and Docker or .env.example"

    def test_partial_reason(self):
        assert scores.quality([repo(tree=["tests/t.py"])]).reason == (
            "Has tests; missing CI, a README, Docker or .env.example"
        )

    def test_forks_ignored(self):
        assert scores.quality([repo(tree=["tests/t.py"], fork=True)]).value == 0


class TestBreadth:
    def skills(self, strong, moderate, emerging=0):
        return (
            [SkillResult(f"s{i}", 2.5, "strong", ()) for i in range(strong)]
            + [SkillResult(f"m{i}", 1, "moderate", ()) for i in range(moderate)]
            + [SkillResult(f"e{i}", 0.1, "emerging", ()) for i in range(emerging)]
        )

    @pytest.mark.parametrize(
        ("strong", "moderate", "value"),
        [(0, 0, 0), (1, 0, 4), (0, 1, 2), (3, 2, 16), (4, 3, 20), (6, 0, 20)],
    )
    def test_points(self, strong, moderate, value):
        assert scores.breadth(self.skills(strong, moderate, emerging=5)).value == value

    def test_reason(self):
        assert scores.breadth(self.skills(1, 2)).reason == "1 strong skill, 2 moderate"


class TestOwnership:
    def test_no_repos(self):
        assert scores.ownership([]).value == 0

    @pytest.mark.parametrize(
        ("mine", "total", "owned"), [(7, 10, True), (69, 100, False), (5, 5, True), (0, 10, False)]
    )
    def test_seventy_percent_threshold(self, mine, total, owned):
        r = repo(user_commits=commits(mine), total=total)
        assert scores.ownership([r]).value == (20 if owned else 0)

    def test_share_of_repos(self):
        mine = repo("a", user_commits=commits(9), total=10)
        theirs = repo("b", user_commits=commits(1), total=10)
        result = scores.ownership([mine, theirs])
        assert result.value == 10
        assert result.reason == "Wrote most of the commits in 1 of 2 original repos"

    def test_total_never_below_user_commits(self):
        assert scores.ownership([repo(user_commits=commits(5), total=0)]).value == 20


def test_signal_score_is_sum_of_subscores():
    r = repo(
        user_commits=weekly(26, start_days_ago=200),
        tree=["tests/t.py", ".github/workflows/ci.yml", "Dockerfile"],
        readme=1000,
    )
    total, subs = scores.score([r], [SkillResult("Python", 2.0, "strong", ())], NOW)
    assert [s.key for s in subs] == list(scores.KEYS)
    assert total == sum(s.value for s in subs)
    assert all(0 <= s.value <= 20 for s in subs)
    assert 0 <= total <= 100
