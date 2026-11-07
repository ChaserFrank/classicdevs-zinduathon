"""Brief 8.5, 8.6, 8.9: flags, claims, tips. Pure."""

from datetime import timedelta

import pytest

from apps.analysis.services import claims, flags, tips
from apps.analysis.services.types import Commit, FlagResult, SubScoreResult
from tests.analysis.builders import NOW, commits, repo


class TestOneShotDump:
    def test_flags_dominant_commit(self):
        r = repo("shop", user_commits=[Commit("a", NOW, 170, 0), Commit("b", NOW, 30, 0)])
        flag = flags.one_shot_dump(r)
        assert flag.type == "one_shot_dump"
        assert flag.repo == "dev/shop"
        assert "85%" in flag.reason and "Worth asking" in flag.reason

    def test_needs_200_added_lines(self):
        assert flags.one_shot_dump(repo(user_commits=[Commit("a", NOW, 199, 0)])) is None
        assert flags.one_shot_dump(repo(user_commits=[Commit("a", NOW, 200, 0)])) is not None

    def test_exactly_80_percent_is_not_flagged(self):
        r = repo(user_commits=[Commit("a", NOW, 160, 0), Commit("b", NOW, 40, 0)])
        assert flags.one_shot_dump(r) is None


class TestUnexplainedBulk:
    def bulk(self, after: int):
        big = Commit("big", NOW - timedelta(days=10), 2000, 0)
        small = [Commit(f"s{i}", NOW - timedelta(days=9 - i), 400, 0) for i in range(after)]
        return repo("lib", user_commits=[big, *small])

    def test_fewer_than_three_follow_ups(self):
        flag = flags.unexplained_bulk(self.bulk(2))
        assert flag.type == "unexplained_bulk"
        assert "2,000 lines with 2 commits after it" in flag.reason

    def test_three_follow_ups_is_fine(self):
        assert flags.unexplained_bulk(self.bulk(3)) is None

    def test_under_2000_lines_is_fine(self):
        r = repo(user_commits=[Commit("a", NOW, 1999, 0)])
        assert flags.unexplained_bulk(r) is None

    def test_one_commit_wording(self):
        assert "1 commit after it" in flags.unexplained_bulk(self.bulk(1)).reason


class TestTutorialClone:
    @pytest.mark.parametrize(
        "name",
        [
            "todo-app",
            "My-ToDo",
            "calculator",
            "weather-app",
            "tic-tac-toe",
            "tictactoe",
            "hello-world",
            "netflix-clone",
            "amazon_clone",
        ],
    )
    def test_names(self, name):
        assert flags.tutorial_clone(repo(name, user_commits=commits(4))) is not None

    def test_five_commits_is_enough_work(self):
        assert flags.tutorial_clone(repo("todo-app", user_commits=commits(5))) is None

    def test_other_names(self):
        assert flags.tutorial_clone(repo("matatu-routes", user_commits=commits(1))) is None


def test_one_flag_per_repo_with_priority():
    # Qualifies as dump, bulk and tutorial at once → only the dump is reported.
    r = repo("todo", user_commits=[Commit("a", NOW, 2500, 0), Commit("b", NOW, 10, 0)])
    result = flags.repo_flags([r])
    assert [f.type for f in result] == ["one_shot_dump"]


def test_forks_are_never_flagged():
    r = repo("todo", user_commits=commits(1), fork=True)
    assert flags.repo_flags([r]) == []


def test_claim_flags_are_prompts_not_accusations():
    [flag] = flags.claim_flags(["Kubernetes"])
    assert flag.type == "unverified_claim" and flag.claim == "Kubernetes"
    assert "ask for an example" in flag.reason


class TestClaims:
    LOOKUP = {
        "react": "React",
        "reactjs": "React",
        "django rest framework": "Django REST Framework",
    }

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("ReactJS", "React"),
            ("  django   REST framework ", "Django REST Framework"),
            ("COBOL", None),
            ("", None),
        ],
    )
    def test_normalise(self, raw, expected):
        assert claims.normalise(raw, self.LOOKUP) == expected

    def test_statuses(self):
        labels = {"React": "strong", "Django": "moderate", "Go": "emerging", "Rust": "unverified"}
        result = claims.check(
            [
                ("React", "React"),
                ("django", "Django"),
                ("golang", "Go"),
                ("rust", "Rust"),
                ("k8s", None),
                ("Vue", "Vue.js"),
            ],
            labels,
        )
        assert result == [
            ("React", "verified"),
            ("django", "verified"),
            ("golang", "partly"),
            ("rust", "unverified"),
            ("k8s", "unverified"),
            ("Vue", "unverified"),
        ]


class TestTips:
    def subs(self, **values):
        defaults = {
            "consistency": 20,
            "iteration": 20,
            "quality": 20,
            "breadth": 20,
            "ownership": 20,
        }
        defaults.update(values)
        return [
            SubScoreResult(k, v, "Active in 3 of the last 52 weeks" if k == "consistency" else "")
            for k, v in defaults.items()
        ]

    def test_nothing_to_suggest(self):
        assert tips.tips_for([repo(readme=1000)], self.subs(), []) == []

    def test_quality_tips_name_the_busiest_repo(self):
        repos = [repo("small", user_commits=commits(2)), repo("shop-app", user_commits=commits(30))]
        result = tips.tips_for(repos, self.subs(quality=0), [])
        assert result == [
            "Add tests to shop-app",
            "Add a GitHub Actions workflow to run shop-app's checks on every push",
            "Add a README to shop-app explaining what it does and how to run it",
        ]

    def test_lowest_subscore_first_and_max_three(self):
        repos = [repo("shop-app", user_commits=commits(3))]
        flag = FlagResult("one_shot_dump", "", "dev/shop-app")
        result = tips.tips_for(
            repos, self.subs(consistency=1, iteration=5, quality=9, ownership=0), [flag, flag]
        )
        assert len(result) == 3
        assert result[0] == "Build a project of your own from scratch and push it"
        assert result[1] == "Commit regularly: active in 3 of the last 52 weeks"
        assert result[2] == "Commit in smaller steps: 2 repos arrived mostly in one commit"

    def test_single_dump_wording(self):
        flag = FlagResult("unexplained_bulk", "", "dev/a")
        result = tips.tips_for([repo(readme=1000)], self.subs(iteration=3), [flag])
        assert result == ["Commit in smaller steps: 1 repo arrived mostly in one commit"]

    def test_tutorial_and_claim_tips(self):
        flagged = [
            FlagResult("tutorial_clone", "", "dev/todo"),
            FlagResult("unverified_claim", "", claim="Kubernetes"),
        ]
        result = tips.tips_for([repo(readme=1000)], self.subs(breadth=2), flagged)
        assert result == [
            "Extend a tutorial project with your own feature and explain it in the README",
            "Publish a small project that uses Kubernetes",
        ]
