"""Auth and profile endpoints. Thin views: validation in serializers, workflows in services."""

from django.conf import settings
from django.contrib.auth import authenticate
from django.db import transaction
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core import audit
from apps.core.schema import errors

from . import emails, github_oauth, services, tokens
from .errors import InvalidCredentials, RefreshTokenInvalid, TokenInvalid
from .models import Role, User
from .serializers import (
    AuthResponseSerializer,
    EmailSerializer,
    GithubAuthorizeResponseSerializer,
    GithubAuthResponseSerializer,
    GithubCallbackSerializer,
    LoginSerializer,
    MeSerializer,
    MeUpdateSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PhoneSendCodeResponseSerializer,
    PhoneSendCodeSerializer,
    PhoneVerifySerializer,
    RefreshSerializer,
    RegisterSerializer,
    TokenPairSerializer,
    TokenSerializer,
)
from .throttles import LoginThrottle

_USER_RELATED = ("job_seeker_profile", "recruiter_profile__company", "github_account")


def fresh_user(user: User) -> User:
    """Reload with profiles in one query so MeSerializer doesn't trigger N lookups."""
    return User.objects.select_related(*_USER_RELATED).get(pk=user.pk)


def auth_payload(user: User, **extra) -> dict:
    user = fresh_user(user)
    return {**tokens.issue_tokens(user), "user": MeSerializer(user).data, **extra}


ME_EXAMPLE = {
    "id": "6f1c7a2e-4c9b-4d1f-9a0e-2b8f1d3c5e7a",
    "email": "wanjiru@example.com",
    "role": "job_seeker",
    "fullName": "Wanjiru Kamau",
    "phone": "+254712345678",
    "emailVerified": True,
    "phoneVerified": False,
    "hasPassword": True,
    "dateJoined": "2026-11-07T10:00:00+03:00",
    "github": {
        "login": "wanjiru-dev",
        "avatarUrl": "https://avatars.githubusercontent.com/u/1",
        "connectedAt": "2026-11-07T10:05:00+03:00",
    },
    "jobSeekerProfile": {
        "headline": "Full-stack developer",
        "location": "Nairobi",
        "cardVisible": True,
        "openToWork": True,
    },
    "recruiterProfile": None,
}
AUTH_EXAMPLE = OpenApiExample(
    "Signed in",
    value={"access": "eyJhbGciOi…", "refresh": "eyJhbGciOi…", "user": ME_EXAMPLE},
    response_only=True,
)


class RegisterView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(
        tags=["Auth"],
        summary="Register with email and password",
        description=(
            "Creates a job seeker or recruiter (recruiters start `pending` until an admin approves "
            "them) and emails a verification link. `consents.terms` must be true. A phone number "
            "is required when `consents.smsFeedback` is true. Returns tokens and the user."
        ),
        request=RegisterSerializer,
        responses={
            201: AuthResponseSerializer,
            **errors((400, "validation_error"), (429, "rate_limited")),
        },
        examples=[
            OpenApiExample(
                "Job seeker",
                value={
                    "email": "wanjiru@example.com",
                    "password": "correct-horse-battery",
                    "role": "job_seeker",
                    "fullName": "Wanjiru Kamau",
                    "phone": "0712345678",
                    "consents": {"terms": True, "emailFeedback": True, "smsFeedback": True},
                },
                request_only=True,
            ),
            OpenApiExample(
                "Recruiter",
                value={
                    "email": "otieno@acme.co.ke",
                    "password": "correct-horse-battery",
                    "role": "recruiter",
                    "fullName": "Brian Otieno",
                    "companyName": "Acme Kenya",
                    "jobTitle": "Talent lead",
                    "consents": {"terms": True, "emailFeedback": True},
                },
                request_only=True,
            ),
            AUTH_EXAMPLE,
        ],
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.register(data=serializer.validated_data, request=request)
        return Response(auth_payload(user), status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (LoginThrottle,)

    @extend_schema(
        tags=["Auth"],
        summary="Sign in with email and password",
        description="Throttled to 5 attempts per minute per IP and email.",
        request=LoginSerializer,
        responses={
            200: AuthResponseSerializer,
            **errors(
                (400, "validation_error"), (401, "invalid_credentials"), (429, "rate_limited")
            ),
        },
        examples=[
            OpenApiExample(
                "Credentials",
                value={"email": "wanjiru@example.com", "password": "correct-horse-battery"},
                request_only=True,
            ),
            AUTH_EXAMPLE,
        ],
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower()
        user = authenticate(request, username=email, password=serializer.validated_data["password"])
        if user is None:
            audit.record("auth.sign_in_failed", request=request, metadata={"email": email})
            raise InvalidCredentials()
        audit.record(
            "auth.sign_in", actor=user, target=user, request=request, metadata={"via": "password"}
        )
        return Response(auth_payload(user))


class RefreshView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(
        tags=["Auth"],
        summary="Refresh tokens",
        description=(
            "Exchanges a refresh token for a new access token **and** a new refresh token. The old "
            "refresh token is blacklisted (rotation), so each refresh token works once. Claims "
            "(role, approval status, GitHub login) are re-read from the database."
        ),
        request=RefreshSerializer,
        responses={
            200: TokenPairSerializer,
            **errors((400, "validation_error"), (401, "token_invalid")),
        },
    )
    def post(self, request):
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            old = RefreshToken(serializer.validated_data["refresh"])
        except TokenError as exc:
            raise RefreshTokenInvalid() from exc
        user = User.objects.filter(public_id=old.get("user_id"), is_active=True).first()
        if user is None:
            raise RefreshTokenInvalid()
        old.blacklist()
        return Response(tokens.issue_tokens(user, update_login=False))


class LogoutView(APIView):
    @extend_schema(
        tags=["Auth"],
        summary="Sign out",
        description="Blacklists the given refresh token. The access token expires on its own.",
        request=RefreshSerializer,
        responses={204: None, **errors((400, "validation_error"), (401, "token_invalid"))},
    )
    def post(self, request):
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = RefreshToken(serializer.validated_data["refresh"])
        except TokenError as exc:
            raise RefreshTokenInvalid() from exc
        if token.get("user_id") != str(request.user.public_id):
            raise RefreshTokenInvalid("This refresh token belongs to another user.")
        token.blacklist()
        audit.record("auth.sign_out", actor=request.user, target=request.user, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Email verification and passwords ---


class EmailVerifyView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(
        tags=["Auth"],
        summary="Verify email",
        description="Posts the token from the emailed link. Idempotent.",
        request=TokenSerializer,
        responses={200: MeSerializer, **errors((400, "token_invalid"))},
    )
    def post(self, request):
        serializer = TokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = tokens.read_email_token(serializer.validated_data["token"])
        if user is None:
            raise TokenInvalid()
        services.verify_email(user, request)
        return Response(MeSerializer(fresh_user(user)).data)


class EmailResendView(APIView):
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "password_reset"  # same budget as reset emails: 5/hour

    @extend_schema(
        tags=["Auth"],
        summary="Resend the verification email",
        request=None,
        responses={204: None, **errors((401, "not_authenticated"), (429, "rate_limited"))},
    )
    def post(self, request):
        if not request.user.is_email_verified:
            emails.send_verification_email(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "password_reset"

    @extend_schema(
        tags=["Auth"],
        summary="Request a password reset email",
        description="Always answers 204, whether or not the email exists (no account enumeration).",
        request=EmailSerializer,
        responses={204: None, **errors((400, "validation_error"), (429, "rate_limited"))},
    )
    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(
            email__iexact=serializer.validated_data["email"], is_active=True
        ).first()
        if user is not None:
            emails.send_password_reset_email(user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetConfirmView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(
        tags=["Auth"],
        summary="Set a new password from a reset link",
        description="The link works once and for 1 hour. Signs the user out everywhere.",
        request=PasswordResetConfirmSerializer,
        responses={204: None, **errors((400, "token_invalid"), (400, "validation_error"))},
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = tokens.read_reset_token(serializer.validated_data["token"])
        if user is None:
            raise TokenInvalid()
        from rest_framework.exceptions import ValidationError

        from .serializers import validate_new_password

        try:
            password = validate_new_password(serializer.validated_data["new_password"], user)
        except ValidationError as exc:
            raise ValidationError({"new_password": exc.detail}) from exc
        services.change_password(user, password, request, action="auth.password_reset")
        if not user.is_email_verified:  # they proved control of the inbox
            services.verify_email(user, request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordChangeView(APIView):
    @extend_schema(
        tags=["Auth"],
        summary="Change password",
        description=(
            "Requires the current password, except for GitHub-only accounts setting their first "
            "password. Signs out other devices and returns a fresh token pair."
        ),
        request=PasswordChangeSerializer,
        responses={
            200: TokenPairSerializer,
            **errors((400, "validation_error"), (401, "not_authenticated")),
        },
    )
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        services.change_password(request.user, serializer.validated_data["new_password"], request)
        return Response(tokens.issue_tokens(request.user, update_login=False))


# --- Phone verification ---


class PhoneSendCodeView(APIView):
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "phone_code"

    @extend_schema(
        tags=["Auth"],
        summary="Send a phone verification code by SMS",
        description=(
            "Optionally sets/changes the phone first (Kenyan formats accepted: 07…, 01…, +254…, "
            "254…). Sends a 6-digit code valid for 10 minutes. Throttled to 3 per hour. While SMS "
            "is "
            "in dry-run mode in local development, the response includes `devCode`."
        ),
        request=PhoneSendCodeSerializer,
        responses={
            202: PhoneSendCodeResponseSerializer,
            **errors((400, "validation_error"), (400, "phone_missing"), (429, "rate_limited")),
        },
    )
    def post(self, request):
        serializer = PhoneSendCodeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        if "phone" in serializer.validated_data:
            services.set_phone(request.user, serializer.validated_data["phone"])
        record, code = services.send_phone_code(request.user)
        body = {"phone": request.user.phone, "expires_at": record.expires_at}
        if settings.SMS_DEV_ECHO_CODES and settings.SMS_DRY_RUN:
            body["dev_code"] = code
        return Response(body, status=status.HTTP_202_ACCEPTED)


class PhoneVerifyView(APIView):
    @extend_schema(
        tags=["Auth"],
        summary="Verify the phone with the SMS code",
        description="Five wrong attempts invalidate the code.",
        request=PhoneVerifySerializer,
        responses={
            200: MeSerializer,
            **errors(
                (400, "code_invalid"), (400, "validation_error"), (429, "code_attempts_exceeded")
            ),
        },
    )
    def post(self, request):
        serializer = PhoneVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.verify_phone_code(request.user, serializer.validated_data["code"], request)
        return Response(MeSerializer(fresh_user(request.user)).data)


# --- GitHub OAuth ---


GITHUB_AUTHORIZE_PARAMS = [
    OpenApiParameter(
        "role",
        str,
        enum=["job_seeker", "recruiter"],
        description="For new sign-ups. Default job_seeker. Recruiters can only link.",
    ),
    OpenApiParameter(
        "link", bool, description="True when linking GitHub to the signed-in account from settings."
    ),
    OpenApiParameter(
        "acceptTerms", bool, description="Required true for a first-time GitHub sign-up."
    ),
    OpenApiParameter("emailFeedback", bool),
    OpenApiParameter("smsFeedback", bool),
]


def _flag(request, name: str) -> bool:
    return str(request.query_params.get(name, "")).lower() in {"1", "true", "yes"}


def build_state(request) -> github_oauth.OAuthState:
    role = request.query_params.get("role", Role.JOB_SEEKER)
    consents = {}
    if _flag(request, "accept_terms"):
        consents = {
            "terms": True,
            "email_feedback": _flag(request, "email_feedback"),
            "sms_feedback": _flag(request, "sms_feedback"),
        }
    return github_oauth.OAuthState(
        role=role if role in (Role.JOB_SEEKER, Role.RECRUITER) else Role.JOB_SEEKER,
        link=_flag(request, "link"),
        consents=consents,
    )


class GithubAuthorizeView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(
        tags=["Auth"],
        summary="Start GitHub sign-in",
        description=(
            "Returns the GitHub URL to send the browser to, with a signed `state` (10 minutes). "
            "Keep `state` in sessionStorage and compare it on the callback page."
        ),
        parameters=GITHUB_AUTHORIZE_PARAMS,
        responses={
            200: GithubAuthorizeResponseSerializer,
            **errors((503, "github_not_configured")),
        },
    )
    def get(self, request):
        state = github_oauth.make_state(build_state(request))
        return Response({"authorize_url": github_oauth.authorize_url(state), "state": state})


class GithubCallbackView(APIView):
    permission_classes = (AllowAny,)  # a JWT is optional: present when linking from settings

    @extend_schema(
        tags=["Auth"],
        summary="Finish GitHub sign-in",
        description=(
            "Exchanges GitHub's `code`. Known GitHub account → signs in. Signed-in caller → links "
            "GitHub to them. Matching verified email → links and signs in. Otherwise creates a job "
            "seeker (requires `acceptTerms` at authorize time). Stores the GitHub token encrypted."
        ),
        request=GithubCallbackSerializer,
        responses={
            200: GithubAuthResponseSerializer,
            **errors(
                (400, "state_invalid"),
                (400, "github_oauth_failed"),
                (400, "github_email_unverified"),
                (400, "terms_required"),
                (400, "recruiter_signup_requires_email"),
                (409, "github_already_linked"),
                (503, "github_not_configured"),
            ),
        },
    )
    def post(self, request):
        serializer = GithubCallbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        state = github_oauth.read_state(serializer.validated_data["state"])
        identity = github_oauth.exchange_code(serializer.validated_data["code"])
        user, created = services.github_sign_in(
            identity, state, current_user=request.user, request=request
        )
        return Response(auth_payload(user, created=created))


class GithubUnlinkView(APIView):
    @extend_schema(
        tags=["Auth"],
        summary="Unlink GitHub",
        description="Refused when the account has no password (you would be locked out).",
        request=None,
        responses={204: None, **errors((400, "github_not_linked"), (409, "password_required"))},
    )
    def delete(self, request):
        services.unlink_github(request.user, request)
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Me ---


class MeView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Profile"],
        summary="Current user",
        responses={200: MeSerializer, **errors((401, "not_authenticated"))},
        examples=[OpenApiExample("Job seeker", value=ME_EXAMPLE, response_only=True)],
    )
    def get(self, request):
        return Response(MeSerializer(fresh_user(request.user)).data)

    @extend_schema(
        tags=["Profile"],
        summary="Update profile",
        description=(
            "Flat body. Job seekers: fullName, phone, headline, location, cardVisible, openToWork. "
            "Recruiters: fullName, phone, jobTitle. Changing the phone marks it unverified."
        ),
        request=MeUpdateSerializer,
        responses={
            200: MeSerializer,
            **errors((400, "validation_error"), (401, "not_authenticated")),
        },
        examples=[
            OpenApiExample(
                "Hide card",
                value={"cardVisible": False, "headline": "Backend dev"},
                request_only=True,
            )
        ],
    )
    @transaction.atomic
    def patch(self, request):
        serializer = MeUpdateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = request.user
        if "full_name" in data:
            user.full_name = data["full_name"]
            user.save(update_fields=["full_name", "updated_at"])
        if "phone" in data:
            services.set_phone(user, data["phone"])
        profile = getattr(user, "job_seeker_profile", None) or getattr(
            user, "recruiter_profile", None
        )
        profile_fields = [f for f in data if hasattr(profile, f) and f not in ("phone",)]
        profile_fields = [f for f in profile_fields if f != "full_name"]
        if profile is not None and profile_fields:
            for name in profile_fields:
                setattr(profile, name, data[name])
            profile.save(update_fields=[*profile_fields, "updated_at"])
        return Response(MeSerializer(fresh_user(user)).data)
