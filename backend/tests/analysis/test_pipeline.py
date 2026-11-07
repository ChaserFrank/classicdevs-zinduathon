"""End-to-end pipeline runs on the persona fixtures (GitHub mocked with `responses`)."""

import pytest
import responses
from freezegun import freeze_time

from apps.analysis.models import Analysis, AnalysisSkill, ClaimedSkill, Flag
from apps.analysis.services import pipeline
from apps.skills.models import Skill
from tests.factories import JobSeekerFactory
from tests.fixtures.github.fake import load_persona, register_persona

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("_frozen")]


@pytest.fixture
def _frozen():
    with freeze_time("2026-11-07 12:00:00"):
        yield


def run_for(login: str, *, job_seeker=None) -> Analysis:
    analysis = Analysis.objects.create(github_login=login, job_seeker=job_seeker)
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        register_persona(rsps, load_persona(login))
        pipeline.run(analysis)
    analysis.refresh_from_db()
    return analysis


def test_amina_full_card():
    profile = JobSeekerFactory().job_seeker_profile
    for i, text in enumerate(["ReactJS", "Kubernetes", "django"]):
        ClaimedSkill.objects.create(
            job_seeker=profile,
            raw_text=text,
            position=i,
            skill=Skill.objects.filter(
                name={"ReactJS": "React", "django": "Django"}.get(text, "")
            ).first(),
        )

    analysis = run_for("amina-demo", job_seeker=profile)

    assert analysis.status == "completed", analysis.error_message
    assert analysis.progress_step == 4
    assert analysis.repos_analysed == 3
    assert analysis.commits_analysed == 44 + 24 + 3
    assert analysis.summary_source == "template"
    skills = {row.skill.name: row.label for row in AnalysisSkill.objects.filter(analysis=analysis)}
    assert skills["TypeScript"] == "moderate"  # 44 commits over 10 months: evidence 1.0
    assert {
        "React",
        "Next.js",
        "Tailwind CSS",
        "Python",
        "Django",
        "Django REST Framework",
        "PostgreSQL",
        "Testing",
        "CI/CD",
        "Docker",
        "JavaScript",
        "Express",
        "Node.js",
    } <= set(skills)
    assert skills["Testing"] == "strong"  # jest + pytest + test paths across two repos: 2.0
    flags = list(Flag.objects.filter(analysis=analysis).values_list("type", flat=True))
    assert sorted(flags) == ["one_shot_dump", "unverified_claim"]
    claims = dict(analysis.claim_results.values_list("claimed_skill__raw_text", "status"))
    assert claims == {"ReactJS": "verified", "Kubernetes": "unverified", "django": "verified"}
    subs = dict(analysis.subscores.values_list("key", "value"))
    assert subs["quality"] == 20
    assert analysis.signal_score == sum(subs.values())
    assert 0 < len(analysis.tips) <= 3


def test_brian_tutorial_flags_and_low_quality():
    analysis = run_for("brian-demo")
    assert analysis.status == "completed"
    flags = dict(
        Flag.objects.filter(analysis=analysis).values_list(
            "analysis_repository__repository__name", "type"
        )
    )
    # todo-app: 300 of 320 sampled lines in one commit → one_shot_dump outranks tutorial_clone
    assert flags == {"todo-app": "one_shot_dump", "weather-app": "tutorial_clone"}
    labels = dict(
        AnalysisSkill.objects.filter(analysis=analysis).values_list("skill__name", "label")
    )
    assert labels["Data analysis"] == "emerging"  # 12 commits over 22 days: 0.6 × 0.6
    assert dict(analysis.subscores.values_list("key", "value"))["quality"] == 3  # README only
    assert any(tip == "Add tests to titanic-analysis" for tip in analysis.tips)


def test_forks_only_fails_with_no_public_repos():
    analysis = run_for("forks-only")
    assert analysis.status == "failed"
    assert analysis.error_code == "no_public_repos"
    assert analysis.signal_score is None


@responses.activate
def test_unknown_user_fails_cleanly():
    responses.get("https://api.github.com/users/nobody", status=404)
    analysis = Analysis.objects.create(github_login="nobody")
    pipeline.run(analysis)
    analysis.refresh_from_db()
    assert (analysis.status, analysis.error_code) == ("failed", "not_found")


def test_unexpected_crash_is_recorded(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("bug")

    monkeypatch.setattr(pipeline, "fetch_profile", boom)
    analysis = Analysis.objects.create(github_login="x")
    pipeline.run(analysis)
    analysis.refresh_from_db()
    assert (analysis.status, analysis.error_code) == ("failed", "server_error")


def test_job_seekers_own_token_is_used(settings):
    from tests.factories import GithubAccountFactory

    account = GithubAccountFactory(login="amina-demo")
    account.set_token("gho_personal")
    account.save()
    analysis = Analysis.objects.create(github_login="amina-demo")
    assert pipeline._token_for(analysis) == "gho_personal"
    assert pipeline._token_for(Analysis(github_login="someone-else")) == settings.GITHUB_TOKEN


def test_rerun_reuses_repository_rows():
    first = run_for("brian-demo")
    second = run_for("brian-demo")
    from apps.analysis.models import Repository

    assert Repository.objects.count() == 3
    assert first.signal_score == second.signal_score  # deterministic
