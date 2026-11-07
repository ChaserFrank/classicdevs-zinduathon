"""Serve GitHub API fixtures through `responses`.

Two formats:
- Persona files (`personas/*.json`): a compact description of an account (repos, languages,
  commit series, file tree, manifest contents). Expanded here into the exact JSON shapes GitHub
  returns, including Link headers for pagination and commit counts.
- Recordings (`recordings/*.json`, written by scripts/record_fixtures.py): raw responses keyed by
  URL, replayed as-is.
"""

import base64
import json
from datetime import datetime, timedelta
from pathlib import Path

import responses

API = "https://api.github.com"
HERE = Path(__file__).parent


def load_persona(name: str) -> dict:
    return json.loads((HERE / "personas" / f"{name}.json").read_text())


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


def register_persona(rsps: responses.RequestsMock, persona: dict) -> None:
    login = persona["login"]
    match = responses.matchers.query_param_matcher
    rsps.get(
        f"{API}/users/{login}",
        json={
            "login": login,
            "id": 1,
            "name": persona.get("name"),
            "avatar_url": f"https://avatars/{login}.png",
        },
    )
    repo_list = []
    for i, repo in enumerate(persona["repos"]):
        repo_list.append(
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
    rsps.get(
        f"{API}/users/{login}/repos",
        json=repo_list,
        match=[match({"type": "owner", "sort": "pushed", "per_page": "100"})],
    )
    for repo in persona["repos"]:
        if repo.get("fork") or repo.get("size", 100) == 0:
            continue
        full = f"{login}/{repo['name']}"
        base = f"{API}/repos/{full}"
        commits = expand_commits(repo)
        rsps.get(f"{base}/languages", json=repo.get("languages", {}))
        pages = [commits[i : i + 100] for i in range(0, len(commits), 100)] or [[]]
        for n, page in enumerate(pages, start=1):
            params = {"author": login, "per_page": "100"}
            headers = {}
            if n < len(pages):
                headers["Link"] = (
                    f'<{base}/commits?author={login}&per_page=100&page={n + 1}>; rel="next"'
                )
            if n > 1:
                params["page"] = str(n)
            rsps.get(
                f"{base}/commits",
                json=[_commit_json(c, login) for c in page],
                headers=headers,
                match=[match(params)],
            )
        total = repo.get("total_commits", len(commits))
        rsps.get(
            f"{base}/commits",
            json=[_commit_json(commits[0], login)] if commits else [],
            headers={"Link": f'<{base}/commits?per_page=1&page={total}>; rel="last"'}
            if total > 1
            else {},
            match=[match({"per_page": "1"})],
        )
        for c in commits:
            rsps.get(
                f"{base}/commits/{c['sha']}",
                json={
                    "sha": c["sha"],
                    "stats": {"additions": c["additions"], "deletions": c["deletions"]},
                },
            )
        tree = repo.get("tree", [])
        rsps.get(
            f"{base}/git/trees/{repo.get('default_branch', 'main')}",
            json={"tree": [{"path": p, "type": "blob"} for p in tree], "truncated": False},
        )
        for path, text in repo.get("files", {}).items():
            rsps.get(
                f"{base}/contents/{path}",
                json={"encoding": "base64", "content": base64.b64encode(text.encode()).decode()},
            )
        if repo.get("readme_size"):
            rsps.get(f"{base}/readme", json={"size": repo["readme_size"]})
        else:
            rsps.get(f"{base}/readme", status=404, json={"message": "Not Found"})


def register_recording(rsps: responses.RequestsMock, path: Path) -> None:
    for entry in json.loads(path.read_text())["responses"]:
        rsps.add(
            responses.GET,
            entry["url"],
            json=entry["body"],
            status=entry["status"],
            headers=entry.get("headers", {}),
            match=[responses.matchers.query_string_matcher(entry["url"].partition("?")[2])],
        )
