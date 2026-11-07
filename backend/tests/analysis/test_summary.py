from types import SimpleNamespace
from unittest import mock

import pytest

from apps.analysis.services import summary
from apps.analysis.services.types import FlagResult, SkillResult, SubScoreResult

KNOWN = ["Python", "Django", "React", "TypeScript", "Go", "C", "Kubernetes", "Node.js", "C++"]


def payload(flags=()):
    return summary.build_payload(
        skills=[
            SkillResult("Python", 2.4, "strong", ()),
            SkillResult("Django", 1.2, "moderate", ()),
            SkillResult("React", 0.3, "emerging", ()),
        ],
        subscores=[
            SubScoreResult("consistency", 15, "Active in 20 of the last 52 weeks"),
            SubScoreResult("quality", 6, "Has CI; missing tests"),
        ],
        flags=list(flags),
        repos_analysed=4,
    )


class FakeProvider:
    name = "fake"

    def __init__(self, text=None, exc=None):
        self.text, self.exc = text, exc

    def summarise(self, data):
        if self.exc:
            raise self.exc
        return self.text


GOOD = "Strong Python work across 4 repositories, with Django close behind. React is emerging. Worth asking about testing."


def test_grounded_text_is_used():
    assert summary.summarise(payload(), KNOWN, FakeProvider(GOOD)) == (GOOD, "llm")


@pytest.mark.parametrize(
    "text",
    [
        "Strong Python and Kubernetes skills.",  # undetected skill
        "Strong Python; scored 99 overall.",  # number not in payload
        "Uses node.js on the backend.",  # alias-like canonical name with dot
    ],
)
def test_ungrounded_text_falls_back_to_template(text):
    result, source = summary.summarise(payload(), KNOWN, FakeProvider(text))
    assert source == "template"
    assert result == summary.template_summary(payload())


def test_short_skill_names_do_not_cause_false_rejections():
    text = "Python is strong. Go ahead and ask about Django. React is emerging."
    assert summary.is_grounded(text, payload(), KNOWN)


def test_names_inside_other_words_are_not_matched():
    assert summary.is_grounded("Python projects using Djangoesque style.", payload(), ["Django2"])


def test_provider_failure_or_crash_falls_back():
    assert summary.summarise(payload(), KNOWN, FakeProvider(None))[1] == "template"
    assert summary.summarise(payload(), KNOWN, FakeProvider(exc=RuntimeError("x")))[1] == "template"


def test_no_provider_configured(settings):
    settings.LLM_API_KEY = ""
    assert summary.get_provider() is None
    assert summary.summarise(payload(), KNOWN)[1] == "template"


def test_unknown_provider(settings):
    settings.LLM_API_KEY = "k"
    settings.LLM_PROVIDER = "other"
    assert summary.get_provider() is None


def test_anthropic_provider_selected(settings):
    settings.LLM_API_KEY = "k"
    settings.LLM_PROVIDER = "anthropic"
    settings.LLM_MODEL = ""
    provider = summary.get_provider()
    assert provider.model == "claude-opus-5-5"


class TestAnthropicProvider:
    def provider(self):
        return summary.AnthropicProvider("test-key")

    def test_request_shape_and_text(self):
        provider = self.provider()
        reply = SimpleNamespace(
            stop_reason="end_turn",
            content=[
                SimpleNamespace(type="thinking"),
                SimpleNamespace(type="text", text=" Hello. "),
            ],
        )
        with mock.patch.object(
            provider.client.beta.messages, "create", return_value=reply
        ) as create:
            assert provider.summarise({"skills": []}) == "Hello."
        kwargs = create.call_args.kwargs
        assert kwargs["model"] == "claude-opus-5-5"
        assert kwargs["fallbacks"] == "default"
        assert kwargs["betas"] == ["server-side-fallback-2026-07-01"]
        assert kwargs["output_config"] == {"effort": "low"}
        assert "thinking" not in kwargs and "temperature" not in kwargs
        assert kwargs["messages"][0]["content"].startswith("Evidence JSON:")

    def test_refusal_returns_none(self):
        provider = self.provider()
        reply = SimpleNamespace(stop_reason="refusal", content=[])
        with mock.patch.object(provider.client.beta.messages, "create", return_value=reply):
            assert provider.summarise({}) is None

    def test_api_error_returns_none(self):
        import anthropic

        provider = self.provider()
        error = anthropic.APIConnectionError(request=mock.Mock())
        with mock.patch.object(provider.client.beta.messages, "create", side_effect=error):
            assert provider.summarise({}) is None


class TestTemplate:
    def test_three_sentences_from_payload_only(self):
        text = summary.template_summary(payload())
        assert text == (
            "Strongest evidence is in Python across 4 public repositories. "
            "Django shows moderate evidence; React is emerging. "
            "The area with most room to grow is quality: has CI; missing tests."
        )
        assert summary.is_grounded(text, payload(), KNOWN)

    def test_with_flags_and_no_strong(self):
        data = summary.build_payload(
            skills=[SkillResult("HTML", 0.2, "emerging", ())],
            subscores=[],
            flags=[FlagResult("tutorial_clone", "x", "a/b")],
            repos_analysed=1,
        )
        text = summary.template_summary(data)
        assert text.startswith("Public evidence across 1 repository is still limited.")
        assert "flags worth asking about" in text

    def test_moderate_only_and_nothing_else(self):
        data = summary.build_payload(
            skills=[SkillResult("Go", 1.0, "moderate", ())],
            subscores=[],
            flags=[],
            repos_analysed=2,
        )
        assert summary.template_summary(data) == (
            "Moderate evidence in Go across 2 public repositories. "
            "No other skills have enough public evidence yet. No noise flags were raised."
        )
