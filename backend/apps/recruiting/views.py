from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch
from django.db.models.functions import TruncWeek
from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import (
    IsApprovedRecruiter,
    IsApprovedRecruiterOrAdmin,
    IsJobSeeker,
    is_admin,
)
from apps.analysis.cards import build_card
from apps.analysis.models import Analysis
from apps.companies.models import Company
from apps.core.exceptions import ApiError
from apps.core.pagination import StandardPagination
from apps.core.schema import errors

from .models import (
    Feedback,
    JobPosting,
    JobRequiredSkill,
    JobStatus,
    Moderation,
    ProfileView,
    ShortlistEntry,
)
from .serializers import (
    CandidateDetailSerializer,
    CandidateMatchSerializer,
    CandidateSearchParamsSerializer,
    CandidateSerializer,
    FeedbackCreateSerializer,
    FeedbackSerializer,
    JobSerializer,
    JobWriteSerializer,
    MatchSerializer,
    ProfileViewsSerializer,
    ShortlistCreateSerializer,
    ShortlistSerializer,
    ShortlistUpdateSerializer,
)
from .services import candidates as search
from .services import feedback as feedback_service
from .services.match import Requirement, match
from .services.moderation import FeedbackRejected

RECRUITER_ERRORS = errors(
    (401, "not_authenticated"), (403, "recruiter_not_approved"), (403, "permission_denied")
)


class AlreadyShortlisted(ApiError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "already_shortlisted"
    default_detail = "This candidate is already on your shortlist for that job."


def _paginate(view, request, items, serializer, **context):
    paginator = StandardPagination()
    page = paginator.paginate_queryset(items, request, view=view)
    return paginator.get_paginated_response(serializer(page, many=True, context=context).data)


def candidate_rows(profiles) -> list[dict]:
    profiles = list(profiles)
    tops = search.top_skills(p.latest_id for p in profiles)
    avatars = dict(
        Analysis.objects.filter(pk__in=[p.latest_id for p in profiles]).values_list(
            "pk", "avatar_url"
        )
    )
    return [
        {
            "github_login": p.github_login or "",
            "name": p.user.full_name,
            "headline": p.headline,
            "location": p.location,
            "avatar_url": avatars.get(p.latest_id) or "",
            "open_to_work": p.open_to_work,
            "signal_score": p.signal_score,
            "analysed_at": p.analysed_at,
            "top_skills": tops.get(p.latest_id, []),
        }
        for p in profiles
    ]


def record_view(user, job_seeker) -> None:
    """Count recruiter views; one per recruiter per job seeker per hour is enough."""
    if not user.is_authenticated or user.role != Role.RECRUITER or job_seeker is None:
        return
    recent = timezone.now() - timedelta(hours=1)
    if not ProfileView.objects.filter(
        recruiter=user, job_seeker=job_seeker, viewed_at__gte=recent
    ).exists():
        ProfileView.objects.create(recruiter=user, job_seeker=job_seeker)


class CandidateListView(APIView):
    permission_classes = (IsApprovedRecruiterOrAdmin,)

    @extend_schema(
        tags=["Candidates"],
        summary="Search candidates",
        description=(
            "Job seekers with a visible card and a completed analysis, by proven skill. Every "
            "skill in `skills` must be at `minLabel` or above. No emails or phone numbers."
        ),
        parameters=[
            OpenApiParameter("skills", str, description="Comma-separated, e.g. `react,django`"),
            OpenApiParameter("minLabel", str, enum=["emerging", "moderate", "strong"]),
            OpenApiParameter("minScore", int),
            OpenApiParameter("openToWork", bool),
            OpenApiParameter("search", str, description="Name, headline, location or GitHub login"),
            OpenApiParameter(
                "ordering", str, enum=["-signalScore", "signalScore", "-analysedAt", "analysedAt"]
            ),
            OpenApiParameter("page", int),
            OpenApiParameter("pageSize", int),
        ],
        responses={
            200: CandidateSerializer(many=True),
            **errors((400, "validation_error")),
            **RECRUITER_ERRORS,
        },
    )
    def get(self, request):
        params = CandidateSearchParamsSerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        data = params.validated_data
        names = [n for n in (data.get("skills") or "").split(",") if n.strip()]
        try:
            skills = search.resolve_skills(names)
        except search.UnknownSkills as exc:
            raise ValidationError({"skills": [f"Unknown skill: {', '.join(exc.names)}"]}) from exc
        queryset = search.search(
            skills=skills,
            min_label=data["min_label"],
            min_score=data.get("min_score"),
            open_to_work=data["open_to_work"],
            text=data["search"],
            ordering=data["ordering"],
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(
            CandidateSerializer(candidate_rows(page), many=True).data
        )


def _candidate_or_404(request, github_login):
    candidate = search.get_candidate(github_login, include_hidden=is_admin(request.user))
    if candidate is None or candidate.latest_id is None:
        raise NotFound("No visible candidate with that GitHub login.")
    return candidate


class CandidateDetailView(APIView):
    permission_classes = (IsApprovedRecruiterOrAdmin,)

    @extend_schema(
        tags=["Candidates"],
        summary="Candidate card",
        description=(
            "The skill card plus your shortlist entries and the feedback you already sent. Counts "
            "as a profile view."
        ),
        responses={
            200: CandidateDetailSerializer,
            **errors((404, "not_found")),
            **RECRUITER_ERRORS,
        },
    )
    def get(self, request, github_login):
        candidate = _candidate_or_404(request, github_login)
        record_view(request.user, candidate)
        analysis = Analysis.objects.get(pk=candidate.latest_id)
        shortlist = ShortlistEntry.objects.filter(
            recruiter=request.user, job_seeker=candidate
        ).select_related("job_seeker__user__github_account", "job_posting")
        sent = Feedback.objects.filter(recruiter=request.user, job_seeker=candidate).select_related(
            "recruiter", "job_posting"
        )
        return Response(
            {
                "candidate": CandidateSerializer(candidate_rows([candidate])[0]).data,
                "card": build_card(analysis),
                "shortlist": ShortlistSerializer(shortlist, many=True).data,
                "feedback_sent": FeedbackSerializer(sent, many=True).data,
            }
        )


class CandidateFeedbackView(APIView):
    permission_classes = (IsApprovedRecruiterOrAdmin,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "feedback"

    @extend_schema(
        tags=["Feedback"],
        summary="Send feedback to a candidate",
        description=(
            "Creates the feedback and notifies the job seeker in-app, by email and by SMS (per "
            "their preferences). HTML is stripped, max 1,000 characters, only https links. "
            "Messages with abusive language are held for admin review (`moderation: held`). "
            "Throttled to 30 per hour."
        ),
        request=FeedbackCreateSerializer,
        responses={
            201: FeedbackSerializer,
            **errors((400, "validation_error"), (404, "not_found"), (429, "rate_limited")),
            **RECRUITER_ERRORS,
        },
        examples=[
            OpenApiExample(
                "Interview",
                value={
                    "status": "interview",
                    "message": "Loved your duka-api tests. Free for a call on Thursday?",
                },
                request_only=True,
            )
        ],
    )
    def post(self, request, github_login):
        candidate = _candidate_or_404(request, github_login)
        serializer = FeedbackCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        job = _job_for(request.user, data.get("job_posting_id"))
        try:
            feedback = feedback_service.send_feedback(
                request.user,
                candidate,
                status=data["status"],
                message=data["message"],
                job_posting=job,
                request=request,
            )
        except FeedbackRejected as exc:
            raise ValidationError({"message": [str(exc)]}) from exc
        return Response(
            FeedbackSerializer(feedback, context={"show_candidate": True}).data, status=201
        )


def _job_for(user, job_id):
    """A job posting the user may attach to feedback/shortlists: own company's (admin: any)."""
    if not job_id:
        return None
    job = JobPosting.objects.filter(public_id=job_id).select_related("company").first()
    if job is None or not (is_admin(user) or job.company_id == user.recruiter_profile.company_id):
        raise ValidationError({"jobPostingId": ["Unknown job posting."]})
    return job


class FeedbackListView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Feedback"],
        summary="My feedback",
        description=(
            "Job seekers: feedback received (held or rejected messages are never shown). "
            "Recruiters: feedback sent."
        ),
        parameters=[OpenApiParameter("page", int), OpenApiParameter("pageSize", int)],
        responses={
            200: FeedbackSerializer(many=True),
            **errors((401, "not_authenticated"), (403, "permission_denied")),
        },
    )
    def get(self, request):
        base = Feedback.objects.select_related(
            "recruiter", "job_posting", "job_seeker__user__github_account"
        )
        if request.user.role == Role.JOB_SEEKER:
            items = base.filter(job_seeker__user=request.user, moderation=Moderation.SENT)
            show_candidate = False
        elif request.user.role == Role.RECRUITER:
            items = base.filter(recruiter=request.user)
            show_candidate = True
        else:
            raise PermissionDenied("Admins read feedback in the admin tools.")
        return _paginate(
            self,
            request,
            items.order_by("-created_at"),
            FeedbackSerializer,
            show_candidate=show_candidate,
        )


class FeedbackReadView(APIView):
    permission_classes = (IsJobSeeker,)

    @extend_schema(
        tags=["Feedback"],
        summary="Mark feedback read",
        request=None,
        responses={200: FeedbackSerializer, **errors((404, "not_found"))},
    )
    def post(self, request, public_id):
        feedback = Feedback.objects.filter(
            public_id=public_id, job_seeker__user=request.user, moderation=Moderation.SENT
        ).first()
        if feedback is None:
            raise NotFound()
        if feedback.read_at is None:
            feedback.read_at = timezone.now()
            feedback.save(update_fields=["read_at", "updated_at"])
        return Response(FeedbackSerializer(feedback).data)


# --- Jobs ---


def _jobs():
    return JobPosting.objects.select_related("company").prefetch_related(
        Prefetch(
            "required_skills",
            queryset=JobRequiredSkill.objects.select_related("skill").order_by("-weight", "id"),
        )
    )


def _set_required_skills(job, items) -> None:
    """Replace the job's required skills. Names, slugs and aliases are accepted; repeats of the
    same skill keep the first entry."""
    try:
        skills = [search.resolve_skills([item["skill"]])[0] for item in items]
    except search.UnknownSkills as exc:
        raise ValidationError(
            {"requiredSkills": [f"Unknown skill: {', '.join(exc.names)}"]}
        ) from exc
    job.required_skills.all().delete()
    seen: set[int] = set()
    for item, skill in zip(items, skills, strict=True):
        if skill.pk in seen:
            continue
        seen.add(skill.pk)
        JobRequiredSkill.objects.create(
            job_posting=job,
            skill=skill,
            # PATCH (partial=True) skips nested defaults, so apply them here.
            minimum_label=item.get("minimum_label", "moderate"),
            weight=item.get("weight", 1),
        )


def _job_or_404(request, public_id, *, edit=False):
    job = _jobs().filter(public_id=public_id).first()
    if job is None:
        raise NotFound()
    user = request.user
    if is_admin(user):
        return job
    if user.role == Role.RECRUITER:
        IsApprovedRecruiter().has_permission(request, None)  # raises recruiter_not_approved
        if job.company_id == user.recruiter_profile.company_id and (
            not edit or job.created_by_id == user.pk
        ):
            return job
        raise NotFound()
    if not edit and user.role == Role.JOB_SEEKER and job.status == JobStatus.OPEN:
        return job
    raise NotFound()


class JobListCreateView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Jobs"],
        summary="Job postings",
        description=(
            "Recruiters: their company's postings. Admins: all. Job seekers: open postings."
        ),
        parameters=[
            OpenApiParameter("status", str, enum=JobStatus.values),
            OpenApiParameter("page", int),
        ],
        responses={200: JobSerializer(many=True), **RECRUITER_ERRORS},
    )
    def get(self, request):
        user = request.user
        jobs = _jobs()
        if user.role == Role.JOB_SEEKER:
            jobs = jobs.filter(status=JobStatus.OPEN)
        elif user.role == Role.RECRUITER:
            IsApprovedRecruiter().has_permission(request, self)
            jobs = jobs.filter(company_id=user.recruiter_profile.company_id)
        if state := request.query_params.get("status"):
            jobs = jobs.filter(status=state)
        return _paginate(self, request, jobs.order_by("-created_at"), JobSerializer)

    @extend_schema(
        tags=["Jobs"],
        summary="Create a job posting",
        request=JobWriteSerializer,
        responses={201: JobSerializer, **errors((400, "validation_error")), **RECRUITER_ERRORS},
        examples=[
            OpenApiExample(
                "Backend role",
                value={
                    "title": "Junior backend developer",
                    "location": "Nairobi",
                    "remotePolicy": "hybrid",
                    "status": "open",
                    "requiredSkills": [
                        {"skill": "Python", "minimumLabel": "moderate", "weight": 3},
                        {"skill": "drf", "minimumLabel": "emerging", "weight": 2},
                        {"skill": "Testing", "minimumLabel": "moderate", "weight": 1},
                    ],
                },
                request_only=True,
            )
        ],
    )
    @transaction.atomic
    def post(self, request):
        if not IsApprovedRecruiterOrAdmin().has_permission(request, self):
            raise PermissionDenied()
        serializer = JobWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        skills = data.pop("required_skills", [])
        company_id = data.pop("company_id", None)
        if is_admin(request.user):
            company = Company.objects.filter(public_id=company_id).first() if company_id else None
            if company is None:
                raise ValidationError({"companyId": ["Admins must choose a company."]})
        else:
            company = request.user.recruiter_profile.company
        job = JobPosting.objects.create(company=company, created_by=request.user, **data)
        _set_required_skills(job, skills)
        return Response(JobSerializer(_jobs().get(pk=job.pk)).data, status=201)


class JobDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Jobs"],
        summary="Job posting",
        responses={200: JobSerializer, **errors((404, "not_found"))},
    )
    def get(self, request, public_id):
        return Response(JobSerializer(_job_or_404(request, public_id)).data)

    @extend_schema(
        tags=["Jobs"],
        summary="Edit a job posting",
        description="Owner recruiter or admin. `requiredSkills`, when sent, replaces the list.",
        request=JobWriteSerializer(partial=True),
        responses={200: JobSerializer, **errors((400, "validation_error"), (404, "not_found"))},
    )
    @transaction.atomic
    def patch(self, request, public_id):
        job = _job_or_404(request, public_id, edit=True)
        serializer = JobWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data.pop("company_id", None)
        skills = data.pop("required_skills", None)
        for field, value in data.items():
            setattr(job, field, value)
        job.save()
        if skills is not None:
            _set_required_skills(job, skills)
        return Response(JobSerializer(_jobs().get(pk=job.pk)).data)

    @extend_schema(
        tags=["Jobs"],
        summary="Delete a job posting",
        responses={204: None, **errors((404, "not_found"))},
    )
    def delete(self, request, public_id):
        _job_or_404(request, public_id, edit=True).delete()
        return Response(status=204)


def _requirements(job) -> list[Requirement]:
    return [Requirement(r.skill.name, r.minimum_label, r.weight) for r in job.required_skills.all()]


class JobMatchesView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Jobs"],
        summary="Ranked candidates for a job",
        description=(
            "Visible candidates ranked by match score (brief 8.7), then Signal Score. Owner "
            "recruiter or admin."
        ),
        parameters=[
            OpenApiParameter("minMatch", int),
            OpenApiParameter("page", int),
            OpenApiParameter("pageSize", int),
        ],
        responses={200: CandidateMatchSerializer(many=True), **errors((404, "not_found"))},
    )
    def get(self, request, public_id):
        job = _job_or_404(request, public_id, edit=True)
        requirements = _requirements(job)
        profiles = list(search.visible_candidates())
        labels = search.skill_labels(p.latest_id for p in profiles)
        min_match = int(request.query_params.get("min_match") or 0)
        scored = []
        for profile in profiles:
            result = match(requirements, labels.get(profile.latest_id, {}))
            if result.score > 0 and result.score >= min_match:
                scored.append((result, profile))
        scored.sort(key=lambda x: (-x[0].score, -(x[1].signal_score or 0), x[1].pk))
        paginator = StandardPagination()
        page = paginator.paginate_queryset(scored, request, view=self)
        rows = candidate_rows([p for _, p in page])
        for row, (result, _) in zip(rows, page, strict=True):
            row["match"] = {
                "score": result.score,
                "met": result.met,
                "partial": result.partial,
                "missing": result.missing,
            }
        return paginator.get_paginated_response(CandidateMatchSerializer(rows, many=True).data)


class JobMatchMeView(APIView):
    permission_classes = (IsJobSeeker,)

    @extend_schema(
        tags=["Jobs"],
        summary="How well do I match this job?",
        description=(
            "Your proven skills against the job's requirements, and what's missing. "
            "No analysis yet → score 0, all missing."
        ),
        responses={200: MatchSerializer, **errors((404, "not_found"))},
    )
    def get(self, request, public_id):
        job = _job_or_404(request, public_id)
        latest = (
            request.user.job_seeker_profile.analyses.filter(status="completed")
            .order_by("-completed_at")
            .first()
        )
        labels = search.skill_labels([latest.pk]).get(latest.pk, {}) if latest else {}
        result = match(_requirements(job), labels)
        return Response(
            {
                "score": result.score,
                "met": result.met,
                "partial": result.partial,
                "missing": result.missing,
            }
        )


# --- Shortlists ---


class ShortlistListCreateView(APIView):
    permission_classes = (IsApprovedRecruiterOrAdmin,)

    @extend_schema(
        tags=["Shortlists"],
        summary="My shortlist",
        parameters=[
            OpenApiParameter("stage", str),
            OpenApiParameter("jobPostingId", str),
            OpenApiParameter("page", int),
        ],
        responses={200: ShortlistSerializer(many=True), **RECRUITER_ERRORS},
    )
    def get(self, request):
        entries = ShortlistEntry.objects.filter(recruiter=request.user).select_related(
            "job_seeker__user__github_account", "job_posting"
        )
        if stage := request.query_params.get("stage"):
            entries = entries.filter(stage=stage)
        if job_id := request.query_params.get("job_posting_id"):
            entries = entries.filter(job_posting__public_id=job_id)
        return _paginate(self, request, entries.order_by("-updated_at"), ShortlistSerializer)

    @extend_schema(
        tags=["Shortlists"],
        summary="Shortlist a candidate",
        request=ShortlistCreateSerializer,
        responses={
            201: ShortlistSerializer,
            **errors((400, "validation_error"), (404, "not_found"), (409, "already_shortlisted")),
            **RECRUITER_ERRORS,
        },
    )
    @transaction.atomic
    def post(self, request):
        serializer = ShortlistCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        candidate = _candidate_or_404(request, data["github_login"])
        job = _job_for(request.user, data.get("job_posting_id"))
        try:
            with transaction.atomic():
                entry = ShortlistEntry.objects.create(
                    recruiter=request.user,
                    job_seeker=candidate,
                    job_posting=job,
                    stage=data["stage"],
                    note=data["note"],
                )
        except IntegrityError as exc:
            raise AlreadyShortlisted() from exc
        if data["notify_candidate"]:
            feedback_service.notify_stage(entry)
        return Response(ShortlistSerializer(entry).data, status=201)


class ShortlistDetailView(APIView):
    permission_classes = (IsApprovedRecruiterOrAdmin,)

    def _entry(self, request, public_id):
        entry = (
            ShortlistEntry.objects.filter(public_id=public_id, recruiter=request.user)
            .select_related(
                "job_seeker__user__github_account",
                "job_posting",
                "recruiter__recruiter_profile__company",
            )
            .first()
        )
        if entry is None:
            raise NotFound()
        return entry

    @extend_schema(
        tags=["Shortlists"],
        summary="Move stage or edit note",
        description=(
            "`notifyCandidate` tells the job seeker about the new stage (in-app, email, SMS). "
            "`feedbackMessage` also sends feedback, e.g. when moving to interview."
        ),
        request=ShortlistUpdateSerializer,
        responses={
            200: ShortlistSerializer,
            **errors((400, "validation_error"), (404, "not_found")),
        },
    )
    @transaction.atomic
    def patch(self, request, public_id):
        entry = self._entry(request, public_id)
        serializer = ShortlistUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        for field in ("stage", "note"):
            if field in data:
                setattr(entry, field, data[field])
        entry.save()
        if data["notify_candidate"]:
            feedback_service.notify_stage(entry)
        if data.get("feedback_message"):
            status_for_stage = {
                "interview": "interview",
                "rejected": "not_a_fit",
                "saved": "shortlisted",
                "contacted": "shortlisted",
            }
            try:
                feedback_service.send_feedback(
                    request.user,
                    entry.job_seeker,
                    status=status_for_stage.get(entry.stage, "general"),
                    message=data["feedback_message"],
                    job_posting=entry.job_posting,
                    request=request,
                )
            except FeedbackRejected as exc:
                raise ValidationError({"feedbackMessage": [str(exc)]}) from exc
        return Response(ShortlistSerializer(entry).data)

    @extend_schema(
        tags=["Shortlists"],
        summary="Remove from shortlist",
        responses={204: None, **errors((404, "not_found"))},
    )
    def delete(self, request, public_id):
        self._entry(request, public_id).delete()
        return Response(status=204)


class ProfileViewsView(APIView):
    permission_classes = (IsJobSeeker,)

    @extend_schema(
        tags=["Profile"],
        summary="Who's looking (counts only)",
        description=(
            "Distinct recruiters who viewed your card, this week and per week for 8 weeks. Names "
            "are never shown."
        ),
        responses={200: ProfileViewsSerializer},
    )
    def get(self, request):
        profile = request.user.job_seeker_profile
        now = timezone.now()
        views = ProfileView.objects.filter(job_seeker=profile)
        this_week = (
            views.filter(viewed_at__gte=now - timedelta(days=7))
            .values("recruiter")
            .distinct()
            .count()
        )
        weekly = (
            views.filter(viewed_at__gte=now - timedelta(weeks=8))
            .annotate(week=TruncWeek("viewed_at"))
            .values("week")
            .annotate(recruiters=Count("recruiter", distinct=True))
            .order_by("week")
        )
        return Response(
            {
                "this_week": this_week,
                "weeks": [
                    {"week_start": w["week"].date(), "recruiters": w["recruiters"]} for w in weekly
                ],
            }
        )
