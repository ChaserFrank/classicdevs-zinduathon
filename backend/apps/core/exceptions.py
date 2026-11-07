"""One error shape for the whole API: `{"code", "message", "fields"?}`.

The frontend switches on `code` (stable, machine-readable) and may show `message` (human sentence).
`fields` appears only for validation errors and maps each field to its messages, so forms can show
errors next to inputs. Raise `ApiError` subclasses for domain errors such as `no_public_repos`.
"""

import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


class ApiError(exceptions.APIException):
    """Base for domain errors. Subclass with `status_code`, `default_code`, `default_detail`."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "bad_request"
    default_detail = "The request could not be processed."

    def __init__(self, message: str | None = None, *, code: str | None = None):
        super().__init__(detail=message or self.default_detail, code=code or self.default_code)


# Map DRF's built-in exceptions to our documented codes.
_CODE_BY_EXCEPTION: list[tuple[type[Exception], str]] = [
    (exceptions.ValidationError, "validation_error"),
    (exceptions.NotAuthenticated, "not_authenticated"),
    (exceptions.AuthenticationFailed, "token_invalid"),
    (exceptions.PermissionDenied, "permission_denied"),
    (exceptions.NotFound, "not_found"),
    (exceptions.Throttled, "rate_limited"),
    (exceptions.MethodNotAllowed, "method_not_allowed"),
    (exceptions.NotAcceptable, "not_acceptable"),
    (exceptions.UnsupportedMediaType, "unsupported_media_type"),
    (exceptions.ParseError, "parse_error"),
]

_DEFAULT_MESSAGES = {
    "validation_error": "Some fields are invalid.",
    "not_authenticated": "Sign in to continue.",
    "token_invalid": "Your session has expired or the token is invalid. Sign in again.",
    "not_found": "Not found.",
}


def _first_message(detail) -> str:
    if isinstance(detail, list):
        return _first_message(detail[0]) if detail else ""
    if isinstance(detail, dict):
        return _first_message(next(iter(detail.values()))) if detail else ""
    return str(detail)


def _code_for(exc: exceptions.APIException) -> str:
    # A specific code on a PermissionDenied (e.g. "recruiter_not_approved") wins over the generic.
    detail_code = exc.get_codes() if not isinstance(exc, exceptions.ValidationError) else None
    if isinstance(exc, ApiError):
        return str(detail_code or exc.default_code)
    for exc_type, code in _CODE_BY_EXCEPTION:
        if isinstance(exc, exc_type):
            if (
                isinstance(detail_code, str)
                and detail_code != exc_type.default_code
                and exc_type is exceptions.PermissionDenied
            ):
                return detail_code
            return code
    return str(detail_code or "error")


def _fields(detail) -> dict[str, list[str]]:
    """Flatten DRF's nested validation detail into {field: [messages]}; nested keys use dots."""
    out: dict[str, list[str]] = {}

    def walk(prefix: str, value) -> None:
        if isinstance(value, dict):
            for key, inner in value.items():
                walk(f"{prefix}.{key}" if prefix else str(key), inner)
        elif (
            isinstance(value, list)
            and value
            and all(not isinstance(v, (dict, list)) for v in value)
        ):
            out.setdefault(prefix or "nonFieldErrors", []).extend(str(v) for v in value)
        elif isinstance(value, list):
            for index, inner in enumerate(value):
                walk(f"{prefix}.{index}" if prefix else str(index), inner)
        else:
            out.setdefault(prefix or "nonFieldErrors", []).append(str(value))

    walk("", detail)
    return out


def api_exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    response = drf_exception_handler(exc, context)
    if response is None:
        # Unexpected error: log with traceback (Sentry picks it up) and hide internals.
        logger.exception("Unhandled API error", exc_info=exc)
        return Response(
            {"code": "server_error", "message": "Something went wrong on our side. Try again."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    code = _code_for(exc)
    if isinstance(exc, exceptions.ValidationError):
        body = {
            "code": code,
            "message": _DEFAULT_MESSAGES["validation_error"],
            "fields": _fields(exc.detail),
        }
    else:
        message = _first_message(exc.detail) or _DEFAULT_MESSAGES.get(code, "Request failed.")
        if isinstance(exc, exceptions.NotAuthenticated):
            message = _DEFAULT_MESSAGES["not_authenticated"]
        body = {"code": code, "message": message}
        if isinstance(exc, exceptions.Throttled) and exc.wait is not None:
            body["message"] = f"Too many requests. Try again in {int(exc.wait)} seconds."

    response.data = body
    return response
