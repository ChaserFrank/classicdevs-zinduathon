import pytest
import responses

from apps.analysis.models import GithubCache
from apps.analysis.services import github as gh
from tests.fixtures.github.fake import API, load_persona, register_persona

pytestmark = pytest.mark.django_db


@responses.activate
def test_sends_version_header_and_token():
    responses.get(f"{API}/users/ann", json={"login": "Ann", "name": None})
    gh.GithubClient("tok").profile("ann")
    sent = responses.calls[0].request.headers
    assert sent["X-GitHub-Api-Version"] == "2022-11-28"
    assert sent["Authorization"] == "Bearer tok"


@responses.activate
def test_no_token_means_no_auth_header():
    responses.get(f"{API}/users/ann", json={"login": "ann"})
    gh.GithubClient("").profile("ann")
    assert "Authorization" not in responses.calls[0].request.headers


@responses.activate
def test_unknown_user():
    responses.get(f"{API}/users/ghost", status=404, json={"message": "Not Found"})
    with pytest.raises(gh.UserNotFound):
        gh.GithubClient().profile("ghost")


@responses.activate
def test_rate_limited_reads_reset_header():
    responses.get(
        f"{API}/users/ann",
        status=403,
        json={"message": "API rate limit exceeded"},
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1794050000"},
    )
    with pytest.raises(gh.GitHubRateLimited) as info:
        gh.GithubClient().profile("ann")
    assert info.value.code == "github_rate_limited"
    assert info.value.reset_at.year == 2026


@responses.activate
def test_secondary_rate_limit_without_headers():
    responses.get(f"{API}/users/ann", status=429, body="You have exceeded a secondary rate limit")
    with pytest.raises(gh.GitHubRateLimited):
        gh.GithubClient().profile("ann")


@responses.activate
def test_server_error_and_network_error():
    responses.get(f"{API}/users/a", status=502)
    responses.get(f"{API}/users/b", body=__import__("requests").ConnectionError("down"))
    with pytest.raises(gh.GithubUnavailable):
        gh.GithubClient().profile("a")
    with pytest.raises(gh.GithubUnavailable):
        gh.GithubClient().profile("b")


@responses.activate
def test_etag_cache_round_trip():
    url = f"{API}/users/ann"
    responses.get(url, json={"login": "ann", "name": "Ann"}, headers={"ETag": '"v1"'})
    responses.get(url, status=304)
    client = gh.GithubClient(cache=gh.DbCache())

    assert client.profile("ann").name == "Ann"
    assert GithubCache.objects.get(url=url).etag == '"v1"'
    assert client.profile("ann").name == "Ann"  # served from cache on 304
    assert responses.calls[1].request.headers["If-None-Match"] == '"v1"'


@responses.activate
def test_expired_cache_is_ignored():
    from datetime import UTC, datetime, timedelta

    url = f"{API}/users/ann"
    GithubCache.objects.create(
        url=url,
        etag='"old"',
        payload={"data": {"login": "old"}, "link": ""},
        fetched_at=datetime.now(UTC) - timedelta(hours=25),
    )
    responses.get(url, json={"login": "ann"})
    assert gh.GithubClient(cache=gh.DbCache()).profile("ann").login == "ann"
    assert "If-None-Match" not in responses.calls[0].request.headers


@responses.activate
def test_commit_count_from_link_header_and_empty_repo():
    responses.get(
        f"{API}/repos/a/b/commits",
        json=[{"sha": "x"}],
        headers={
            "Link": f'<{API}/repos/a/b/commits?per_page=1&page=2>; rel="next", <{API}/repos/a/b/commits?per_page=1&page=873>; rel="last"'
        },
    )
    responses.get(
        f"{API}/repos/a/empty/commits", status=409, json={"message": "Git Repository is empty."}
    )
    client = gh.GithubClient()
    assert client.commit_count("a/b") == 873
    assert client.commit_count("a/empty") == 0


@responses.activate
def test_user_commits_follow_pagination_up_to_three_pages():
    persona = {
        "login": "busy",
        "repos": [
            {
                "name": "big",
                "commit_series": [
                    {
                        "start": "2025-01-01T00:00:00+00:00",
                        "count": 350,
                        "every_days": 1,
                        "additions": 1,
                        "deletions": 0,
                    }
                ],
            }
        ],
    }
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        register_persona(rsps, persona)
        commits = gh.GithubClient().user_commits("busy/big", "busy")
    assert len(commits) == 300


def test_manifest_paths_depth_and_skips():
    tree = [
        "package.json",
        "web/package.json",
        "a/b/package.json",
        "node_modules/package.json",
        "requirements.txt",
        "x.py",
    ]
    assert gh.manifest_paths(tree) == ["package.json", "requirements.txt", "web/package.json"]


def test_sample_is_deterministic():
    from tests.analysis.builders import commits

    pool = commits(50)
    first = gh.sample_commits(pool, "dev/app", 20)
    assert first == gh.sample_commits(pool, "dev/app", 20)
    assert len(first) == 20
    assert gh.sample_commits(pool[:5], "dev/app", 20) == pool[:5]


@responses.activate
def test_fetch_profile_skips_forks_and_empty_repos():
    register_persona(responses, load_persona("amina-demo"))
    profile, repos = gh.fetch_profile(gh.GithubClient(), "amina-demo", workers=1)
    assert profile.name == "Amina Odhiambo"
    assert [r.name for r in repos] == ["shop-app", "duka-api", "matatu-routes"]
    shop = repos[0]
    assert shop.user_commit_count == 44 and shop.total_commits == 48
    assert len(shop.sampled_commits) == 20
    assert "package.json" in shop.manifests and shop.readme_size == 1800


@responses.activate
def test_fetch_profile_in_parallel_without_db_cache():
    register_persona(responses, load_persona("brian-demo"))
    _, repos = gh.fetch_profile(gh.GithubClient(), "brian-demo", workers=3)
    assert sorted(r.name for r in repos) == ["titanic-analysis", "todo-app", "weather-app"]


@responses.activate
def test_only_forks_means_no_public_repos():
    register_persona(responses, load_persona("forks-only"))
    with pytest.raises(gh.NoPublicRepos):
        gh.fetch_profile(gh.GithubClient(), "forks-only", workers=1)


@responses.activate
def test_missing_readme_tree_and_details_do_not_fail():
    responses.get(f"{API}/repos/a/b/readme", status=404)
    responses.get(f"{API}/repos/a/b/git/trees/main", status=500)
    responses.get(f"{API}/repos/a/b/contents/x", json={"encoding": "none"})
    client = gh.GithubClient()
    assert client.readme_size("a/b") == 0
    assert client.tree("a/b", "main") == []
    assert client.file_text("a/b", "x") == ""
