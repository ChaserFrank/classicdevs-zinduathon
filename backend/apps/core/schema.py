"""Helpers so every endpoint documents its error responses the same way."""

from drf_spectacular.utils import OpenApiExample, OpenApiResponse

from .serializers import ErrorSerializer

_STATUS_TEXT = {
    400: "Bad request",
    401: "Not signed in or token invalid",
    403: "Not allowed",
    404: "Not found",
    409: "Conflict",
    429: "Too many requests",
    503: "Dependency unavailable",
}


def errors(*pairs: tuple[int, str]) -> dict[int, OpenApiResponse]:
    """errors((400, "validation_error"), (401, "token_invalid")) → schema `responses` entries.

    Several codes may share a status; they are listed in the description and as examples.
    """
    by_status: dict[int, list[str]] = {}
    for status_code, code in pairs:
        by_status.setdefault(status_code, []).append(code)
    return {
        status_code: OpenApiResponse(
            response=ErrorSerializer,
            description=f"{_STATUS_TEXT.get(status_code, 'Error')}: "
            + ", ".join(f"`{c}`" for c in codes),
            examples=[
                OpenApiExample(code, value={"code": code, "message": "…"}, response_only=True)
                for code in codes
            ],
        )
        for status_code, codes in by_status.items()
    }
