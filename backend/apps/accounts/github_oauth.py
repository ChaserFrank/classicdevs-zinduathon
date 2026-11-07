"""GitHub OAuth 2.0 web flow for a single-page app.

The browser goes to GitHub with a signed `state`; GitHub sends it back with a one-time `code`; the
SPA posts both to us and we exchange the code server-side (the client secret never reaches the
browser). `state` is signed and expires after 10 minutes, so it can't be forged or replayed later.
"""

import secrets
from dataclasses import dataclass, field
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.core import signing

from .errors import GithubEmailUnverified, GithubNotConfigured, GithubOAuthFailed, StateInvalid

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"  # noqa: S105 - URL, not a secret
API_URL = "https://api.github.com"
STATE_SALT = "skillproof.github-oauth-state"
STATE_MAX_AGE = 600
TIMEOUT = 10


@dataclass(frozen=True)
class OAuthState:
    role: str = "job_seeker"
    link: bool = False
    consents: dict = field(default_factory=dict)


@dataclass(frozen=True)
class GithubIdentity:
    github_id: int
    login: str
    name: str | None
    avatar_url: str
    primary_email: str | None  # verified primary email, if any
    access_token: str
    scopes: str


def ensure_configured() -> None:
    if not (settings.GITHUB_OAUTH_CLIENT_ID and settings.GITHUB_OAUTH_CLIENT_SECRET):
        raise GithubNotConfigured()


def make_state(state: OAuthState) -> str:
    payload = {
        "r": state.role,
        "l": state.link,
        "c": state.consents,
        "n": secrets.token_urlsafe(8),  # makes every state unique
    }
    return signing.dumps(payload, salt=STATE_SALT, compress=True)


def read_state(value: str) -> OAuthState:
    try:
        data = signing.loads(value, salt=STATE_SALT, max_age=STATE_MAX_AGE)
    except signing.BadSignature as exc:
        raise StateInvalid() from exc
    return OAuthState(
        role=data.get("r", "job_seeker"), link=bool(data.get("l")), consents=data.get("c") or {}
    )


def authorize_url(state: str) -> str:
    ensure_configured()
    query = urlencode(
        {
            "client_id": settings.GITHUB_OAUTH_CLIENT_ID,
            "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URI,
            "scope": settings.GITHUB_OAUTH_SCOPES,
            "state": state,
            "allow_signup": "true",
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


def _api_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "SkillProof",
    }


def exchange_code(code: str) -> GithubIdentity:
    """Code → access token → profile + verified primary email."""
    ensure_configured()
    try:
        response = requests.post(
            TOKEN_URL,
            data={
                "client_id": settings.GITHUB_OAUTH_CLIENT_ID,
                "client_secret": settings.GITHUB_OAUTH_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.GITHUB_OAUTH_REDIRECT_URI,
            },
            headers={"Accept": "application/json"},
            timeout=TIMEOUT,
        )
        data = response.json() if response.ok else {}
    except (requests.RequestException, ValueError) as exc:
        raise GithubOAuthFailed("Could not reach GitHub. Try again.") from exc
    token = data.get("access_token")
    if not token:
        # e.g. {"error": "bad_verification_code"}: the code was used or expired.
        raise GithubOAuthFailed()

    try:
        user_resp = requests.get(f"{API_URL}/user", headers=_api_headers(token), timeout=TIMEOUT)
        emails_resp = requests.get(
            f"{API_URL}/user/emails", headers=_api_headers(token), timeout=TIMEOUT
        )
        user_resp.raise_for_status()
        profile = user_resp.json()
        emails = emails_resp.json() if emails_resp.ok else []
    except (requests.RequestException, ValueError) as exc:
        raise GithubOAuthFailed("Could not read your GitHub profile. Try again.") from exc

    primary = next(
        (
            e["email"]
            for e in emails
            if isinstance(e, dict) and e.get("primary") and e.get("verified")
        ),
        None,
    )
    return GithubIdentity(
        github_id=int(profile["id"]),
        login=profile["login"],
        name=profile.get("name"),
        avatar_url=profile.get("avatar_url") or "",
        primary_email=primary.lower() if primary else None,
        access_token=token,
        scopes=data.get("scope", ""),
    )


def require_email(identity: GithubIdentity) -> str:
    if not identity.primary_email:
        raise GithubEmailUnverified()
    return identity.primary_email
