from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.analysis.models import Analysis, AnalysisSkill
from apps.skills.models import Skill
from tests.factories import GithubAccountFactory

EVIDENCE = {"strong": "2.50", "moderate": "1.00", "emerging": "0.30", "unverified": "0"}


def make_candidate(
    login,
    score=60,
    skills=None,
    *,
    visible=True,
    open_to_work=True,
    headline="Developer",
    days_ago=0,
    name=None,
):
    account = GithubAccountFactory(login=login, user__full_name=name or login.title())
    profile = account.user.job_seeker_profile
    profile.card_visible, profile.open_to_work, profile.headline = visible, open_to_work, headline
    profile.save()
    add_analysis(profile, login, score, skills or {}, days_ago=days_ago)
    return profile


def add_analysis(profile, login, score, skills, *, days_ago=0):
    analysis = Analysis.objects.create(
        github_login=login,
        job_seeker=profile,
        status="completed",
        signal_score=score,
        completed_at=timezone.now() - timedelta(days=days_ago),
    )
    for name, label in skills.items():
        AnalysisSkill.objects.create(
            analysis=analysis,
            skill=Skill.objects.get(name=name),
            label=label,
            evidence=Decimal(EVIDENCE[label]),
        )
    return analysis
