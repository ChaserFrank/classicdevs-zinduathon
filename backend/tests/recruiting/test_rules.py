"""Brief 8.7 match score and section 10 feedback hygiene. Pure."""

import pytest

from apps.recruiting.services import moderation
from apps.recruiting.services.match import Requirement, credit, match


@pytest.mark.parametrize(
    ("label", "minimum", "expected"),
    [
        ("strong", "strong", 1.0),
        ("strong", "emerging", 1.0),
        ("moderate", "strong", 0.5),
        ("emerging", "strong", 0.0),
        ("emerging", "moderate", 0.5),
        ("emerging", "emerging", 1.0),
        (None, "emerging", 0.0),  # absent: no half credit even one level below
        ("unverified", "emerging", 0.0),
        (None, "moderate", 0.0),
    ],
)
def test_credit(label, minimum, expected):
    assert credit(label, minimum) == expected


def test_weighted_score_and_buckets():
    reqs = [
        Requirement("Python", "moderate", 3),
        Requirement("Django", "strong", 2),
        Requirement("Docker", "emerging", 1),
    ]
    result = match(reqs, {"Python": "strong", "Django": "moderate"})
    # (3×1 + 2×0.5 + 1×0) / 6 × 100 = 66.67 → 67
    assert result.score == 67
    assert (result.met, result.partial, result.missing) == (("Python",), ("Django",), ("Docker",))


def test_perfect_and_zero():
    reqs = [Requirement("Go", "emerging", 1)]
    assert match(reqs, {"Go": "emerging"}).score == 100
    assert match(reqs, {}).score == 0


def test_half_rounds_up():
    reqs = [
        Requirement("A", "strong", 1),
        Requirement("B", "strong", 1),
        Requirement("C", "strong", 1),
        Requirement("D", "strong", 1),
        Requirement("E", "strong", 1),
        Requirement("F", "strong", 1),
        Requirement("G", "strong", 1),
        Requirement("H", "strong", 1),
    ]
    # 1 half credit of 8 → 6.25; 5 met of 8 → 62.5 → 63
    labels = dict.fromkeys("ABCDE", "strong")
    assert match(reqs, labels).score == 63


def test_no_requirements():
    assert match([], {"Python": "strong"}).score == 0


class TestModeration:
    def test_strips_html_and_whitespace(self):
        result = moderation.clean("<p>Hello <b>there</b></p>\n\n\n\n<script>x</script>Bye   now")
        assert result.message == "Hello there\n\nxBye now"
        assert result.hold_reason == ""

    @pytest.mark.parametrize("text", ["", "   ", "<br>"])
    def test_empty(self, text):
        with pytest.raises(moderation.FeedbackRejected, match="Write a message"):
            moderation.clean(text)

    def test_max_length_after_cleaning(self):
        assert moderation.clean("a" * 1000).message == "a" * 1000
        with pytest.raises(moderation.FeedbackRejected, match="1000"):
            moderation.clean("a" * 1001)
        assert moderation.clean("<b>" * 50 + "a" * 990).message == "a" * 990

    @pytest.mark.parametrize(
        "text",
        ["See http://evil.example", "javascript:alert(1)", "FTP://x.y/z", "data:text/html,hi"],
    )
    def test_non_https_links_rejected(self, text):
        with pytest.raises(moderation.FeedbackRejected, match="https"):
            moderation.clean(text)

    @pytest.mark.parametrize(
        "text",
        [
            "Portfolio: https://example.com/a?b=c",
            "Call at 10:30, note: bring CV",
            "www.example.com",
        ],
    )
    def test_allowed(self, text):
        assert moderation.clean(text).hold_reason == ""

    @pytest.mark.parametrize("text", ["Your code is garbage", "wewe ni mjinga", "What an IDIOT"])
    def test_abuse_is_held_not_rejected(self, text):
        assert moderation.clean(text).hold_reason.startswith("Contains flagged language")

    def test_word_boundaries(self):
        assert moderation.clean("Great at scrapping and classifying data").hold_reason == ""
