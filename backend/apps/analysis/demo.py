"""Demo personas: realistic GitHub accounts served without the network.

Each persona file in `demo_personas/` describes an account compactly (repos, languages, commit
series, file tree, manifests). `routes()` expands it into the exact responses GitHub's REST API
would give, including pagination and Link headers. Two consumers:

- `ReplaySession` plugs into GithubClient so `seed_demo` runs the *real* pipeline on personas
  (no network, works on a fresh deploy at the venue);
- the tests register the same routes with `responses`.
"""

import base64
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import requests

API = "https://api.github.com"
PERSONA_DIR = Path(__file__).parent / "demo_personas"


@dataclass(frozen=True)
class Route:
    url: str
    params: dict = field(default_factory=dict)
    json: object = None
    status: int = 200
    headers: dict = field(default_factory=dict)


def persona_names() -> list[str]:
    return sorted(p.stem for p in PERSONA_DIR.glob("*.json"))


def load_persona(name: str, directory: Path = PERSONA_DIR) -> dict:
    return json.loads((directory / f"{name}.json").read_text())


def expand_commits(repo: dict) -> list[dict]:
    commits = list(repo.get("commits", []))
    for series in repo.get("commit_series", []):
        start = datetime.fromisoformat(series["start"])
        for i in range(series["count"]):
            commits.append(
                {
                    "sha": f"{repo['name']}-{series.get('prefix', 's')}{i}",
                    "date": (start + timedelta(days=i * series["every_days"])).isoformat(),
                    "additions": series["additions"],
                    "deletions": series["deletions"],
                }
            )
    return sorted(commits, key=lambda c: c["date"], reverse=True)  # GitHub: newest first


def _commit_json(c: dict, login: str) -> dict:
    return {
        "sha": c["sha"],
        "author": {"login": login},
        "commit": {"author": {"date": c["date"].replace("+00:00", "Z")}, "message": "work"},
    }


def routes(persona: dict) -> list[Route]:
    login = persona["login"]
    out = [
        Route(
            f"{API}/users/{login}",
            json={
                "login": login,
                "id": persona.get("id", 1),
                "name": persona.get("name"),
                "avatar_url": f"https://avatars.githubusercontent.com/{login}",
            },
        )
    ]
    listing = []
    for i, repo in enumerate(persona["repos"]):
        listing.append(
            {
                "id": repo.get("id", 100 + i),
                "name": repo["name"],
                "full_name": f"{login}/{repo['name']}",
                "owner": {"login": login},
                "html_url": f"https://github.com/{login}/{repo['name']}",
                "fork": repo.get("fork", False),
                "size": repo.get("size", 100),
                "default_branch": repo.get("default_branch", "main"),
                "pushed_at": repo.get("pushed_at", "2026-11-01T00:00:00Z"),
            }
        )
    out.append(
        Route(
            f"{API}/users/{login}/repos",
            {"type": "owner", "sort": "pushed", "per_page": "100"},
            listing,
        )
    )

    for repo in persona["repos"]:
        if repo.get("fork") or repo.get("size", 100) == 0:
            continue
        base = f"{API}/repos/{login}/{repo['name']}"
        commits = expand_commits(repo)
        out.append(Route(f"{base}/languages", json=repo.get("languages", {})))
        pages = [commits[i : i + 100] for i in range(0, len(commits), 100)] or [[]]
        for n, page in enumerate(pages, start=1):
            params = {"author": login, "per_page": "100"} | ({"page": str(n)} if n > 1 else {})
            headers = (
                {"Link": f'<{base}/commits?author={login}&per_page=100&page={n + 1}>; rel="next"'}
                if n < len(pages)
                else {}
            )
            out.append(
                Route(
                    f"{base}/commits",
                    params,
                    [_commit_json(c, login) for c in page],
                    headers=headers,
                )
            )
        total = repo.get("total_commits", len(commits))
        out.append(
            Route(
                f"{base}/commits",
                {"per_page": "1"},
                [_commit_json(commits[0], login)] if commits else [],
                headers={"Link": f'<{base}/commits?per_page=1&page={total}>; rel="last"'}
                if total > 1
                else {},
            )
        )
        for c in commits:
            out.append(
                Route(
                    f"{base}/commits/{c['sha']}",
                    json={
                        "sha": c["sha"],
                        "stats": {"additions": c["additions"], "deletions": c["deletions"]},
                    },
                )
            )
        out.append(
            Route(
                f"{base}/git/trees/{repo.get('default_branch', 'main')}",
                {"recursive": "1"},
                {
                    "tree": [{"path": p, "type": "blob"} for p in repo.get("tree", [])],
                    "truncated": False,
                },
            )
        )
        for path, text in repo.get("files", {}).items():
            out.append(
                Route(
                    f"{base}/contents/{path}",
                    json={
                        "encoding": "base64",
                        "content": base64.b64encode(text.encode()).decode(),
                    },
                )
            )
        if repo.get("readme_size"):
            out.append(Route(f"{base}/readme", json={"size": repo["readme_size"]}))
        else:
            out.append(Route(f"{base}/readme", json={"message": "Not Found"}, status=404))
    return out


class ReplaySession(requests.Session):
    """A requests.Session that answers GitHub API calls from persona routes."""

    def __init__(self, personas: list[dict]):
        super().__init__()
        self.table = {}
        for persona in personas:
            for route in routes(persona):
                self.table[(route.url, frozenset(route.params.items()))] = route

    def get(self, url, **kwargs):
        parts = urlsplit(url)
        key = (f"{parts.scheme}://{parts.netloc}{parts.path}", frozenset(parse_qsl(parts.query)))
        route = self.table.get(key) or Route(url, json={"message": "Not Found"}, status=404)
        response = requests.Response()
        response.status_code = route.status
        response.url = url
        response._content = json.dumps(route.json).encode()
        response.headers.update({"Content-Type": "application/json", **route.headers})
        return response
