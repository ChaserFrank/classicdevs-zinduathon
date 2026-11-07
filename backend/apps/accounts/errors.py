"""Domain errors for accounts and auth. Each has a stable `code` the frontend can switch on."""

from rest_framework import status

from apps.core.exceptions import ApiError


class InvalidCredentials(ApiError):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_code = "invalid_credentials"
    default_detail = "Email or password is incorrect."


class TokenInvalid(ApiError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "token_invalid"
    default_detail = "This link is invalid or has expired. Request a new one."


class StateInvalid(ApiError):
    default_code = "state_invalid"
    default_detail = "The sign-in attempt expired or was tampered with. Start again."


class GithubNotConfigured(ApiError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = "github_not_configured"
    default_detail = "GitHub sign-in is not configured on this server."


class GithubOAuthFailed(ApiError):
    default_code = "github_oauth_failed"
    default_detail = "GitHub did not accept the sign-in. Start again."


class GithubEmailUnverified(ApiError):
    default_code = "github_email_unverified"
    default_detail = "Your GitHub account has no verified primary email. Verify one on GitHub."


class GithubAlreadyLinked(ApiError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "github_already_linked"
    default_detail = "That GitHub account is linked to a different SkillProof account."


class GithubNotLinked(ApiError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "github_not_linked"
    default_detail = "No GitHub account is linked."


class PasswordRequired(ApiError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "password_required"
    default_detail = "Set a password before unlinking GitHub, or you would be locked out."


class TermsRequired(ApiError):
    default_code = "terms_required"
    default_detail = "Accept the terms and privacy policy to create an account."


class RecruiterSignupNeedsEmail(ApiError):
    default_code = "recruiter_signup_requires_email"
    default_detail = "Recruiters register with email first, then link GitHub from settings."


class EmailNotVerified(ApiError):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "email_not_verified"
    default_detail = "Verify your email address first."


class PhoneMissing(ApiError):
    default_code = "phone_missing"
    default_detail = "Add a phone number first."


class CodeInvalid(ApiError):
    default_code = "code_invalid"
    default_detail = "That code is wrong or has expired."


class CodeAttemptsExceeded(ApiError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_code = "code_attempts_exceeded"
    default_detail = "Too many wrong codes. Request a new one."


class RefreshTokenInvalid(ApiError):
    """401 even on views without authenticators (DRF would otherwise turn 401 into 403)."""

    status_code = status.HTTP_401_UNAUTHORIZED
    default_code = "token_invalid"
    default_detail = "Your session has expired or the token is invalid. Sign in again."
