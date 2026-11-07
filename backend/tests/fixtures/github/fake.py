"""Serve GitHub API fixtures through `responses`.

Personas: shared demo personas live in apps/analysis/demo_personas/ (also used by seed_demo);
test-only ones (e.g. forks-only) in tests/fixtures/github/personas/. Both expand through
apps.analysis.demo.routes into GitHub's exact response shapes.

Recordings (`recordings/*.json`, from scripts/record_fixtures.py) are replayed as-is.
"""

import json
from pathlib import Path

import responses

from apps.analysis import demo

API = demo.API
HERE = Path(__file__).parent


def load_persona(name: str) -> dict:
    local = HERE / "personas" / f"{name}.json"
    return json.loads(local.read_text()) if local.exists() else demo.load_persona(name)


def register_persona(rsps: responses.RequestsMock, persona: dict) -> None:
    for route in demo.routes(persona):
        rsps.add(
            responses.GET,
            route.url,
            json=route.json,
            status=route.status,
            headers=route.headers,
            match=[responses.matchers.query_param_matcher(route.params)],
        )


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
