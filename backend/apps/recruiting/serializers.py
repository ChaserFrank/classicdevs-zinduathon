from rest_framework import serializers

from apps.analysis.serializers import CardSerializer

from .models import (
    LABEL_CHOICES,
    EmploymentType,
    Feedback,
    FeedbackStatus,
    JobPosting,
    JobStatus,
    RemotePolicy,
    ShortlistEntry,
    Stage,
)

# Recruiters never see emails or phone numbers: no serializer here exposes them.


class TopSkillSerializer(serializers.Serializer):
    name = serializers.CharField()
    label = serializers.CharField()


class CandidateSerializer(serializers.Serializer):
    github_login = serializers.CharField()
    name = serializers.CharField(allow_blank=True)
    headline = serializers.CharField(allow_blank=True)
    location = serializers.CharField(allow_blank=True)
    avatar_url = serializers.CharField(allow_blank=True)
    open_to_work = serializers.BooleanField()
    signal_score = serializers.IntegerField()
    analysed_at = serializers.DateTimeField()
    top_skills = TopSkillSerializer(many=True)


class MatchSerializer(serializers.Serializer):
    score = serializers.IntegerField(min_value=0, max_value=100)
    met = serializers.ListField(child=serializers.CharField())
    partial = serializers.ListField(
        child=serializers.CharField(), help_text="One level below: half credit"
    )
    missing = serializers.ListField(child=serializers.CharField())


class CandidateMatchSerializer(CandidateSerializer):
    match = MatchSerializer()


class CandidateSearchParamsSerializer(serializers.Serializer):
    skills = serializers.CharField(
        required=False, allow_blank=True, help_text="Comma-separated names, slugs or aliases"
    )
    min_label = serializers.ChoiceField(choices=[c for c, _ in LABEL_CHOICES], default="emerging")
    min_score = serializers.IntegerField(required=False, min_value=0, max_value=100)
    open_to_work = serializers.BooleanField(required=False, allow_null=True, default=None)
    search = serializers.CharField(required=False, allow_blank=True, default="")
    ordering = serializers.ChoiceField(
        choices=["-signalScore", "signalScore", "-analysedAt", "analysedAt"], default="-signalScore"
    )


class FeedbackCreateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=FeedbackStatus.choices)
    message = serializers.CharField(
        max_length=5000, help_text="Max 1,000 characters after HTML is stripped"
    )
    job_posting_id = serializers.UUIDField(required=False, allow_null=True)


class JobRefSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="public_id")
    title = serializers.CharField()


class FeedbackSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    company = serializers.CharField(source="company_name")
    recruiter_name = serializers.SerializerMethodField()
    candidate = serializers.SerializerMethodField()
    job_posting = JobRefSerializer(allow_null=True)

    class Meta:
        model = Feedback
        fields = (
            "id",
            "status",
            "message",
            "company",
            "recruiter_name",
            "candidate",
            "job_posting",
            "moderation",
            "read_at",
            "created_at",
        )

    def get_recruiter_name(self, obj) -> str:
        return (obj.recruiter.full_name if obj.recruiter else "") or "A recruiter"

    def get_candidate(self, obj) -> dict | None:
        """Only for the sender's view: who the feedback was about."""
        if not self.context.get("show_candidate"):
            return None
        user = obj.job_seeker.user
        account = getattr(user, "github_account", None)
        return {"githubLogin": account.login if account else "", "name": user.full_name}


class RequiredSkillSerializer(serializers.Serializer):
    skill = serializers.CharField(help_text="Name, slug or alias")
    minimum_label = serializers.ChoiceField(
        choices=[c for c, _ in LABEL_CHOICES], default="moderate"
    )
    weight = serializers.IntegerField(min_value=1, max_value=3, default=1)


class JobSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    company = serializers.CharField(source="company.name", read_only=True)
    required_skills = serializers.SerializerMethodField()

    class Meta:
        model = JobPosting
        fields = (
            "id",
            "company",
            "title",
            "description",
            "location",
            "employment_type",
            "remote_policy",
            "status",
            "closes_at",
            "required_skills",
            "created_at",
            "updated_at",
        )

    def get_required_skills(self, obj) -> list[dict]:
        return [
            {"skill": r.skill.name, "minimum_label": r.minimum_label, "weight": r.weight}
            for r in obj.required_skills.all()
        ]


class JobWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=120)
    description = serializers.CharField(required=False, allow_blank=True)
    location = serializers.CharField(required=False, allow_blank=True, max_length=120)
    employment_type = serializers.ChoiceField(
        choices=EmploymentType.choices, default=EmploymentType.FULL_TIME
    )
    remote_policy = serializers.ChoiceField(
        choices=RemotePolicy.choices, default=RemotePolicy.ONSITE
    )
    status = serializers.ChoiceField(choices=JobStatus.choices, default=JobStatus.DRAFT)
    closes_at = serializers.DateTimeField(required=False, allow_null=True)
    required_skills = RequiredSkillSerializer(many=True, required=False)
    company_id = serializers.UUIDField(required=False, help_text="Admins only")


class ShortlistSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    candidate = serializers.SerializerMethodField()
    job_posting = JobRefSerializer(allow_null=True)

    class Meta:
        model = ShortlistEntry
        fields = ("id", "candidate", "job_posting", "stage", "note", "created_at", "updated_at")

    def get_candidate(self, obj) -> dict:
        user = obj.job_seeker.user
        account = getattr(user, "github_account", None)
        return {
            "githubLogin": account.login if account else "",
            "name": user.full_name,
            "headline": obj.job_seeker.headline,
        }


class ShortlistCreateSerializer(serializers.Serializer):
    github_login = serializers.CharField()
    job_posting_id = serializers.UUIDField(required=False, allow_null=True)
    stage = serializers.ChoiceField(choices=Stage.choices, default=Stage.SAVED)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500, default="")
    notify_candidate = serializers.BooleanField(
        default=False, help_text="Tell the job seeker (in-app, email, SMS)"
    )


class ShortlistUpdateSerializer(serializers.Serializer):
    stage = serializers.ChoiceField(choices=Stage.choices, required=False)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)
    notify_candidate = serializers.BooleanField(default=False)
    feedback_message = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Also send feedback (e.g. when moving to interview)",
    )


class CandidateDetailSerializer(serializers.Serializer):
    candidate = CandidateSerializer()
    card = CardSerializer()
    shortlist = ShortlistSerializer(many=True)
    feedback_sent = FeedbackSerializer(many=True)


class ProfileViewWeekSerializer(serializers.Serializer):
    week_start = serializers.DateField()
    recruiters = serializers.IntegerField()


class ProfileViewsSerializer(serializers.Serializer):
    this_week = serializers.IntegerField(help_text="Distinct recruiters in the last 7 days")
    weeks = ProfileViewWeekSerializer(many=True)
