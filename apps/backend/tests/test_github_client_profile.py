"""GitHub client methods added for profile evidence (contents, search, events, repository)."""

import logging

import pytest
import respx
from django.test import override_settings

from services.github.client import ContentEntry, GitHubClient
from services.github.errors import GitHubRateLimited, GitHubValidationError

from .test_github_client import API, TOKEN, repo_json


@pytest.fixture
def client():
    with GitHubClient(TOKEN, cache_scope="t2") as c:
        yield c


def pr_item(repo: str, merged: str | None = "2026-08-01T10:00:00Z") -> dict[str, object]:
    return {
        "repository_url": f"{API}/repos/{repo}",
        "pull_request": {"merged_at": merged},
    }


@respx.mock
def test_root_contents(client) -> None:
    respx.get(f"{API}/repos/octocat/r1/contents/").respond(
        200,
        json=[
            {"name": "package.json", "type": "file", "size": 812},
            {"name": "src", "type": "dir", "size": 0},
        ],
    )
    assert client.list_root_contents("octocat/r1") == [
        ContentEntry("package.json", "file", 812),
        ContentEntry("src", "dir", 0),
    ]


@respx.mock
def test_root_contents_of_empty_repository(client) -> None:
    respx.get(f"{API}/repos/octocat/empty/contents/").respond(404)
    assert client.list_root_contents("octocat/empty") == []


@respx.mock
def test_get_file_raw(client) -> None:
    route = respx.get(f"{API}/repos/octocat/r1/contents/go.mod").respond(200, text="module x\n")
    assert client.get_file("octocat/r1", "go.mod") == "module x\n"
    assert route.calls.last.request.headers["Accept"] == "application/vnd.github.raw+json"


@respx.mock
def test_get_repository(client) -> None:
    respx.get(f"{API}/repos/pallets/flask").respond(
        200, json=repo_json(5, full_name="pallets/flask", owner={"login": "pallets"})
    )
    repo = client.get_repository("pallets/flask")
    assert (repo.full_name, repo.owner_login, repo.topics) == (
        "pallets/flask",
        "pallets",
        ("django",),
    )


@respx.mock
def test_search_merged_pull_requests_paginates(client) -> None:
    route = respx.get(f"{API}/search/issues")
    route.side_effect = [
        respx.MockResponse(
            200,
            json={"total_count": 3, "items": [pr_item("pallets/flask"), pr_item("psf/requests")]},
            headers={"Link": f'<{API}/search/issues?page=2>; rel="next"'},
        ),
        respx.MockResponse(200, json={"total_count": 3, "items": [pr_item("pallets/flask")]}),
    ]
    refs, truncated = client.search_merged_pull_requests("octocat")
    assert [r.repo_full_name for r in refs] == ["pallets/flask", "psf/requests", "pallets/flask"]
    assert truncated is False
    query = route.calls[0].request.url.params["q"]
    assert query == "type:pr author:octocat is:merged is:public -user:octocat"


@respx.mock
@override_settings(GITHUB_CONTRIB_MAX_PRS=100)
def test_search_is_capped(client) -> None:
    respx.get(f"{API}/search/issues").respond(
        200,
        json={"items": [pr_item(f"o/r{i}") for i in range(100)]},
        headers={"Link": f'<{API}/search/issues?page=2>; rel="next"'},
    )
    refs, truncated = client.search_merged_pull_requests("octocat")
    assert len(refs) == 100
    assert truncated is True
    assert len(respx.calls) == 1


@respx.mock
def test_search_422_is_a_validation_error(client) -> None:
    respx.get(f"{API}/search/issues").respond(422)
    with pytest.raises(GitHubValidationError):
        client.search_merged_pull_requests("ghost")


@respx.mock
def test_search_rate_limit(client) -> None:
    respx.get(f"{API}/search/issues").respond(
        403, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "9999999999"}
    )
    with pytest.raises(GitHubRateLimited):
        client.search_merged_pull_requests("octocat")


@respx.mock
def test_public_pushes_only_external(client) -> None:
    respx.get(f"{API}/users/octocat/events/public").respond(
        200,
        json=[
            {
                "type": "PushEvent",
                "repo": {"name": "psf/requests"},
                "created_at": "2026-08-02T10:00:00Z",
            },
            {"type": "PushEvent", "repo": {"name": "Octocat/own"}},
            {"type": "WatchEvent", "repo": {"name": "psf/black"}},
        ],
    )
    pushes = client.list_public_pushes("octocat")
    assert [p.repo_full_name for p in pushes] == ["psf/requests"]
    assert pushes[0].created_at is not None


@respx.mock
def test_events_stop_after_three_pages(client) -> None:
    route = respx.get(url__startswith=f"{API}/users/octocat/events/public").respond(
        200, json=[], headers={"Link": f'<{API}/users/octocat/events/public?page=9>; rel="next"'}
    )
    client.list_public_pushes("octocat")
    assert route.call_count == 3


@respx.mock
def test_no_token_in_errors_or_logs(client, caplog: pytest.LogCaptureFixture) -> None:
    respx.get(f"{API}/search/issues").respond(422)
    with caplog.at_level(logging.DEBUG), pytest.raises(GitHubValidationError) as exc:
        client.search_merged_pull_requests("octocat")
    assert TOKEN not in str(exc.value)
    assert TOKEN not in caplog.text
