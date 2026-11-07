from rest_framework import serializers

from apps.accounts.models import Role, User
from apps.core.models import AuditLog
from apps.notifications.models import Delivery
from apps.recruiting.models import Feedback
from apps.skills.models import Category, DependencyMapping, Ecosystem, Skill


class StatsSerializer(serializers.Serializer):
    users_by_role = serializers.DictField(child=serializers.IntegerField())
    pending_recruiters = serializers.IntegerField()
    analyses_per_day = serializers.ListField(child=serializers.DictField())
    average_signal_score = serializers.FloatField(allow_null=True)
    feedback_sent = serializers.IntegerField()
    feedback_held = serializers.IntegerField()
    delivery_rates = serializers.DictField(
        child=serializers.DictField(),
        help_text="Per channel: total, ok (sent/delivered/dry run), failed, skipped, rate",
    )


class AdminUserSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    email_verified = serializers.BooleanField(source="is_email_verified", read_only=True)
    phone_verified = serializers.BooleanField(source="is_phone_verified", read_only=True)
    github_login = serializers.SerializerMethodField()
    approval_status = serializers.SerializerMethodField()
    company = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "role",
            "phone",
            "is_active",
            "email_verified",
            "phone_verified",
            "github_login",
            "approval_status",
            "company",
            "last_login",
            "date_joined",
        )

    def get_github_login(self, user) -> str | None:
        account = getattr(user, "github_account", None)
        return account.login if account else None

    def get_approval_status(self, user) -> str | None:
        profile = getattr(user, "recruiter_profile", None)
        return profile.approval_status if profile else None

    def get_company(self, user) -> str | None:
        profile = getattr(user, "recruiter_profile", None)
        return profile.company.name if profile else None


class AdminUserUpdateSerializer(serializers.Serializer):
    is_active = serializers.BooleanField(
        required=False, help_text="False suspends and signs the user out"
    )
    role = serializers.ChoiceField(choices=Role.choices, required=False)


class RecruiterQueueSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="user.public_id")
    email = serializers.EmailField(source="user.email")
    full_name = serializers.CharField(source="user.full_name")
    email_verified = serializers.BooleanField(source="user.is_email_verified")
    company = serializers.CharField(source="company.name")
    job_title = serializers.CharField()
    approval_status = serializers.CharField()
    review_note = serializers.CharField()
    reviewed_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()


class ReviewSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=500, default="")


class DeliverySerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    kind = serializers.CharField(source="notification.kind")
    user = serializers.EmailField(source="notification.user.email")

    class Meta:
        model = Delivery
        fields = (
            "id",
            "kind",
            "user",
            "channel",
            "provider",
            "recipient",
            "status",
            "attempts",
            "last_error",
            "provider_message_id",
            "sent_at",
            "delivered_at",
            "created_at",
        )


class AuditLogSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = (
            "created_at",
            "actor",
            "action",
            "target_type",
            "target_id",
            "metadata",
            "ip_address",
            "user_agent",
        )

    def get_actor(self, entry) -> str | None:
        return entry.actor.email if entry.actor else None


class HeldFeedbackSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    recruiter = serializers.SerializerMethodField()
    job_seeker = serializers.EmailField(source="job_seeker.user.email")

    class Meta:
        model = Feedback
        fields = (
            "id",
            "company_name",
            "recruiter",
            "job_seeker",
            "status",
            "message",
            "moderation",
            "held_reason",
            "created_at",
        )

    def get_recruiter(self, feedback) -> str | None:
        return feedback.recruiter.email if feedback.recruiter else None


class AdminSkillSerializer(serializers.ModelSerializer):
    # Write-only here; to_representation() adds the alias list from the related rows.
    aliases = serializers.ListField(
        child=serializers.CharField(max_length=80), required=False, write_only=True
    )

    class Meta:
        model = Skill
        fields = ("name", "slug", "category", "aliases")
        extra_kwargs = {"slug": {"required": False}}

    def to_representation(self, skill):
        data = super().to_representation(skill)
        data["aliases"] = sorted(a.alias for a in skill.aliases.all())
        return data


class DependencyMappingSerializer(serializers.ModelSerializer):
    skill = serializers.SlugRelatedField(slug_field="name", queryset=Skill.objects.all())
    ecosystem = serializers.ChoiceField(choices=Ecosystem.choices)

    class Meta:
        model = DependencyMapping
        fields = ("ecosystem", "package_name", "skill")


CATEGORY_CHOICES = Category.choices
