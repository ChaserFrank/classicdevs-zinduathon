from django.db import transaction
from django.db.models import Prefetch
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import IsJobSeeker, is_admin
from apps.core.schema import errors

from . import cards
from .errors import GithubLoginRequired
from .models import Analysis, AnalysisStatus, ClaimedSkill, SubScore
from .serializers import (
    AnalysisCreateSerializer,
    AnalysisDetailSerializer,
    AnalysisListItemSerializer,
    AnalysisStartedSerializer,
    CardSerializer,
    ClaimedSkillSerializer,
    ClaimedSkillsSerializer,
    ClaimedSkillsUpdateSerializer,
)
from .services import runner

CARD_EXAMPLE = {
    "username": "wanjiru-dev",
    "profile": {
        "username": "wanjiru-dev",
        "name": "Wanjiru Kamau",
        "avatarUrl": "https://avatars.githubusercontent.com/u/1",
        "verifiedOwner": True,
    },
    "signalScore": 72,
    "subScores": {
        "consistency": {"value": 15, "reason": "Active in 20 of the last 52 weeks"},
        "iteration": {
            "value": 14,
            "reason": (
                "Median commit 120 lines; 4 of 6 repos with 10+ commits; "
                "1 mostly arrived in one commit"
            ),
        },
        "quality": {
            "value": 17,
            "reason": "Has tests, CI, a README; missing Docker or .env.example",
        },
        "breadth": {"value": 14, "reason": "3 strong skills, 1 moderate"},
        "ownership": {"value": 12, "reason": "Wrote most of the commits in 4 of 6 original repos"},
    },
    "skills": [
        {
            "name": "TypeScript",
            "category": "Language",
            "label": "Strong",
            "evidence": 3.6,
            "repos": [
                {
                    "name": "shop-app",
                    "url": "https://github.com/wanjiru-dev/shop-app",
                    "commits": 48,
                    "firstCommit": "2026-03-02T09:12:00+00:00",
                    "lastCommit": "2026-10-28T17:40:00+00:00",
                    "hasTests": True,
                    "hasCI": True,
                }
            ],
        }
    ],
    "claims": [
        {"skill": "React", "status": "Verified"},
        {"skill": "Kubernetes", "status": "Unverified"},
    ],
    "flags": [
        {
            "type": "one_shot_dump",
            "repo": "matatu-routes",
            "reason": (
                "86% of the sampled code in matatu-routes arrived in a single commit. "
                "Worth asking how it was built."
            ),
        }
    ],
    "aiSummary": "Strongest evidence is in TypeScript and React across 6 public repositories. …",
    "reposAnalysed": 6,
    "commitsAnalysed": 182,
    "analysedAt": "2026-11-07T10:00:00+00:00",
}


def _with_relations(queryset):
    return queryset.select_related("job_seeker__user").prefetch_related(
        Prefetch("subscores", queryset=SubScore.objects.order_by("id"))
    )


def _can_see(user, analysis: Analysis) -> bool:
    if is_admin(user):
        return True
    if analysis.triggered_by_id == user.pk:
        return True
    return analysis.job_seeker is not None and analysis.job_seeker.user_id == user.pk


def detail_payload(analysis: Analysis, user) -> dict:
    complete = analysis.status == AnalysisStatus.COMPLETED
    return {
        "id": analysis.public_id,
        "github_login": analysis.github_login,
        "status": analysis.status,
        "progress_step": analysis.progress_step,
        "error_code": analysis.error_code,
        "error_message": analysis.error_message,
        "signal_score": analysis.signal_score,
        "created_at": analysis.created_at,
        "completed_at": analysis.completed_at,
        "card": cards.build_card(analysis) if complete else None,
        "tips": list(analysis.tips) if complete and _can_see(user, analysis) else [],
    }


class AnalysisListCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    def get_throttles(self):
        if self.request.method == "POST":
            self.throttle_scope = "analysis"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    @extend_schema(
        tags=["Analyses"],
        summary="Start an analysis",
        description=(
            "Job seekers analyse their own linked GitHub account (email must be verified). Admins "
            "pass `githubLogin`. Returns `202 {id, status}` and runs in the background: poll "
            "`GET /analyses/{id}`. A completed analysis under 24 h old is returned instead "
            "(`200`, with the card) unless `force` is true or the claimed skills changed. Only one "
            "analysis per login runs at a time. Throttled to 10 per hour."
        ),
        request=AnalysisCreateSerializer,
        responses={
            200: AnalysisDetailSerializer,
            202: AnalysisStartedSerializer,
            **errors(
                (400, "validation_error"),
                (400, "github_not_linked"),
                (403, "email_not_verified"),
                (403, "permission_denied"),
                (409, "analysis_in_progress"),
                (429, "rate_limited"),
            ),
        },
        examples=[
            OpenApiExample("Job seeker", value={}, request_only=True),
            OpenApiExample(
                "Admin", value={"githubLogin": "octocat", "force": True}, request_only=True
            ),
            OpenApiExample(
                "Started",
                value={"id": "1b6f…", "status": "queued"},
                response_only=True,
                status_codes=["202"],
            ),
        ],
    )
    def post(self, request):
        if request.user.role not in (Role.JOB_SEEKER, Role.ADMIN):
            raise PermissionDenied("Only job seekers and admins can run analyses.")
        serializer = AnalysisCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if is_admin(request.user) and not data.get("github_login"):
            raise GithubLoginRequired()
        analysis, reused = runner.start(
            request.user,
            github_login=data.get("github_login"),
            force=data["force"],
            request=request,
        )
        if reused:
            return Response(detail_payload(analysis, request.user))
        return Response(
            {"id": analysis.public_id, "status": analysis.status}, status=status.HTTP_202_ACCEPTED
        )

    @extend_schema(
        tags=["Analyses"],
        summary="Analysis history",
        description=(
            "Job seekers see their own analyses (scores over time are the iteration evidence). "
            "Admins see all, filterable by `githubLogin` and `status`."
        ),
        parameters=[
            OpenApiParameter("githubLogin", str, description="Admins only"),
            OpenApiParameter("status", str, enum=AnalysisStatus.values, description="Admins only"),
            OpenApiParameter("page", int),
            OpenApiParameter("pageSize", int),
        ],
        responses={
            200: AnalysisListItemSerializer(many=True),
            **errors((401, "not_authenticated"), (403, "permission_denied")),
        },
    )
    def get(self, request):
        queryset = _with_relations(Analysis.objects.all()).order_by("-created_at")
        if is_admin(request.user):
            if login := request.query_params.get("github_login"):
                queryset = queryset.filter(github_login=login.lower())
            if state := request.query_params.get("status"):
                queryset = queryset.filter(status=state)
        elif request.user.role == Role.JOB_SEEKER:
            queryset = queryset.filter(job_seeker__user=request.user)
        else:
            raise PermissionDenied("Only job seekers and admins have analysis history.")
        paginator = self.paginator
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(AnalysisListItemSerializer(page, many=True).data)

    @property
    def paginator(self):
        if not hasattr(self, "_paginator"):
            from apps.core.pagination import StandardPagination

            self._paginator = StandardPagination()
        return self._paginator


class AnalysisDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Analyses"],
        summary="Analysis status and card",
        description=(
            "Poll every 2–3 seconds while `status` is `queued` or `running`; `progressStep` goes "
            "1→4. When `completed`, `card` holds the skill card. When `failed`, `errorCode` is one "
            "of `not_found`, `no_public_repos`, `github_rate_limited`, `github_unavailable`, "
            "`timeout`, `server_error`."
        ),
        responses={
            200: AnalysisDetailSerializer,
            **errors((401, "not_authenticated"), (404, "not_found")),
        },
    )
    def get(self, request, public_id):
        analysis = _with_relations(Analysis.objects.filter(public_id=public_id)).first()
        if analysis is None or not _can_see(request.user, analysis):
            raise NotFound()
        return Response(detail_payload(analysis, request.user))


class CardView(APIView):
    """Public share link. Authentication is optional (it lets recruiter views be counted)."""

    permission_classes = (AllowAny,)

    @extend_schema(
        tags=["Analyses"],
        summary="Public skill card",
        description=(
            "The latest completed card for a GitHub login, or 404. Cards of job seekers are "
            "preferred over admin-run analyses of the same login."
        ),
        responses={200: CardSerializer, **errors((404, "not_found"))},
        examples=[OpenApiExample("Card", value=CARD_EXAMPLE, response_only=True)],
        auth=[{"jwtAuth": []}, {}],
    )
    def get(self, request, github_login):
        completed = Analysis.objects.filter(
            github_login=github_login.lower(), status=AnalysisStatus.COMPLETED
        ).order_by("-completed_at")
        analysis = completed.filter(job_seeker__isnull=False).first() or completed.first()
        if analysis is None:
            raise NotFound("No skill card for this GitHub account yet.")
        on_card_viewed(request, analysis)
        return Response(cards.build_card(analysis))


def on_card_viewed(request, analysis) -> None:
    """Hook for recruiter profile views (wired up in Phase 5)."""


class ClaimedSkillsView(APIView):
    permission_classes = (IsJobSeeker,)

    def _response(self, profile):
        rows = profile.claimed_skills.select_related("skill")
        return Response({"skills": ClaimedSkillSerializer(rows, many=True).data})

    @extend_schema(
        tags=["Profile"],
        summary="My claimed skills",
        responses={
            200: ClaimedSkillsSerializer,
            **errors((401, "not_authenticated"), (403, "permission_denied")),
        },
    )
    def get(self, request):
        return self._response(request.user.job_seeker_profile)

    @extend_schema(
        tags=["Profile"],
        summary="Replace my claimed skills",
        description=(
            "What you list on your CV (max 12), in order. Each entry is matched to the catalogue "
            'by name or alias ("reactjs" → React); unmatched entries are kept and will show as '
            "Unverified. Changing the list makes the next analysis run fresh."
        ),
        request=ClaimedSkillsUpdateSerializer,
        responses={
            200: ClaimedSkillsSerializer,
            **errors((400, "validation_error"), (403, "permission_denied")),
        },
        examples=[
            OpenApiExample(
                "CV skills", value={"skills": ["React", "django", "Kubernetes"]}, request_only=True
            )
        ],
    )
    @transaction.atomic
    def put(self, request):
        serializer = ClaimedSkillsUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = request.user.job_seeker_profile
        from apps.skills.models import Skill

        from .services.pipeline import load_catalogue

        _, lookup = load_catalogue()
        wanted = serializer.validated_data["skills"]
        existing = {c.raw_text.lower(): c for c in profile.claimed_skills.all()}
        keep = {text.lower() for text in wanted}
        profile.claimed_skills.exclude(
            pk__in=[c.pk for k, c in existing.items() if k in keep]
        ).delete()
        skills = Skill.objects.in_bulk(list(lookup.values()), field_name="name")
        for position, text in enumerate(wanted):
            name = lookup.get(text.lower())
            row = existing.get(text.lower()) or ClaimedSkill(job_seeker=profile, raw_text=text)
            row.raw_text, row.position, row.skill = (
                text,
                position,
                skills.get(name) if name else None,
            )
            row.save()
        return self._response(profile)
