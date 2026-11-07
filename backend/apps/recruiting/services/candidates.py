"""Candidate search over job seekers with a visible card and a completed analysis.

Each job seeker is represented by their *latest* completed analysis (a correlated subquery), and
skill filters are EXISTS checks against analysis_analysisskill using its (skill, label) index, so
the database does the filtering and pagination stays cheap.
"""

from django.db.models import Exists, F, OuterRef, Q, Subquery

from apps.accounts.models import JobSeekerProfile
from apps.analysis.models import Analysis, AnalysisSkill
from apps.analysis.services.pipeline import load_catalogue
from apps.skills.models import Skill

from .match import RANK

ORDERINGS = {
    "-signalScore": ("-signal_score", "-analysed_at"),
    "signalScore": ("signal_score", "-analysed_at"),
    "-analysedAt": ("-analysed_at",),
    "analysedAt": ("analysed_at",),
}


class UnknownSkills(ValueError):
    def __init__(self, names: list[str]):
        super().__init__(names)
        self.names = names


def labels_at_least(minimum: str) -> list[str]:
    return [label for label, rank in RANK.items() if rank >= max(RANK[minimum], 1)]


def resolve_skills(raw_names: list[str]) -> list[Skill]:
    """Names, slugs or aliases ("drf", "reactjs") → Skill rows; unknown names are an error."""
    _, lookup = load_catalogue()
    by_name = Skill.objects.in_bulk(field_name="name")
    by_slug = {s.slug: s for s in by_name.values()}
    found, unknown = [], []
    for raw in raw_names:
        key = " ".join(raw.lower().split())
        skill = by_slug.get(key) or by_name.get(lookup.get(key, ""))
        (found if skill else unknown).append(skill or raw)
    if unknown:
        raise UnknownSkills(unknown)
    return list(dict.fromkeys(found))


def visible_candidates():
    latest = Analysis.objects.filter(job_seeker=OuterRef("pk"), status="completed").order_by(
        "-completed_at"
    )
    return (
        JobSeekerProfile.objects.filter(card_visible=True, user__is_active=True)
        .annotate(
            latest_id=Subquery(latest.values("pk")[:1]),
            signal_score=Subquery(latest.values("signal_score")[:1]),
            analysed_at=Subquery(latest.values("completed_at")[:1]),
            github_login=F("user__github_account__login"),
        )
        .filter(latest_id__isnull=False)
        .select_related("user", "user__github_account")
    )


def search(
    *,
    skills: list[Skill] = (),
    min_label: str = "emerging",
    min_score: int | None = None,
    open_to_work: bool | None = None,
    text: str = "",
    ordering: str = "-signalScore",
):
    queryset = visible_candidates()
    labels = labels_at_least(min_label)
    for skill in skills:
        queryset = queryset.filter(
            Exists(
                AnalysisSkill.objects.filter(
                    analysis_id=OuterRef("latest_id"), skill=skill, label__in=labels
                )
            )
        )
    if min_score is not None:
        queryset = queryset.filter(signal_score__gte=min_score)
    if open_to_work is not None:
        queryset = queryset.filter(open_to_work=open_to_work)
    if text := text.strip():
        queryset = queryset.filter(
            Q(user__full_name__icontains=text)
            | Q(headline__icontains=text)
            | Q(location__icontains=text)
            | Q(user__github_account__login__icontains=text)
        )
    return queryset.order_by(*ORDERINGS.get(ordering, ORDERINGS["-signalScore"]), "pk")


def get_candidate(github_login: str, *, include_hidden: bool = False):
    queryset = visible_candidates() if not include_hidden else _all_candidates()
    return queryset.filter(user__github_account__login=github_login.lower()).first()


def _all_candidates():
    latest = Analysis.objects.filter(job_seeker=OuterRef("pk"), status="completed").order_by(
        "-completed_at"
    )
    return JobSeekerProfile.objects.annotate(
        latest_id=Subquery(latest.values("pk")[:1]),
        signal_score=Subquery(latest.values("signal_score")[:1]),
        analysed_at=Subquery(latest.values("completed_at")[:1]),
        github_login=F("user__github_account__login"),
    ).select_related("user", "user__github_account")


def skill_labels(analysis_ids) -> dict[int, dict[str, str]]:
    """analysis id → {skill name: label}."""
    out: dict[int, dict[str, str]] = {}
    for analysis_id, name, label in AnalysisSkill.objects.filter(
        analysis_id__in=list(analysis_ids)
    ).values_list("analysis_id", "skill__name", "label"):
        out.setdefault(analysis_id, {})[name] = label
    return out


def top_skills(analysis_ids, limit: int = 5) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    rows = (
        AnalysisSkill.objects.filter(analysis_id__in=list(analysis_ids))
        .exclude(label="unverified")
        .order_by("analysis_id", "-evidence", "skill__name")
        .values_list("analysis_id", "skill__name", "label")
    )
    for analysis_id, name, label in rows:
        bucket = out.setdefault(analysis_id, [])
        if len(bucket) < limit:
            bucket.append({"name": name, "label": label.title()})
    return out
