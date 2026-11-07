"""Companies and the recruiters who belong to them.

Recruiters start `pending`: anyone can claim to be a recruiter, and recruiters see job seekers'
cards and can message them, so an admin approves each one (after the email is verified).
"""

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

from apps.core.models import PublicIdModel, TimeStampedModel


class Company(PublicIdModel):
    name = models.CharField(max_length=120)
    website = models.URLField(blank=True)
    location = models.CharField(max_length=120, blank=True)
    is_verified = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "companies"
        ordering = ("name",)
        constraints = [models.UniqueConstraint(Lower("name"), name="companies_company_name_ci")]

    def __str__(self) -> str:
        return self.name


class ApprovalStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    SUSPENDED = "suspended", "Suspended"


class RecruiterProfile(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recruiter_profile"
    )
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="recruiters")
    job_title = models.CharField(max_length=120, blank=True)
    approval_status = models.CharField(
        max_length=16, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recruiter_reviews",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(approval_status__in=ApprovalStatus.values),
                name="companies_recruiter_status_valid",
            )
        ]
        indexes = [models.Index(fields=("approval_status",), name="companies_rp_status_idx")]

    def __str__(self) -> str:
        return f"{self.user.email} @ {self.company.name} ({self.approval_status})"

    @property
    def is_approved(self) -> bool:
        return self.approval_status == ApprovalStatus.APPROVED
