"""Development-only GitHub sign-in pages, because there is no frontend yet.

`/auth/github/dev-login` sends the browser to GitHub; GitHub returns to `/auth/github/dev-callback`,
a small page that posts `code` + `state` to the real callback endpoint (exactly what the React
callback page will do) and shows the tokens so they can be pasted into Swagger's Authorize box.

Both answer 404 unless GITHUB_DEV_CALLBACK_ENABLED is true, which only dev settings allow.
"""

from django.conf import settings
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.views.decorators.http import require_GET

from . import github_oauth
from .errors import GithubNotConfigured
from .models import Role


def _ensure_enabled() -> None:
    if not settings.GITHUB_DEV_CALLBACK_ENABLED:
        raise Http404


@require_GET
def dev_login(request):
    _ensure_enabled()
    role = request.GET.get("role", Role.JOB_SEEKER)
    state = github_oauth.make_state(
        github_oauth.OAuthState(
            role=role if role in (Role.JOB_SEEKER, Role.RECRUITER) else Role.JOB_SEEKER,
            consents={"terms": True, "email_feedback": True, "sms_feedback": False},
        )
    )
    try:
        url = github_oauth.authorize_url(state)
    except GithubNotConfigured:
        return render(
            request,
            "accounts/github_dev_callback.html",
            {
                "error": "GitHub OAuth is not configured. Set GITHUB_OAUTH_CLIENT_ID and "
                "GITHUB_OAUTH_CLIENT_SECRET in backend/.env and restart the server."
            },
            status=503,
        )
    response = HttpResponseRedirect(url)
    # The callback page compares this with GitHub's `state` (what the SPA does with sessionStorage).
    response.set_cookie("sp_oauth_state", state, max_age=600, httponly=False, samesite="Lax")
    return response


@require_GET
def dev_callback(request):
    _ensure_enabled()
    return render(
        request,
        "accounts/github_dev_callback.html",
        {
            "code": request.GET.get("code", ""),
            "state": request.GET.get("state", ""),
            "error": request.GET.get("error_description") or request.GET.get("error", ""),
        },
    )
