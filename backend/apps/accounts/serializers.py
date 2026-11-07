from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.companies.models import Company, RecruiterProfile

from . import phone as phone_utils
from .models import GithubAccount, JobSeekerProfile, Role, User


def normalise_phone_field(value: str | None, *, user: User | None = None) -> str | None:
    if not value:
        return None
    try:
        e164 = phone_utils.normalise(value)
    except phone_utils.InvalidPhone as exc:
        raise serializers.ValidationError(str(exc)) from exc
    clash = User.objects.filter(phone=e164)
    if user is not None:
        clash = clash.exclude(pk=user.pk)
    if clash.exists():
        raise serializers.ValidationError("This phone number is used by another account.")
    return e164


def validate_new_password(password: str, user: User) -> str:
    try:
        password_validation.validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages)) from exc
    return password


# --- Output: the signed-in user ("me") ---


class CompanySerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)

    class Meta:
        model = Company
        fields = ("id", "name", "website", "location", "is_verified")


class GithubAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = GithubAccount
        fields = ("login", "avatar_url", "connected_at")


class JobSeekerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobSeekerProfile
        fields = ("headline", "location", "card_visible", "open_to_work")


class RecruiterProfileSerializer(serializers.ModelSerializer):
    company = CompanySerializer()

    class Meta:
        model = RecruiterProfile
        fields = ("company", "job_title", "approval_status", "review_note", "reviewed_at")


class MeSerializer(serializers.ModelSerializer):
    """What the frontend needs after sign-in to route and render the account menu."""

    id = serializers.UUIDField(source="public_id", read_only=True)
    email_verified = serializers.BooleanField(source="is_email_verified", read_only=True)
    phone_verified = serializers.BooleanField(source="is_phone_verified", read_only=True)
    has_password = serializers.SerializerMethodField()
    github = serializers.SerializerMethodField()
    job_seeker_profile = serializers.SerializerMethodField()
    recruiter_profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "role",
            "full_name",
            "phone",
            "email_verified",
            "phone_verified",
            "has_password",
            "date_joined",
            "github",
            "job_seeker_profile",
            "recruiter_profile",
        )

    def get_has_password(self, user) -> bool:
        return user.has_usable_password()

    def _related(self, user, attr, serializer):
        obj = getattr(user, attr, None)
        return serializer(obj).data if obj is not None else None

    @extend_schema_field(GithubAccountSerializer(allow_null=True))
    def get_github(self, user):
        return self._related(user, "github_account", GithubAccountSerializer)

    @extend_schema_field(JobSeekerProfileSerializer(allow_null=True))
    def get_job_seeker_profile(self, user):
        return self._related(user, "job_seeker_profile", JobSeekerProfileSerializer)

    @extend_schema_field(RecruiterProfileSerializer(allow_null=True))
    def get_recruiter_profile(self, user):
        return self._related(user, "recruiter_profile", RecruiterProfileSerializer)


class AuthResponseSerializer(serializers.Serializer):
    """Same shape from register, login and the GitHub callback."""

    access = serializers.CharField()
    refresh = serializers.CharField()
    user = MeSerializer()


class GithubAuthResponseSerializer(AuthResponseSerializer):
    created = serializers.BooleanField(help_text="True when this sign-in created a new account.")


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


# --- Input ---


class ConsentsSerializer(serializers.Serializer):
    terms = serializers.BooleanField(help_text="Terms of service and privacy policy. Must be true.")
    email_feedback = serializers.BooleanField(default=False)
    sms_feedback = serializers.BooleanField(default=False)

    def validate_terms(self, value):
        if not value:
            raise serializers.ValidationError("You must accept the terms and privacy policy.")
        return value


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    role = serializers.ChoiceField(choices=[Role.JOB_SEEKER, Role.RECRUITER])
    full_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    company_name = serializers.CharField(required=False, allow_blank=True, max_length=120)
    job_title = serializers.CharField(required=False, allow_blank=True, max_length=120)
    consents = ConsentsSerializer()

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_phone(self, value):
        return normalise_phone_field(value)

    def validate(self, attrs):
        errors = {}
        if attrs["role"] == Role.RECRUITER and not (attrs.get("company_name") or "").strip():
            errors["company_name"] = ["Recruiters must name their company."]
        if attrs["consents"].get("sms_feedback") and not attrs.get("phone"):
            errors["phone"] = ["Add a phone number to receive feedback by SMS."]
        candidate = User(email=attrs["email"], full_name=attrs.get("full_name", ""))
        try:
            validate_new_password(attrs["password"], candidate)
        except serializers.ValidationError as exc:
            errors["password"] = exc.detail
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class TokenSerializer(serializers.Serializer):
    token = serializers.CharField(help_text="The token from the emailed link.")


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = self.context["request"].user
        # GitHub-only accounts have no password yet; they may set one without a current password.
        if user.has_usable_password() and not user.check_password(
            attrs.get("current_password", "")
        ):
            raise serializers.ValidationError({"current_password": ["Current password is wrong."]})
        attrs["new_password"] = validate_new_password(attrs["new_password"], user)
        return attrs


class PhoneSendCodeSerializer(serializers.Serializer):
    phone = serializers.CharField(
        required=False, help_text="Optional: set or change the number before sending the code."
    )

    def validate_phone(self, value):
        return normalise_phone_field(value, user=self.context["request"].user)


class PhoneSendCodeResponseSerializer(serializers.Serializer):
    phone = serializers.CharField()
    expires_at = serializers.DateTimeField()
    dev_code = serializers.CharField(
        required=False, help_text="Only in local development while SMS is dry-run."
    )


class PhoneVerifySerializer(serializers.Serializer):
    code = serializers.RegexField(
        r"^\s*\d{6}\s*$", error_messages={"invalid": "Enter the 6-digit code."}
    )


class GithubAuthorizeResponseSerializer(serializers.Serializer):
    authorize_url = serializers.URLField()
    state = serializers.CharField()


class GithubCallbackSerializer(serializers.Serializer):
    code = serializers.CharField()
    state = serializers.CharField()


class MeUpdateSerializer(serializers.Serializer):
    """Flat PATCH body; fields are routed to the user or the role profile."""

    full_name = serializers.CharField(max_length=150, required=False)
    phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    headline = serializers.CharField(max_length=160, required=False, allow_blank=True)
    location = serializers.CharField(max_length=120, required=False, allow_blank=True)
    card_visible = serializers.BooleanField(required=False)
    open_to_work = serializers.BooleanField(required=False)
    job_title = serializers.CharField(max_length=120, required=False, allow_blank=True)

    JOB_SEEKER_FIELDS = ("headline", "location", "card_visible", "open_to_work")
    RECRUITER_FIELDS = ("job_title",)

    def validate_phone(self, value):
        return normalise_phone_field(value, user=self.context["request"].user)

    def validate(self, attrs):
        role = self.context["request"].user.role
        allowed = {
            Role.JOB_SEEKER: self.JOB_SEEKER_FIELDS,
            Role.RECRUITER: self.RECRUITER_FIELDS,
        }.get(role, ())
        not_allowed = (
            set(attrs) & (set(self.JOB_SEEKER_FIELDS) | set(self.RECRUITER_FIELDS))
        ) - set(allowed)
        if not_allowed:
            raise serializers.ValidationError(
                {field: ["Not available for your role."] for field in sorted(not_allowed)}
            )
        return attrs
