"""Request ID middleware.

Each request gets an id (reused from an incoming `X-Request-ID` when it looks safe, so a frontend or
proxy can correlate), stored for logging and echoed back in the response header. When a user
reports "it failed", the id in their browser's network tab finds the exact log lines.
"""

import re
import uuid

from .request_context import request_id_var

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{8,128}$")
HEADER = "X-Request-ID"


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.META.get("HTTP_X_REQUEST_ID", "")
        # Untrusted input goes into logs, so accept only a conservative character set.
        request_id = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex
        request.request_id = request_id
        token = request_id_var.set(request_id)
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response[HEADER] = request_id
        return response


HEALTH_PATH = "/api/v1/health"


class HealthCheckMiddleware:
    """Answer the platform health probe before Host validation and HTTPS redirects.

    Load balancers often probe over plain HTTP with an internal IP as the Host header, which
    ALLOWED_HOSTS (CommonMiddleware) would reject with 400 and SECURE_SSL_REDIRECT would bounce.
    The response is identical to the DRF view's; only GET/HEAD on the exact path are handled.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == HEALTH_PATH and request.method in ("GET", "HEAD"):
            from django.http import JsonResponse

            from .health import report

            body, status_code = report()
            return JsonResponse(body, status=status_code)
        return self.get_response(request)
