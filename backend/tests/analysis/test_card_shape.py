"""Snapshot of the card contract (brief 7.1 / frontend lib/types.ts). If this fails, the frontend
breaks: change the contract deliberately and tell the frontend team."""

import pytest
import responses
from freezegun import freeze_time

from apps.analysis.cards import build_card
from apps.analysis.models import Analysis
from apps.analysis.services import pipeline
from tests.fixtures.github.fake import load_persona, register_persona

pytestmark = pytest.mark.django_db

CARD_KEYS = [
    "username",
    "profile",
    "signalScore",
    "subScores",
    "skills",
    "claims",
    "flags",
    "aiSummary",
    "reposAnalysed",
    "commitsAnalysed",
    "analysedAt",
]
PROFILE_KEYS = ["username", "name", "avatarUrl", "verifiedOwner"]
SKILL_KEYS = ["name", "category", "label", "evidence", "repos"]
REPO_KEYS = ["name", "url", "commits", "firstCommit", "lastCommit", "hasTests", "hasCI"]


@pytest.fixture
def card(api_client):
    with freeze_time("2026-11-07 12:00"):
        analysis = Analysis.objects.create(github_login="amina-dev")
        with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
            register_persona(rsps, load_persona("amina-dev"))
            pipeline.run(analysis)
    # Through the real renderer: camel-casing must not turn hasCI into hasCi.
    return api_client.get("/api/v1/cards/amina-dev").json()


def test_exact_keys(card):
    assert list(card) == CARD_KEYS
    assert list(card["profile"]) == PROFILE_KEYS
    assert list(card["subScores"]) == [
        "consistency",
        "iteration",
        "quality",
        "breadth",
        "ownership",
    ]
    for sub in card["subScores"].values():
        assert list(sub) == ["value", "reason"] and 0 <= sub["value"] <= 20
    for skill in card["skills"]:
        assert list(skill) == SKILL_KEYS
        for repo in skill["repos"]:
            assert list(repo) == REPO_KEYS
    for claim in card["claims"]:
        assert list(claim) == ["skill", "status"]
    for flag in card["flags"]:
        assert set(flag) <= {"type", "repo", "reason"}


def test_value_casing_and_types(card):
    assert {s["category"] for s in card["skills"]} <= {"Language", "Framework", "Practice", "Tool"}
    assert {s["label"] for s in card["skills"]} <= {"Strong", "Moderate", "Emerging", "Unverified"}
    assert all(isinstance(s["evidence"], float) for s in card["skills"])
    assert isinstance(card["signalScore"], int)
    assert card["signalScore"] == sum(s["value"] for s in card["subScores"].values())
    assert card["analysedAt"].startswith("2026-11-07")
    assert card["profile"]["verifiedOwner"] is False  # no linked GithubAccount
    assert card["flags"][0] == {
        "type": "one_shot_dump",
        "reason": card["flags"][0]["reason"],
        "repo": "matatu-routes",
    }


def test_skills_sorted_by_evidence(card):
    evidence = [s["evidence"] for s in card["skills"]]
    assert evidence == sorted(evidence, reverse=True)


def test_builder_handles_empty_analysis():
    analysis = Analysis.objects.create(github_login="x", status="completed")
    card = build_card(analysis)
    assert card["skills"] == [] and card["subScores"] == {} and card["profile"]["name"] is None
    assert card["profile"]["avatarUrl"] == "https://github.com/x.png"
