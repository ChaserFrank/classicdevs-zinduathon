from rest_framework import status

from apps.core.exceptions import ApiError


class AnalysisInProgress(ApiError):
    status_code = status.HTTP_409_CONFLICT
    default_code = "analysis_in_progress"
    default_detail = "An analysis of this GitHub account is already running. Check back shortly."


class GithubLoginRequired(ApiError):
    default_code = "validation_error"
    default_detail = "githubLogin is required."
