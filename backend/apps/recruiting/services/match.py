"""Job match score (brief 8.7). Pure.

    match = Σ weight × credit / Σ weight × 100
    credit = 1.0 if the candidate's label meets the minimum, 0.5 if one level below, else 0

"One level below" needs a detected skill: a skill we found no evidence for (absent or
Unverified) earns nothing, even when the minimum is Emerging.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

RANK = {"unverified": 0, "emerging": 1, "moderate": 2, "strong": 3}


@dataclass(frozen=True)
class Requirement:
    skill: str
    minimum_label: str
    weight: int = 1


@dataclass(frozen=True)
class MatchResult:
    score: int  # 0–100
    met: tuple[str, ...]
    partial: tuple[str, ...]  # one level below the minimum: half credit
    missing: tuple[str, ...]


def credit(label: str | None, minimum: str) -> float:
    have = RANK.get(label or "unverified", 0)
    need = RANK[minimum]
    if have == 0:
        return 0.0
    if have >= need:
        return 1.0
    if have == need - 1:
        return 0.5
    return 0.0


def match(requirements: Sequence[Requirement], labels: Mapping[str, str]) -> MatchResult:
    """`labels`: the candidate's skill name → label (lowercase)."""
    if not requirements:
        return MatchResult(0, (), (), ())
    total = sum(r.weight for r in requirements)
    earned, met, partial, missing = 0.0, [], [], []
    for req in requirements:
        c = credit(labels.get(req.skill), req.minimum_label)
        earned += req.weight * c
        (met if c == 1.0 else partial if c == 0.5 else missing).append(req.skill)
    score = math.floor(earned / total * 100 + 0.5)
    return MatchResult(score, tuple(met), tuple(partial), tuple(missing))
