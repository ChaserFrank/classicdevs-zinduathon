"""Building blocks every other app uses, plus the append-only audit log.

Why two id columns: the BigAutoField `id` is small and fast for joins, while `public_id` (UUID) is
what appears in URLs, so ids can't be guessed or enumerated (`/analyses/1`, `/analyses/2`, ...).
"""

import uuid

from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PublicIdModel(TimeStampedModel):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        abstract = True


class AuditLog(TimeStampedModel):
    """Who did what, to which object, from where. Append-only (no update/delete through the app).

    Needed to answer "who approved this recruiter?" or "when was this data exported?" and as
    evidence for the Kenya Data Protection Act 2019 obligations.
    """

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,  # keep the trail even after an account is deleted
        related_name="audit_entries",
    )
    action = models.CharField(max_length=64, db_index=True)
    target_type = models.CharField(max_length=64, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("actor", "-created_at"), name="core_audit_actor_idx")]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action} {self.target_type}:{self.target_id}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("Audit log entries are append-only.")
        super().save(*args, **kwargs)
