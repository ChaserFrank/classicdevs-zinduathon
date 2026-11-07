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


class JobSeekerProfile(TimeStampedModel):
    """Job-seeker-only fields. 1:1 with User so the user table stays role-neutral."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="job_seeker_profile")
    headline = models.CharField(max_length=160, blank=True)
    location = models.CharField(max_length=120, blank=True)
    card_visible = models.BooleanField(
        default=True, help_text="Recruiters can find and view this card."
    )
    open_to_work = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"Job seeker {self.user.email}"


class GithubAccount(TimeStampedModel):
    """The GitHub identity proven by OAuth. A job seeker's analysed login comes from here, which is
    what makes `verifiedOwner` true on their card."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="github_account")
    github_id = models.BigIntegerField(unique=True)
    login = models.CharField(max_length=39, unique=True, help_text="Lowercase GitHub login")
    avatar_url = models.URLField(max_length=500, blank=True)
    # Fernet ciphertext; use set_token()/get_token(). Never logged, never returned by the API.
    access_token_encrypted = models.TextField(blank=True)
    token_scopes = models.CharField(max_length=255, blank=True)
    connected_at = models.DateTimeField(default=timezone.now)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return self.login

    def save(self, *args, **kwargs):
        self.login = (self.login or "").lower()
        super().save(*args, **kwargs)

    def set_token(self, token: str) -> None:
        from apps.core.crypto import encrypt

        self.access_token_encrypted = encrypt(token)

    def get_token(self) -> str:
        from apps.core.crypto import decrypt

        return decrypt(self.access_token_encrypted)


class ConsentType(models.TextChoices):
    TERMS = "terms", "Terms of service"
    PRIVACY = "privacy", "Privacy policy"
    SMS_FEEDBACK = "sms_feedback", "Feedback by SMS"
    EMAIL_FEEDBACK = "email_feedback", "Feedback by email"


class ConsentRecord(models.Model):
    """Append-only consent history (Kenya Data Protection Act 2019): we can show when each consent
    was given or withdrawn and under which policy version. The latest row per type wins."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="consents")
    consent_type = models.CharField(max_length=20, choices=ConsentType.choices)
    granted = models.BooleanField()
    policy_version = models.CharField(max_length=32)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(consent_type__in=ConsentType.values),
                name="accounts_consent_type_valid",
            )
        ]
        indexes = [
            models.Index(
                fields=("user", "consent_type", "-created_at"), name="accounts_consent_idx"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id} {self.consent_type}={self.granted}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("Consent records are append-only; add a new row instead.")
        super().save(*args, **kwargs)


class VerificationPurpose(models.TextChoices):
    VERIFY_EMAIL = "verify_email", "Verify email"
    VERIFY_PHONE = "verify_phone", "Verify phone"
    RESET_PASSWORD = "reset_password", "Reset password"


class VerificationCode(TimeStampedModel):
    """Short codes sent by SMS. Only an HMAC of the code is stored, so a database leak doesn't
    reveal live codes. Email links use signed tokens instead (see tokens.py)."""

    MAX_ATTEMPTS = 5

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="verification_codes")
    purpose = models.CharField(max_length=20, choices=VerificationPurpose.choices)
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(purpose__in=VerificationPurpose.values),
                name="accounts_verification_purpose_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(attempts__gte=0) & models.Q(attempts__lte=5),
                name="accounts_verification_attempts_range",
            ),
        ]
        indexes = [models.Index(fields=("user", "purpose", "-created_at"), name="accounts_vc_idx")]

    @property
    def is_usable(self) -> bool:
        return (
            self.used_at is None
            and self.attempts < self.MAX_ATTEMPTS
            and self.expires_at > timezone.now()
        )
