"""In-app inbox, per-channel preferences, and one Delivery row per email/SMS attempt.

Every outbound message is logged as a Delivery (including skipped and dry-run ones) so admins can
answer "did this job seeker get the feedback?" and retry failures.
"""

from django.conf import settings
from django.db import models

from apps.core.models import PublicIdModel, TimeStampedModel


class Kind(models.TextChoices):
    ANALYSIS_COMPLETED = "analysis_completed", "Analysis completed"
    ANALYSIS_FAILED = "analysis_failed", "Analysis failed"
    RECRUITER_FEEDBACK = "recruiter_feedback", "Recruiter feedback"
    RECRUITER_APPROVED = "recruiter_approved", "Recruiter approved"
    RECRUITER_REJECTED = "recruiter_rejected", "Recruiter rejected"
    SHORTLISTED = "shortlisted", "Shortlisted"
    PROFILE_VIEWED_DIGEST = "profile_viewed_digest", "Weekly profile views"


class Channel(models.TextChoices):
    IN_APP = "in_app", "In-app"
    EMAIL = "email", "Email"
    SMS = "sms", "SMS"


class Notification(PublicIdModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    kind = models.CharField(max_length=32, choices=Kind.choices)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    link_path = models.CharField(max_length=200, blank=True, help_text="Path on FRONTEND_URL")
    # `feedback` (FK to recruiting.Feedback) is added in Phase 5 with the recruiting app.
    analysis = models.ForeignKey(
        "analysis.Analysis", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("user", "read_at", "-created_at"), name="notif_inbox_idx")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind__in=Kind.values), name="notif_kind_valid"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} {self.kind}"


class NotificationPreference(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preferences"
    )
    kind = models.CharField(max_length=32, choices=Kind.choices)
    channel = models.CharField(max_length=8, choices=Channel.choices)
    enabled = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("user", "kind", "channel"), name="notif_pref_unique"),
            models.CheckConstraint(
                condition=models.Q(kind__in=Kind.values), name="notif_pref_kind_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(channel__in=Channel.values), name="notif_pref_channel_valid"
            ),
        ]


class DeliveryStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    SENT = "sent", "Sent"
    DELIVERED = "delivered", "Delivered"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"
    DRY_RUN = "dry_run", "Dry run"


class Provider(models.TextChoices):
    SMTP = "smtp", "SMTP"
    THRIVEWAVE = "thrivewave", "Thrivewave"


class Delivery(TimeStampedModel):
    MAX_ATTEMPTS = 3

    notification = models.ForeignKey(
        Notification, on_delete=models.CASCADE, related_name="deliveries"
    )
    channel = models.CharField(max_length=8, choices=[(c, c) for c in ("email", "sms")])
    recipient = models.CharField(max_length=254, blank=True)
    status = models.CharField(
        max_length=12, choices=DeliveryStatus.choices, default=DeliveryStatus.QUEUED
    )
    provider = models.CharField(max_length=16, choices=Provider.choices)
    provider_message_id = models.CharField(max_length=128, blank=True)
    provider_response = models.JSONField(default=dict, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.CharField(max_length=300, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "deliveries"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("status",), name="delivery_status_idx"),
            models.Index(fields=("provider_message_id",), name="delivery_provider_msg_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=DeliveryStatus.values), name="delivery_status_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(channel__in=["email", "sms"]), name="delivery_channel_valid"
            ),
        ]
