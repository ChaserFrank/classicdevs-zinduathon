from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import health
from .serializers import HealthSerializer


class HealthView(APIView):
    """Liveness + readiness for Render/Railway health checks and the demo status page."""

    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = ()  # platforms poll this every few seconds

    @extend_schema(
        tags=["System"],
        summary="Health check",
        description=(
            "Checks PostgreSQL and Redis. Returns 200 when both answer, 503 otherwise, plus the "
            "running version and commit so you can confirm what is deployed."
        ),
        responses={200: HealthSerializer, 503: HealthSerializer},
        examples=[
            OpenApiExample(
                "Healthy",
                value={
                    "status": "ok",
                    "checks": {"database": "ok", "redis": "ok"},
                    "version": "0.1.0",
                    "commitSha": "59739f0",
                    "time": "2026-11-07T10:00:00+03:00",
                },
                response_only=True,
                status_codes=["200"],
            )
        ],
    )
    def get(self, request):
        checks = {
            "database": "ok" if health.check_database() else "down",
            "redis": "ok" if health.check_redis() else "down",
        }
        healthy = all(value == "ok" for value in checks.values())
        body = {
            "status": "ok" if healthy else "degraded",
            "checks": checks,
            "version": settings.APP_VERSION,
            "commit_sha": settings.GIT_COMMIT_SHA,
            "time": timezone.localtime().isoformat(),
        }
        return Response(body, status=status.HTTP_200_OK if healthy else 503)


def json_404(request, exception=None):
    """Unknown URLs answer in the API error shape instead of an HTML page."""
    return JsonResponse({"code": "not_found", "message": "Not found."}, status=404)


def json_500(request):
    return JsonResponse(
        {"code": "server_error", "message": "Something went wrong on our side. Try again."},
        status=500,
    )
