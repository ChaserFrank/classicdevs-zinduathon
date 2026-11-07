"""Analyses and the evidence behind every number on a skill card.

Why rows and not a JSON blob: recruiters filter by skill, label and score (Phase 5), sub-scores are
charted over time, and every number must be traceable to the repos that produced it. Normalised
rows make those queries indexable and keep each fact in one place.
"""

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

from apps.core.models import PublicIdModel, TimeStampedModel


class Repository(TimeStampedModel):
    """A public GitHub repo. Shared across analyses so history refers to the same row."""

    github_id = models.BigIntegerField(unique=True)
    owner_login = models.CharField(max_length=39, db_index=True)
    name = models.CharField(max_length=100)
    html_url = models.URLField(max_length=300)
    is_fork = models.BooleanField(default=False)
    default_branch = models.CharField(max_length=255, blank=True)
    pushed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "repositories"

    def __str__(self) -> str:
        return f"{self.owner_login}/{self.name}"


class AnalysisStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    RUNNING = "running", "Running"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class SummarySource(models.TextChoices):
    LLM = "llm", "LLM"
    TEMPLATE = "template", "Template"


class Analysis(PublicIdModel):
    job_seeker = models.ForeignKey(
        "accounts.JobSeekerProfile",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="analyses",
        help_text="Null for admin-run analyses of any login.",
    )
    github_login = models.CharField(max_length=39, help_text="Lowercase")
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    status = models.CharField(
        max_length=12, choices=AnalysisStatus.choices, default=AnalysisStatus.QUEUED
    )
    progress_step = models.PositiveSmallIntegerField(
        default=0, help_text="1 reading repos · 2 reading commits · 3 finding skills · 4 scoring"
    )
    error_code = models.CharField(max_length=40, blank=True)
    error_message = models.CharField(max_length=300, blank=True)
    # Snapshot of the GitHub profile at analysis time (shown on the card).
    github_name = models.CharField(max_length=255, blank=True)
    avatar_url = models.URLField(max_length=500, blank=True)
    signal_score = models.PositiveSmallIntegerField(null=True, blank=True)
    ai_summary = models.TextField(blank=True)
    summary_source = models.CharField(max_length=8, choices=SummarySource.choices, blank=True)
    tips = models.JSONField(default=list, blank=True, help_text="Up to 3 improvement tips (text)")
    repos_analysed = models.PositiveSmallIntegerField(default=0)
    commits_analysed = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "analyses"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("github_login", "-created_at"), name="analysis_login_created_idx"),
            models.Index(fields=("status",), name="analysis_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=AnalysisStatus.values),
                name="analysis_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(signal_score__isnull=True)
                | models.Q(signal_score__gte=0, signal_score__lte=100),
                name="analysis_signal_score_range",
            ),
            models.CheckConstraint(
                condition=models.Q(progress_step__lte=4), name="analysis_progress_range"
            ),
            models.CheckConstraint(
                condition=models.Q(summary_source__in=["", *SummarySource.values]),
                name="analysis_summary_source_valid",
            ),
            # At most one queued/running analysis per login (enforced by the database too).
            models.UniqueConstraint(
                fields=("github_login",),
                condition=models.Q(status__in=["queued", "running"]),
                name="analysis_one_active_per_login",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.github_login} {self.status} {self.signal_score}"

    def save(self, *args, **kwargs):
        self.github_login = (self.github_login or "").lower()
        super().save(*args, **kwargs)


class SubScoreKey(models.TextChoices):
    CONSISTENCY = "consistency", "Consistency"
    ITERATION = "iteration", "Iteration"
    QUALITY = "quality", "Quality practices"
    BREADTH = "breadth", "Breadth"
    OWNERSHIP = "ownership", "Ownership"


class SubScore(TimeStampedModel):
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE, related_name="subscores")
    key = models.CharField(max_length=12, choices=SubScoreKey.choices)
    value = models.PositiveSmallIntegerField()
    reason = models.CharField(max_length=300)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("analysis", "key"), name="analysis_subscore_unique"),
            models.CheckConstraint(
                condition=models.Q(value__gte=0, value__lte=20), name="analysis_subscore_range"
            ),
            models.CheckConstraint(
                condition=models.Q(key__in=SubScoreKey.values), name="analysis_subscore_key_valid"
            ),
        ]


class AnalysisRepository(TimeStampedModel):
    """The evidence row the UI shows: what we measured in one repo during one analysis."""

    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE, related_name="repo_rows")
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name="+")
    user_commits = models.PositiveIntegerField(default=0)
    total_commits = models.PositiveIntegerField(default=0)
    first_commit_at = models.DateTimeField(null=True, blank=True)
    last_commit_at = models.DateTimeField(null=True, blank=True)
    has_tests = models.BooleanField(default=False)
    has_ci = models.BooleanField(default=False)
    readme_length = models.PositiveIntegerField(default=0)
    sampled_additions = models.PositiveIntegerField(default=0)
    sampled_deletions = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("analysis", "repository"), name="analysis_repo_unique")
        ]


class SkillLabel(models.TextChoices):
    STRONG = "strong", "Strong"
    MODERATE = "moderate", "Moderate"
    EMERGING = "emerging", "Emerging"
    UNVERIFIED = "unverified", "Unverified"


class AnalysisSkill(TimeStampedModel):
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE, related_name="skill_rows")
    skill = models.ForeignKey("skills.Skill", on_delete=models.PROTECT, related_name="+")
    evidence = models.DecimalField(max_digits=5, decimal_places=2)
    label = models.CharField(max_length=12, choices=SkillLabel.choices)
    repos = models.ManyToManyField(
        AnalysisRepository, through="SkillEvidence", related_name="skills"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("analysis", "skill"), name="analysis_skill_unique"),
            models.CheckConstraint(
                condition=models.Q(evidence__gte=0), name="analysis_skill_evidence_nonneg"
            ),
            models.CheckConstraint(
                condition=models.Q(label__in=SkillLabel.values), name="analysis_skill_label_valid"
            ),
        ]
        indexes = [models.Index(fields=("skill", "label"), name="analysis_skill_label_idx")]


class SkillEvidence(TimeStampedModel):
    """Which repos prove which skill (through table)."""

    analysis_skill = models.ForeignKey(AnalysisSkill, on_delete=models.CASCADE)
    analysis_repository = models.ForeignKey(AnalysisRepository, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("analysis_skill", "analysis_repository"), name="analysis_evidence_unique"
            )
        ]


class ClaimedSkill(TimeStampedModel):
    """What the job seeker says on their CV (max 12), checked against evidence on each analysis."""

    MAX_PER_USER = 12

    job_seeker = models.ForeignKey(
        "accounts.JobSeekerProfile", on_delete=models.CASCADE, related_name="claimed_skills"
    )
    raw_text = models.CharField(max_length=80)
    skill = models.ForeignKey(
        "skills.Skill", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(
                "job_seeker", Lower("raw_text"), name="analysis_claimed_unique_text"
            )
        ]

    def __str__(self) -> str:
        return self.raw_text


class ClaimStatus(models.TextChoices):
    VERIFIED = "verified", "Verified"
    PARTLY = "partly", "Partly"
    UNVERIFIED = "unverified", "Unverified"


class ClaimResult(TimeStampedModel):
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE, related_name="claim_results")
    claimed_skill = models.ForeignKey(ClaimedSkill, on_delete=models.CASCADE, related_name="+")
    status = models.CharField(max_length=12, choices=ClaimStatus.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("analysis", "claimed_skill"), name="analysis_claimresult_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=ClaimStatus.values),
                name="analysis_claimresult_status_valid",
            ),
        ]


class FlagType(models.TextChoices):
    ONE_SHOT_DUMP = "one_shot_dump", "One-shot code dump"
    UNEXPLAINED_BULK = "unexplained_bulk", "Unexplained bulk commit"
    TUTORIAL_CLONE = "tutorial_clone", "Tutorial clone"
    UNVERIFIED_CLAIM = "unverified_claim", "Unverified claim"


class Flag(TimeStampedModel):
    analysis = models.ForeignKey(Analysis, on_delete=models.CASCADE, related_name="flags")
    type = models.CharField(max_length=20, choices=FlagType.choices)
    analysis_repository = models.ForeignKey(
        AnalysisRepository, null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    claimed_skill = models.ForeignKey(
        ClaimedSkill, null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    reason = models.CharField(max_length=300)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(type__in=FlagType.values), name="analysis_flag_type_valid"
            )
        ]


class GithubCache(TimeStampedModel):
    """Raw GitHub responses with their ETag. Conditional requests answered 304 don't count
    against the rate limit, so re-analysing a profile costs almost nothing."""

    url = models.CharField(max_length=500, unique=True)
    etag = models.CharField(max_length=200, blank=True)
    payload = models.JSONField()
    fetched_at = models.DateTimeField(db_index=True)
