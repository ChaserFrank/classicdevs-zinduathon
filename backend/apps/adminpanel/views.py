"""Admin-only API (role `admin`). Every state change is audit-logged."""

from datetime import timedelta

from django.db import transaction
from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import tokens
from apps.accounts.models import JobSeekerProfile, Role, User
from apps.accounts.permissions import IsAdminRole
from apps.analysis.models import Analysis
from apps.companies import services as company_services
from apps.companies.models import ApprovalStatus, RecruiterProfile
from apps.core import audit
from apps.core.models import AuditLog
from apps.core.pagination import StandardPagination
from apps.core.schema import errors
from apps.notifications.models import Delivery, DeliveryStatus
from apps.recruiting.models import Feedback, Moderation
from apps.recruiting.services import feedback as feedback_service
from apps.skills.models import DependencyMapping, Skill, SkillAlias

from .serializers import (
    AdminSkillSerializer,
    AdminUserSerializer,
    AdminUserUpdateSerializer,
    AuditLogSerializer,
    DeliverySerializer,
    DependencyMappingSerializer,
    HeldFeedbackSerializer,
    RecruiterQueueSerializer,
    ReviewSerializer,
    StatsSerializer,
)

ADMIN_ERRORS = errors((401, "not_authenticated"), (403, "permission_denied"))
OK_STATUSES = (DeliveryStatus.SENT, DeliveryStatus.DELIVERED, DeliveryStatus.DRY_RUN)


class AdminView(APIView):
    permission_classes = (IsAdminRole,)

    def paginate(self, request, queryset, serializer):
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(serializer(page, many=True).data)


class StatsView(AdminView):
    @extend_schema(
        tags=["Admin"], summary="Dashboard stats", responses={200: StatsSerializer, **ADMIN_ERRORS}
    )
    def get(self, request):
        since = timezone.now() - timedelta(days=14)
        per_day = (
            Analysis.objects.filter(created_at__gte=since)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(total=Count("id"), completed=Count("id", filter=Q(status="completed")))
            .order_by("day")
        )
        rates = {}
        for channel in ("email", "sms"):
            rows = Delivery.objects.filter(channel=channel)
            total = rows.exclude(status=DeliveryStatus.SKIPPED).count()
            ok = rows.filter(status__in=OK_STATUSES).count()
            rates[channel] = {
                "total": total,
                "ok": ok,
                "failed": rows.filter(status=DeliveryStatus.FAILED).count(),
                "skipped": rows.filter(status=DeliveryStatus.SKIPPED).count(),
                "rate": round(ok / total, 3) if total else None,
            }
        average = Analysis.objects.filter(status="completed").aggregate(v=Avg("signal_score"))["v"]
        return Response(
            {
                "users_by_role": {
                    role: User.objects.filter(role=role).count() for role in Role.values
                },
                "pending_recruiters": RecruiterProfile.objects.filter(
                    approval_status=ApprovalStatus.PENDING
                ).count(),
                "analyses_per_day": [
                    {
                        "date": row["day"].isoformat(),
                        "total": row["total"],
                        "completed": row["completed"],
                    }
                    for row in per_day
                ],
                "average_signal_score": round(average, 1) if average is not None else None,
                "feedback_sent": Feedback.objects.filter(moderation=Moderation.SENT).count(),
                "feedback_held": Feedback.objects.filter(moderation=Moderation.HELD).count(),
                "delivery_rates": rates,
            }
        )


class RecruiterQueueView(AdminView):
    @extend_schema(
        tags=["Admin"],
        summary="Recruiter approval queue",
        parameters=[
            OpenApiParameter("status", str, enum=ApprovalStatus.values),
            OpenApiParameter("page", int),
        ],
        responses={200: RecruiterQueueSerializer(many=True), **ADMIN_ERRORS},
    )
    def get(self, request):
        queryset = RecruiterProfile.objects.select_related("user", "company").order_by("created_at")
        if state := request.query_params.get("status"):
            queryset = queryset.filter(approval_status=state)
        return self.paginate(request, queryset, RecruiterQueueSerializer)


class RecruiterReviewView(AdminView):
    action = ""

    @extend_schema(
        tags=["Admin"],
        summary="Approve or reject a recruiter",
        description=(
            "Records the reviewer and note, audit-logs it and emails the recruiter (SMS if opted "
            "in). Approval requires a verified email."
        ),
        request=ReviewSerializer,
        responses={
            200: RecruiterQueueSerializer,
            **errors((403, "email_not_verified"), (404, "not_found")),
            **ADMIN_ERRORS,
        },
    )
    def post(self, request, public_id):
        profile = (
            RecruiterProfile.objects.select_related("user", "company")
            .filter(user__public_id=public_id)
            .first()
        )
        if profile is None:
            raise NotFound()
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        handler = company_services.approve if self.action == "approve" else company_services.reject
        handler(
            profile, reviewer=request.user, note=serializer.validated_data["note"], request=request
        )
        return Response(RecruiterQueueSerializer(profile).data)


class UserListView(AdminView):
    @extend_schema(
        tags=["Admin"],
        summary="Users",
        parameters=[
            OpenApiParameter("search", str, description="Email, name or GitHub login"),
            OpenApiParameter("role", str, enum=Role.values),
            OpenApiParameter("isActive", bool),
            OpenApiParameter("page", int),
        ],
        responses={200: AdminUserSerializer(many=True), **ADMIN_ERRORS},
    )
    def get(self, request):
        queryset = User.objects.select_related(
            "github_account", "recruiter_profile__company"
        ).order_by("-date_joined")
        if term := request.query_params.get("search", "").strip():
            queryset = queryset.filter(
                Q(email__icontains=term)
                | Q(full_name__icontains=term)
                | Q(github_account__login__icontains=term)
            )
        if role := request.query_params.get("role"):
            queryset = queryset.filter(role=role)
        if (active := request.query_params.get("is_active")) is not None:
            queryset = queryset.filter(is_active=active.lower() in {"1", "true"})
        return self.paginate(request, queryset, AdminUserSerializer)


class UserDetailView(AdminView):
    def _user(self, public_id) -> User:
        user = (
            User.objects.select_related("github_account", "recruiter_profile__company")
            .filter(public_id=public_id)
            .first()
        )
        if user is None:
            raise NotFound()
        return user

    @extend_schema(
        tags=["Admin"],
        summary="User",
        responses={200: AdminUserSerializer, **errors((404, "not_found")), **ADMIN_ERRORS},
    )
    def get(self, request, public_id):
        return Response(AdminUserSerializer(self._user(public_id)).data)

    @extend_schema(
        tags=["Admin"],
        summary="Suspend, reactivate or change role",
        description=(
            "`isActive: false` suspends the account and signs it out everywhere. A role change "
            "needs the matching profile (promoting to admin always works). Admins can't change "
            "their own account here."
        ),
        request=AdminUserUpdateSerializer,
        responses={
            200: AdminUserSerializer,
            **errors((400, "validation_error"), (404, "not_found")),
            **ADMIN_ERRORS,
        },
    )
    @transaction.atomic
    def patch(self, request, public_id):
        user = self._user(public_id)
        if user.pk == request.user.pk:
            raise ValidationError({"id": ["Use another admin account to change your own access."]})
        serializer = AdminUserUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        changes = {}
        if "is_active" in data and data["is_active"] != user.is_active:
            user.is_active = data["is_active"]
            changes["is_active"] = data["is_active"]
            if not user.is_active:
                tokens.blacklist_all(user)
        if "role" in data and data["role"] != user.role:
            new = data["role"]
            if new == Role.JOB_SEEKER and not JobSeekerProfile.objects.filter(user=user).exists():
                raise ValidationError({"role": ["This user has no job seeker profile."]})
            if new == Role.RECRUITER and not RecruiterProfile.objects.filter(user=user).exists():
                raise ValidationError({"role": ["This user has no recruiter profile."]})
            changes["role"] = {"from": user.role, "to": new}
            user.role = new
            user.is_staff = new == Role.ADMIN
        if changes:
            user.save()
            action = (
                "admin.user_suspended"
                if changes.get("is_active") is False
                else "admin.user_updated"
            )
            audit.record(action, actor=request.user, target=user, request=request, metadata=changes)
        return Response(AdminUserSerializer(user).data)


class DeliveryListView(AdminView):
    @extend_schema(
        tags=["Admin"],
        summary="Notification deliveries",
        parameters=[
            OpenApiParameter("status", str, enum=DeliveryStatus.values),
            OpenApiParameter("channel", str, enum=["email", "sms"]),
            OpenApiParameter("provider", str, enum=["smtp", "thrivewave"]),
            OpenApiParameter("page", int),
        ],
        responses={200: DeliverySerializer(many=True), **ADMIN_ERRORS},
    )
    def get(self, request):
        queryset = Delivery.objects.select_related("notification__user").order_by("-created_at")
        for field in ("status", "channel", "provider"):
            if value := request.query_params.get(field):
                queryset = queryset.filter(**{field: value})
        return self.paginate(request, queryset, DeliverySerializer)


class DeliveryRetryView(AdminView):
    @extend_schema(
        tags=["Admin"],
        summary="Retry a failed delivery",
        description="Re-sends the originally rendered message (3 more attempts).",
        request=None,
        responses={
            200: DeliverySerializer,
            **errors((400, "validation_error"), (404, "not_found")),
            **ADMIN_ERRORS,
        },
    )
    def post(self, request, public_id):
        delivery = (
            Delivery.objects.select_related("notification__user")
            .filter(public_id=public_id)
            .first()
        )
        if delivery is None:
            raise NotFound()
        if delivery.status != DeliveryStatus.FAILED:
            raise ValidationError({"status": ["Only failed deliveries can be retried."]})
        Delivery.objects.filter(pk=delivery.pk).update(
            status=DeliveryStatus.QUEUED, attempts=0, last_error=""
        )
        audit.record("admin.delivery_retry", actor=request.user, target=delivery, request=request)
        from apps.notifications.tasks import deliver

        transaction.on_commit(lambda: deliver.delay(delivery.pk))
        delivery.refresh_from_db()
        return Response(DeliverySerializer(delivery).data)


class AuditLogView(AdminView):
    @extend_schema(
        tags=["Admin"],
        summary="Audit log",
        parameters=[
            OpenApiParameter("actor", str, description="Actor email (contains)"),
            OpenApiParameter(
                "action", str, description="Exact action or prefix ending in '.' (e.g. `auth.`)"
            ),
            OpenApiParameter("since", str, description="ISO 8601"),
            OpenApiParameter("until", str, description="ISO 8601"),
            OpenApiParameter("page", int),
        ],
        responses={200: AuditLogSerializer(many=True), **ADMIN_ERRORS},
    )
    def get(self, request):
        queryset = AuditLog.objects.select_related("actor").order_by("-created_at", "-id")
        params = request.query_params
        if actor := params.get("actor"):
            queryset = queryset.filter(actor__email__icontains=actor)
        if action := params.get("action"):
            queryset = (
                queryset.filter(action__startswith=action)
                if action.endswith(".")
                else queryset.filter(action=action)
            )
        for name, lookup in (("since", "created_at__gte"), ("until", "created_at__lte")):
            if raw := params.get(name):
                moment = parse_datetime(raw)
                if moment is None:
                    raise ValidationError({name: ["Use ISO 8601, e.g. 2026-11-07T00:00:00Z."]})
                queryset = queryset.filter(**{lookup: moment})
        return self.paginate(request, queryset, AuditLogSerializer)


class HeldFeedbackView(AdminView):
    @extend_schema(
        tags=["Admin"],
        summary="Feedback held for review",
        responses={200: HeldFeedbackSerializer(many=True), **ADMIN_ERRORS},
    )
    def get(self, request):
        queryset = Feedback.objects.filter(moderation=Moderation.HELD).select_related(
            "recruiter", "job_seeker__user"
        )
        return self.paginate(request, queryset.order_by("created_at"), HeldFeedbackSerializer)


class HeldFeedbackDecisionView(AdminView):
    action = ""

    @extend_schema(
        tags=["Admin"],
        summary="Release (send) or reject held feedback",
        request=None,
        responses={200: HeldFeedbackSerializer, **errors((404, "not_found")), **ADMIN_ERRORS},
    )
    def post(self, request, public_id):
        feedback = Feedback.objects.filter(public_id=public_id, moderation=Moderation.HELD).first()
        if feedback is None:
            raise NotFound()
        handler = feedback_service.release if self.action == "release" else feedback_service.reject
        handler(feedback, admin=request.user, request=request)
        return Response(HeldFeedbackSerializer(feedback).data)


def _save_aliases(skill: Skill, aliases) -> None:
    if aliases is None:
        return
    skill.aliases.all().delete()
    for alias in {a.strip().lower() for a in aliases if a.strip()}:
        if SkillAlias.objects.filter(alias=alias).exclude(skill=skill).exists():
            raise ValidationError({"aliases": [f"'{alias}' already belongs to another skill."]})
        SkillAlias.objects.create(skill=skill, alias=alias)


class SkillAdminListView(AdminView):
    @extend_schema(
        tags=["Admin"],
        summary="Skill catalogue (admin)",
        parameters=[OpenApiParameter("page", int)],
        responses={200: AdminSkillSerializer(many=True)},
    )
    def get(self, request):
        return self.paginate(
            request,
            Skill.objects.prefetch_related("aliases").order_by("name"),
            AdminSkillSerializer,
        )

    @extend_schema(
        tags=["Admin"],
        summary="Add a skill",
        description="Takes effect on the next analysis: no deploy needed.",
        request=AdminSkillSerializer,
        responses={201: AdminSkillSerializer, **errors((400, "validation_error"))},
    )
    @transaction.atomic
    def post(self, request):
        serializer = AdminSkillSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        aliases = data.pop("aliases", [])
        data.setdefault("slug", slugify(data["name"].replace("+", "plus").replace("#", "sharp")))
        skill = Skill.objects.create(**data)
        _save_aliases(skill, aliases)
        audit.record(
            "admin.skill_created",
            actor=request.user,
            target=skill,
            request=request,
            metadata={"name": skill.name},
        )
        return Response(AdminSkillSerializer(skill).data, status=201)


class SkillAdminDetailView(AdminView):
    @extend_schema(
        tags=["Admin"],
        summary="Edit a skill",
        description="`aliases`, when sent, replaces the list.",
        request=AdminSkillSerializer(partial=True),
        responses={
            200: AdminSkillSerializer,
            **errors((400, "validation_error"), (404, "not_found")),
        },
    )
    @transaction.atomic
    def patch(self, request, slug):
        skill = Skill.objects.filter(slug=slug).first()
        if skill is None:
            raise NotFound()
        serializer = AdminSkillSerializer(skill, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        aliases = serializer.validated_data.pop("aliases", None)
        serializer.save()
        _save_aliases(skill, aliases)
        audit.record(
            "admin.skill_updated",
            actor=request.user,
            target=skill,
            request=request,
            metadata=dict(request.data),
        )
        return Response(AdminSkillSerializer(skill).data)


class DependencyMappingListView(AdminView):
    @extend_schema(
        tags=["Admin"],
        summary="Dependency mappings",
        parameters=[OpenApiParameter("ecosystem", str), OpenApiParameter("page", int)],
        responses={200: DependencyMappingSerializer(many=True)},
    )
    def get(self, request):
        queryset = DependencyMapping.objects.select_related("skill").order_by(
            "ecosystem", "package_name"
        )
        if eco := request.query_params.get("ecosystem"):
            queryset = queryset.filter(ecosystem=eco)
        return self.paginate(request, queryset, DependencyMappingSerializer)

    @extend_schema(
        tags=["Admin"],
        summary="Map a package to a skill",
        description=(
            "e.g. `{ecosystem: npm, packageName: svelte, skill: Svelte}`. Used from the next "
            "analysis."
        ),
        request=DependencyMappingSerializer,
        responses={201: DependencyMappingSerializer, **errors((400, "validation_error"))},
    )
    def post(self, request):
        serializer = DependencyMappingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mapping = serializer.save()
        audit.record(
            "admin.mapping_created",
            actor=request.user,
            request=request,
            metadata=DependencyMappingSerializer(mapping).data,
        )
        return Response(DependencyMappingSerializer(mapping).data, status=201)


class DependencyMappingDetailView(AdminView):
    @extend_schema(
        tags=["Admin"],
        summary="Change the skill a package maps to",
        request=DependencyMappingSerializer(partial=True),
        responses={200: DependencyMappingSerializer, **errors((404, "not_found"))},
    )
    def patch(self, request, ecosystem, package):
        from apps.analysis.services.manifests import normalise_package

        mapping = DependencyMapping.objects.filter(
            ecosystem=ecosystem, package_name=normalise_package(ecosystem, package)
        ).first()
        if mapping is None:
            raise NotFound()
        serializer = DependencyMappingSerializer(mapping, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        audit.record(
            "admin.mapping_updated", actor=request.user, request=request, metadata=serializer.data
        )
        return Response(serializer.data)
