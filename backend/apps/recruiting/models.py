"""Job postings, shortlists, feedback and profile views: the recruiter side of SkillProof."""

from django.conf import settings
from django.db import models

from apps.core.models import PublicIdModel, TimeStampedModel

LABEL_CHOICES = [("emerging", "Emerging"), ("moderate", "Moderate"), ("strong", "Strong")]


class EmploymentType(models.TextChoices):
    FULL_TIME = "full_time", "Full-time"
    PART_TIME = "part_time", "Part-time"
    CONTRACT = "contract", "Contract"
    INTERNSHIP = "internship", "Internship"


class RemotePolicy(models.TextChoices):
    ONSITE = "onsite", "On-site"
    HYBRID = "hybrid", "Hybrid"
    REMOTE = "remote", "Remote"


class JobStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    OPEN = "open", "Open"
    CLOSED = "closed", "Closed"


class JobPosting(PublicIdModel):
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="jobs")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="job_postings"
    )
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=120, blank=True)
    employment_type = models.CharField(
        max_length=12, choices=EmploymentType.choices, default=EmploymentType.FULL_TIME
    )
    remote_policy = models.CharField(
        max_length=8, choices=RemotePolicy.choices, default=RemotePolicy.ONSITE
    )
    status = models.CharField(max_length=8, choices=JobStatus.choices, default=JobStatus.DRAFT)
    closes_at = models.DateTimeField(null=True, blank=True)
    skills = models.ManyToManyField("skills.Skill", through="JobRequiredSkill", related_name="+")

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("status", "-created_at"), name="job_status_idx")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(employment_type__in=EmploymentType.values),
                name="job_employment_type_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(remote_policy__in=RemotePolicy.values), name="job_remote_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=JobStatus.values), name="job_status_valid"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.title} @ {self.company}"


class JobRequiredSkill(TimeStampedModel):
    job_posting = models.ForeignKey(
        JobPosting, on_delete=models.CASCADE, related_name="required_skills"
    )
    skill = models.ForeignKey("skills.Skill", on_delete=models.PROTECT, related_name="+")
    minimum_label = models.CharField(max_length=10, choices=LABEL_CHOICES, default="moderate")
    weight = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ("-weight", "id")
        constraints = [
            models.UniqueConstraint(fields=("job_posting", "skill"), name="job_skill_unique"),
            models.CheckConstraint(
                condition=models.Q(weight__gte=1, weight__lte=3), name="job_skill_weight_range"
            ),
            models.CheckConstraint(
                condition=models.Q(minimum_label__in=["emerging", "moderate", "strong"]),
                name="job_skill_label_valid",
            ),
        ]


class Stage(models.TextChoices):
    SAVED = "saved", "Saved"
    CONTACTED = "contacted", "Contacted"
    INTERVIEW = "interview", "Interview"
    OFFER = "offer", "Offer"
    REJECTED = "rejected", "Rejected"


class ShortlistEntry(PublicIdModel):
    recruiter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shortlist"
    )
    job_seeker = models.ForeignKey(
        "accounts.JobSeekerProfile", on_delete=models.CASCADE, related_name="shortlisted_by"
    )
    job_posting = models.ForeignKey(
        JobPosting, null=True, blank=True, on_delete=models.CASCADE, related_name="shortlist"
    )
    stage = models.CharField(max_length=10, choices=Stage.choices, default=Stage.SAVED)
    note = models.CharField(max_length=500, blank=True, help_text="Private to the recruiter")

    class Meta:
        verbose_name_plural = "shortlist entries"
        ordering = ("-updated_at",)
        constraints = [
            # NULLs are distinct in a plain unique constraint, so "no job" needs its own.
            models.UniqueConstraint(
                fields=("recruiter", "job_seeker", "job_posting"), name="shortlist_unique"
            ),
            models.UniqueConstraint(
                fields=("recruiter", "job_seeker"),
                condition=models.Q(job_posting__isnull=True),
                name="shortlist_unique_without_job",
            ),
            models.CheckConstraint(
                condition=models.Q(stage__in=Stage.values), name="shortlist_stage_valid"
            ),
        ]


class FeedbackStatus(models.TextChoices):
    SHORTLISTED = "shortlisted", "Shortlisted"
    INTERVIEW = "interview", "Interview"
    NOT_A_FIT = "not_a_fit", "Not a fit"
    GENERAL = "general", "General"


class Moderation(models.TextChoices):
    SENT = "sent", "Sent"
    HELD = "held", "Held for review"
    REJECTED = "rejected", "Rejected by admin"


class Feedback(PublicIdModel):
    MAX_LENGTH = 1000

    recruiter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,  # kept (anonymised) when the recruiter deletes their account
        on_delete=models.SET_NULL,
        related_name="feedback_sent",
    )
    job_seeker = models.ForeignKey(
        "accounts.JobSeekerProfile", on_delete=models.CASCADE, related_name="feedback_received"
    )
    analysis = models.ForeignKey(
        "analysis.Analysis", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    job_posting = models.ForeignKey(
        JobPosting, null=True, blank=True, on_delete=models.SET_NULL, related_name="feedback"
    )
    company_name = models.CharField(
        max_length=120, help_text="Snapshot, so feedback reads correctly after changes"
    )
    status = models.CharField(max_length=12, choices=FeedbackStatus.choices)
    message = models.TextField(max_length=MAX_LENGTH)
    moderation = models.CharField(
        max_length=10, choices=Moderation.choices, default=Moderation.SENT
    )
    held_reason = models.CharField(max_length=200, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("job_seeker", "-created_at"), name="feedback_seeker_idx"),
            models.Index(fields=("moderation",), name="feedback_moderation_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=FeedbackStatus.values), name="feedback_status_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(moderation__in=Moderation.values),
                name="feedback_moderation_valid",
            ),
        ]


class ProfileView(TimeStampedModel):
    """A recruiter opened a job seeker's card. Job seekers see counts, never names."""

    recruiter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile_views"
    )
    job_seeker = models.ForeignKey(
        "accounts.JobSeekerProfile", on_delete=models.CASCADE, related_name="views"
    )
    viewed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=("job_seeker", "-viewed_at"), name="profileview_seeker_idx")]
