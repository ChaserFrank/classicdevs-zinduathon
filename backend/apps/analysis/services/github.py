"""Step 1: collect evidence from GitHub (brief 8.1). The only module that talks to GitHub.

Everything is converted to `Repo`/`Commit` dataclasses before it leaves this module.

Rate-limit economics: with a token GitHub allows 5,000 requests/hour (60 without). Responses are
cached with their ETag; a repeat request sends `If-None-Match` and a 304 reply is free. Total commit
counts use `per_page=1` and the `Link: rel="last"` page number, which costs one request whatever the
repo size.
"""

import base64
import logging
import random
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import requests

from .manifests import MANIFEST_FILES
from .types import Commit, Repo

logger = logging.getLogger(__name__)

API_VERSION = "2022-11-28"
PER_PAGE = 100
MAX_COMMIT_PAGES = 3  # up to 300 of the user's commits per repo
MAX_MANIFESTS = 5
TIMEOUT = 10
_SKIP_DIRS = ("node_modules/", "vendor/", "dist/", "build/", ".venv/", "venv/")
_LAST_PAGE = re.compile(r'[?&]page=(\d+)>;\s*rel="last"')
_NEXT = re.compile(r'<([^>]+)>;\s*rel="next"')


# --- Errors ---


class GithubError(Exception):
    code = "github_error"
    message = "GitHub could not be read. Try again later."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.message)
        self.message = message or self.message


class UserNotFound(GithubError):
    code = "not_found"
    message = "That GitHub user does not exist."


class NoPublicRepos(GithubError):
    code = "no_public_repos"
    message = "This GitHub account has no public, non-fork repositories with code to analyse."


class GitHubRateLimited(GithubError):
    code = "github_rate_limited"

    def __init__(self, reset_at: datetime | None = None):
        self.reset_at = reset_at
        when = f" after {reset_at:%H:%M} UTC" if reset_at else " later"
        super().__init__(f"GitHub's rate limit was reached. Try again{when}.")


class GithubUnavailable(GithubError):
    code = "github_unavailable"


class _NotFound(Exception):
    pass


# --- Cache ---


class NullCache:
    def get(self, url: str):
        return None

    def set(self, url: str, etag: str, payload: dict) -> None:
        return None


class DbCache:
    """ETag cache in the analysis_githubcache table, 24 h TTL."""

    def __init__(self, ttl_hours: int = 24):
        self.ttl = timedelta(hours=ttl_hours)

    def get(self, url: str):
        from apps.analysis.models import GithubCache

        row = GithubCache.objects.filter(url=url[:500]).first()
        if row is None or row.fetched_at < datetime.now(UTC) - self.ttl:
            return None
        return row.etag, row.payload

    def set(self, url: str, etag: str, payload: dict) -> None:
        from apps.analysis.models import GithubCache

        GithubCache.objects.update_or_create(
            url=url[:500],
            defaults={"etag": etag, "payload": payload, "fetched_at": datetime.now(UTC)},
        )


# --- Client ---


@dataclass(frozen=True)
class Profile:
    login: str
    name: str | None
    avatar_url: str


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class GithubClient:
    def __init__(
        self,
        token: str = "",
        *,
        base_url: str = "https://api.github.com",
        cache=None,
        session: requests.Session | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.cache = cache or NullCache()
        self.session = session or requests.Session()
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "SkillProof",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def get(self, path: str, params: dict | None = None, *, url: str | None = None) -> dict:
        """GET with ETag caching. Returns {"data": json, "link": Link header}.
        Raises _NotFound on 404, GitHubRateLimited, GithubUnavailable."""
        if url is None:
            query = f"?{urlencode(sorted((params or {}).items()))}" if params else ""
            url = f"{self.base_url}{path}{query}"
        cached = self.cache.get(url)
        headers = dict(self.headers)
        if cached and cached[0]:
            headers["If-None-Match"] = cached[0]
        try:
            response = self.session.get(url, headers=headers, timeout=TIMEOUT)
        except requests.RequestException as exc:
            raise GithubUnavailable() from exc

        if response.status_code == 304 and cached:
            return cached[1]
        if response.status_code in (403, 429) and (
            response.headers.get("X-RateLimit-Remaining") == "0"
            or "rate limit" in response.text.lower()
        ):
            reset = response.headers.get("X-RateLimit-Reset")
            raise GitHubRateLimited(datetime.fromtimestamp(int(reset), UTC) if reset else None)
        if response.status_code == 404:
            raise _NotFound(url)
        if response.status_code == 409:  # "Git Repository is empty"
            return {"data": None, "link": ""}
        if response.status_code >= 400:
            raise GithubUnavailable(f"GitHub answered {response.status_code}.")
        try:
            data = response.json()
        except ValueError as exc:
            raise GithubUnavailable() from exc
        payload = {"data": data, "link": response.headers.get("Link", "")}
        if etag := response.headers.get("ETag"):
            self.cache.set(url, etag, payload)
        return payload

    # --- Endpoints ---

    def profile(self, login: str) -> Profile:
        try:
            data = self.get(f"/users/{login}")["data"]
        except _NotFound as exc:
            raise UserNotFound() from exc
        return Profile(
            login=data["login"], name=data.get("name"), avatar_url=data.get("avatar_url") or ""
        )

    def owned_repos(self, login: str) -> list[dict]:
        try:
            data = self.get(
                f"/users/{login}/repos", {"type": "owner", "sort": "pushed", "per_page": PER_PAGE}
            )["data"]
        except _NotFound as exc:
            raise UserNotFound() from exc
        return data or []

    def languages(self, full_name: str) -> dict[str, int]:
        return self._safe(lambda: self.get(f"/repos/{full_name}/languages")["data"], {}) or {}

    def user_commits(self, full_name: str, login: str) -> list[Commit]:
        commits: list[Commit] = []
        try:
            page = self.get(f"/repos/{full_name}/commits", {"author": login, "per_page": PER_PAGE})
        except _NotFound:
            return []
        for _ in range(MAX_COMMIT_PAGES):
            for item in page["data"] or []:
                date = _parse_date(((item.get("commit") or {}).get("author") or {}).get("date"))
                if date:
                    commits.append(Commit(sha=item["sha"], date=date))
            match = _NEXT.search(page["link"] or "")
            if not match:
                break
            page = self.get("", url=match.group(1))
        return commits

    def commit_count(self, full_name: str) -> int:
        try:
            page = self.get(f"/repos/{full_name}/commits", {"per_page": 1})
        except _NotFound:
            return 0
        match = _LAST_PAGE.search(page["link"] or "")
        if match:
            return int(match.group(1))
        return len(page["data"] or [])

    def commit_stats(self, full_name: str, sha: str) -> tuple[int, int] | None:
        def fetch():
            stats = (self.get(f"/repos/{full_name}/commits/{sha}")["data"] or {}).get("stats") or {}
            return int(stats.get("additions", 0)), int(stats.get("deletions", 0))

        return self._safe(fetch, None)

    def tree(self, full_name: str, branch: str) -> list[str]:
        def fetch():
            data = self.get(f"/repos/{full_name}/git/trees/{branch}", {"recursive": 1})["data"]
            return [i["path"] for i in (data or {}).get("tree", []) if i.get("type") == "blob"]

        return self._safe(fetch, [])

    def file_text(self, full_name: str, path: str) -> str:
        def fetch():
            data = self.get(f"/repos/{full_name}/contents/{path}")["data"] or {}
            if data.get("encoding") != "base64":
                return ""
            return base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")

        return self._safe(fetch, "")

    def readme_size(self, full_name: str) -> int:
        return self._safe(
            lambda: int((self.get(f"/repos/{full_name}/readme")["data"] or {}).get("size", 0)), 0
        )

    @staticmethod
    def _safe(fn: Callable, default):
        """Per-repo details are best-effort: a missing README or tree must not fail the analysis.
        Rate limits still propagate."""
        try:
            return fn()
        except _NotFound:
            return default
        except GithubUnavailable:
            logger.warning("GitHub detail request failed; continuing without it")
            return default


# --- Orchestration ---


def manifest_paths(tree_paths: list[str]) -> list[str]:
    """Manifests at the root or one directory down (monorepos: frontend/, backend/)."""
    found = [
        path
        for path in tree_paths
        if path.rsplit("/", 1)[-1] in MANIFEST_FILES
        and path.count("/") <= 1
        and not path.startswith(_SKIP_DIRS)
    ]
    return sorted(found, key=lambda p: (p.count("/"), p))[:MAX_MANIFESTS]


def sample_commits(commits: list[Commit], full_name: str, size: int) -> list[Commit]:
    """Deterministic sample (seeded by repo name): the same history always gives the same score."""
    if len(commits) <= size:
        return list(commits)
    return random.Random(full_name).sample(commits, size)  # noqa: S311 - not security related


def fetch_repo(client: GithubClient, raw: dict, login: str, commit_sample: int) -> Repo:
    full_name = raw["full_name"]
    commits = client.user_commits(full_name, login)
    stats = {}
    for commit in sample_commits(commits, full_name, commit_sample):
        if (result := client.commit_stats(full_name, commit.sha)) is not None:
            stats[commit.sha] = result
    commits = [Commit(c.sha, c.date, *stats[c.sha]) if c.sha in stats else c for c in commits]
    tree = client.tree(full_name, raw.get("default_branch") or "main")
    return Repo(
        github_id=raw["id"],
        owner=raw["owner"]["login"],
        name=raw["name"],
        html_url=raw["html_url"],
        default_branch=raw.get("default_branch") or "",
        is_fork=bool(raw.get("fork")),
        pushed_at=_parse_date(raw.get("pushed_at")),
        languages=client.languages(full_name),
        user_commits=commits,
        user_commit_count=len(commits),
        total_commits=max(client.commit_count(full_name), len(commits)),
        tree_paths=tree,
        manifests={p: client.file_text(full_name, p) for p in manifest_paths(tree)},
        readme_size=client.readme_size(full_name),
    )


def fetch_profile(
    client: GithubClient,
    login: str,
    *,
    max_repos: int = 15,
    commit_sample: int = 20,
    workers: int = 5,
    on_repos_listed: Callable[[], None] | None = None,
) -> tuple[Profile, list[Repo]]:
    profile = client.profile(login)
    candidates = [
        r
        for r in client.owned_repos(login)
        if not r.get("fork")
        and r.get("size", 0) > 0  # empty repos report size 0
        and (r.get("owner") or {}).get("login", "").lower() == login.lower()
    ][:max_repos]
    if not candidates:
        raise NoPublicRepos()
    if on_repos_listed:
        on_repos_listed()

    def work(raw):
        try:
            return fetch_repo(client, raw, profile.login, commit_sample)
        finally:
            if workers > 1:
                from django.db import connection

                connection.close()  # each worker thread opened its own DB connection (cache)

    if workers <= 1:
        repos = [work(raw) for raw in candidates]
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            repos = list(pool.map(work, candidates))
    return profile, repos
