"""Record real GitHub API responses for pipeline tests.

    GITHUB_TOKEN=... python scripts/record_fixtures.py octocat another-login

Runs the same fetch the pipeline does (with a recording session) and writes
tests/fixtures/github/recordings/<login>.json. Tests replay it with
tests.fixtures.github.fake.register_recording. Only public data is requested; the token is never
written to the file.
"""

import json
import os
import sys
from pathlib import Path

import django
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from apps.analysis.services.github import GithubClient, GithubError, fetch_profile  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "tests/fixtures/github/recordings"
KEEP_HEADERS = ("Link", "ETag", "X-RateLimit-Remaining")


class RecordingSession(requests.Session):
    def __init__(self):
        super().__init__()
        self.recorded = []

    def get(self, url, **kwargs):
        response = super().get(url, **kwargs)
        try:
            body = response.json()
        except ValueError:
            body = None
        self.recorded.append(
            {
                "url": url,
                "status": response.status_code,
                "headers": {k: v for k, v in response.headers.items() if k in KEEP_HEADERS},
                "body": body,
            }
        )
        return response


def record(login: str) -> Path:
    session = RecordingSession()
    client = GithubClient(os.environ.get("GITHUB_TOKEN", ""), session=session)
    try:
        fetch_profile(client, login, workers=1)
    except GithubError as exc:
        print(f"{login}: {exc.code} (recorded anyway)")
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{login.lower()}.json"
    path.write_text(json.dumps({"login": login, "responses": session.recorded}, indent=1))
    print(f"{login}: {len(session.recorded)} responses → {path}")
    return path


if __name__ == "__main__":
    if not os.environ.get("GITHUB_TOKEN"):
        sys.exit("Set GITHUB_TOKEN (60 requests/hour without one is not enough).")
    for name in sys.argv[1:]:
        record(name)
