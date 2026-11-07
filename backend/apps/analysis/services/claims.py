"""Claimed skills vs. evidence (brief 8.6). Pure.

verified = Strong or Moderate · partly = Emerging · unverified = not detected (or no evidence).
"""

from collections.abc import Mapping, Sequence

STATUS_BY_LABEL = {"strong": "verified", "moderate": "verified", "emerging": "partly"}


def normalise(raw: str, lookup: Mapping[str, str]) -> str | None:
    """Map typed text ("reactjs", " Django REST framework ") to a skill name via names/aliases.

    `lookup` maps lowercase skill names and aliases → canonical skill name."""
    key = " ".join((raw or "").lower().split())
    return lookup.get(key)


def check(
    claimed: Sequence[tuple[str, str | None]], labels: Mapping[str, str]
) -> list[tuple[str, str]]:
    """claimed: [(raw_text, skill_name_or_None)], labels: skill name → label.
    Returns [(raw_text, status)] in the same order."""
    results = []
    for raw, skill in claimed:
        label = labels.get(skill) if skill else None
        results.append((raw, STATUS_BY_LABEL.get(label or "", "unverified")))
    return results
