"""The single user table for all three roles.

Why one table with a `role` column rather than separate user types: sign-in, tokens, notifications
and audit all work the same for everyone. Role-specific data lives in 1:1 profile tables (added in
Phase 2), which keeps this table narrow and in 3NF.
"""

import uuid

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from apps.core.models import TimeStampedModel

from .managers import UserManager


class Role(models.TextChoices):
    JOB_SEEKER = "job_seeker", "Job seeker"
    RECRUITER = "recruiter", "Recruiter"
    ADMIN = "admin", "Admin"


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    # unique=True satisfies Django auth; the Lower() constraint below also blocks case variants
    # written by raw SQL or bulk_create, which bypass save().
    email = models.EmailField(max_length=254, unique=True)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.JOB_SEEKER)
    full_name = models.CharField(max_length=150, blank=True)
    # NULL (not "") when absent so the partial unique constraint allows many users without a phone.
    phone = models.CharField(  # noqa: DJ001
        max_length=16, null=True, blank=True, help_text="E.164, e.g. +254712345678"
    )
    email_verified_at = models.DateTimeField(null=True, blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False, help_text="Can sign in to /django-admin/.")
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        ordering = ("-date_joined",)
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique"),
            models.UniqueConstraint(
                fields=("phone",),
                condition=models.Q(phone__isnull=False),
                name="accounts_user_phone_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(role__in=Role.values), name="accounts_user_role_valid"
            ),
        ]
        indexes = [models.Index(fields=("role",), name="accounts_user_role_idx")]

    def __str__(self) -> str:
        return self.email

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        if self.phone == "":
            self.phone = None
        super().save(*args, **kwargs)

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None

    @property
    def is_phone_verified(self) -> bool:
        return self.phone_verified_at is not None
