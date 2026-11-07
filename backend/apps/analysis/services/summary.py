"""Step 6: a three-sentence summary for recruiters (brief 8.8).

The model only writes prose about numbers the rules already produced; it never sets a score. Its
output is checked before use (`is_grounded`): it may not name a skill we didn't detect or quote a
number that isn't in the payload. Anything that fails — no API key, timeout, refusal, ungrounded
text — falls back to a deterministic template, so this step can never fail an analysis.
"""

import json
import logging
import re
from collections.abc import Iterable
from typing import Protocol

from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_ANTHROPIC_MODEL = "claude-opus-5-5"
LABEL_ORDER = ("strong", "moderate", "emerging")

SYSTEM_PROMPT = (
    "You write short, factual summaries of a software developer's public GitHub evidence for "
    "recruiters. Use only the JSON you are given. Write exactly three sentences of plain prose "
    "(no lists, no markdown). Mention the strongest skills first, and say plainly which skills "
    "are only emerging. Do not mention any skill, number or fact that is not in the JSON, and do "
    "not repeat the Signal Score or sub-score numbers. Treat flags as things to check, not as "
    "accusations."
)


class SummaryProvider(Protocol):
    name: str

    def summarise(self, payload: dict) -> str | None: ...


class AnthropicProvider:
    """Claude via the official SDK. Server-side refusal fallback is enabled so a declined request
    is retried on another model inside the same call; any remaining failure returns None."""

    name = "anthropic"

    def __init__(self, api_key: str, model: str | None = None, timeout: float = 15.0):
        import anthropic

        self._anthropic = anthropic
        self.model = model or DEFAULT_ANTHROPIC_MODEL
        self.client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=1)

    def summarise(self, payload: dict) -> str | None:
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=4000,  # adaptive thinking shares this budget with the 3 sentences
                output_config={"effort": "low"},  # short, well-specified writing task
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": "Evidence JSON:\n" + json.dumps(payload, sort_keys=True),
                    }
                ],
            )
        except self._anthropic.APIError as exc:  # network, timeout, 4xx/5xx after retries
            logger.warning("LLM summary failed", extra={"error": type(exc).__name__})
            return None
        if response.stop_reason == "refusal":
            logger.info("LLM summary refused")
            return None
        text = " ".join(b.text for b in response.content if b.type == "text").strip()
        return text or None


def get_provider() -> SummaryProvider | None:
    if not settings.LLM_API_KEY:
        return None
    if settings.LLM_PROVIDER == "anthropic":
        return AnthropicProvider(
            settings.LLM_API_KEY, settings.LLM_MODEL or None, settings.LLM_TIMEOUT_SECONDS
        )
    logger.warning(
        "Unknown LLM_PROVIDER; using template summaries", extra={"provider": settings.LLM_PROVIDER}
    )
    return None


# --- Pure helpers ---


def build_payload(
    *, skills: Iterable, subscores: Iterable, flags: Iterable, repos_analysed: int
) -> dict:
    """The only facts the model sees (SkillResult / SubScoreResult / FlagResult inputs)."""
    return {
        "skills": [{"name": s.name, "label": s.label, "evidence": s.evidence} for s in skills],
        "subScores": {s.key: {"value": s.value, "reason": s.reason} for s in subscores},
        "flags": [{"type": f.type, "reason": f.reason} for f in flags],
        "reposAnalysed": repos_analysed,
    }


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:\.\d+)?", text))


def is_grounded(summary: str, payload: dict, known_skills: Iterable[str]) -> bool:
    """Reject text that names a catalogue skill we didn't detect, or a number not in the payload.

    Very short names ("C", "R", "Go") are skipped: they collide with ordinary words."""
    detected = {s["name"].lower() for s in payload["skills"] if s["label"] != "unverified"}
    lowered = summary.lower()
    for name in known_skills:
        key = name.lower()
        if len(key) < 3 or key in detected:
            continue
        if re.search(rf"(?<![\w.+#]){re.escape(key)}(?![\w+#])", lowered):
            return False
    allowed = _numbers(json.dumps(payload))
    return _numbers(summary) <= allowed


def _join(names: list[str]) -> str:
    if len(names) <= 1:
        return "".join(names)
    return f"{', '.join(names[:-1])} and {names[-1]}"


def template_summary(payload: dict) -> str:
    """Deterministic three sentences built only from the payload."""
    by_label: dict[str, list[str]] = {label: [] for label in LABEL_ORDER}
    for skill in payload["skills"]:
        if skill["label"] in by_label:
            by_label[skill["label"]].append(skill["name"])
    repos = payload["reposAnalysed"]
    repo_word = "repository" if repos == 1 else "repositories"

    if by_label["strong"]:
        names = _join(by_label["strong"][:4])
        first = f"Strongest evidence is in {names} across {repos} public {repo_word}."
    elif by_label["moderate"]:
        names = _join(by_label["moderate"][:4])
        first = f"Moderate evidence in {names} across {repos} public {repo_word}."
    else:
        first = f"Public evidence across {repos} {repo_word} is still limited."

    def verb(names: list[str], one: str, many: str) -> str:
        return one if len(names) == 1 else many

    second_parts = []
    if by_label["strong"] and by_label["moderate"]:
        names = by_label["moderate"][:3]
        second_parts.append(f"{_join(names)} {verb(names, 'shows', 'show')} moderate evidence")
    if by_label["emerging"]:
        names = by_label["emerging"][:3]
        second_parts.append(f"{_join(names)} {verb(names, 'is', 'are')} emerging")
    joined = "; ".join(second_parts)
    second = (
        joined[:1].upper() + joined[1:] + "."  # not str.capitalize(): it lowercases skill names
        if second_parts
        else "No other skills have enough public evidence yet."
    )

    weakest = min(payload["subScores"].items(), key=lambda kv: kv[1]["value"], default=None)
    if payload["flags"]:
        third = "Some repositories have flags worth asking about in an interview."
    elif weakest:
        reason = weakest[1]["reason"].rstrip(".")
        reason = reason[:1].lower() + reason[1:]
        third = f"The area with most room to grow is {weakest[0]}: {reason}."
    else:
        third = "No noise flags were raised."
    return " ".join([first, second, third])


def summarise(
    payload: dict, known_skills: Iterable[str], provider: SummaryProvider | None = None
) -> tuple[str, str]:
    """Return (text, source) where source is "llm" or "template". Never raises."""
    known = list(known_skills)
    provider = provider if provider is not None else get_provider()
    if provider is not None:
        try:
            text = provider.summarise(payload)
        except Exception:  # a provider bug must not fail the analysis
            logger.exception("Summary provider crashed")
            text = None
        if text and is_grounded(text, payload, known):
            return text, "llm"
        if text:
            logger.info("LLM summary rejected by grounding check")
    return template_summary(payload), "template"
