"""GitHubClient.list_open_issues (Phase 7), against recorded fixtures."""

import httpx
import pytest
import respx
from django.test import override_settings

from services.github.client import GitHubClient
from services.github.errors import GitHubNotFound, GitHubRateLimited, GitHubTransientError

from .repo_fixtures import issue_payload
from .test_github_client import API, TOKEN

ISSUES = f"{API}/repos/encode/httpx/issues"


@pytest.fixture
def client():
    with GitHubClient(TOKEN, cache_scope="t7") as c:
        yield c


def pull_request(number: int) -> dict[str, object]:
    return issue_payload(number, pull_request={"url": f"{API}/repos/encode/httpx/pulls/{number}"})


@respx.mock
def test_open_issues_normalized(client) -> None:
    route = respx.get(ISSUES).respond(
        200,
        json=[
            issue_payload(
                3,
                title="Support HTTP/3",
                body="Details",
                labels=[{"name": "Type: Enhancement"}, {"name": "good first issue"}],
                assignees=[{"login": "x"}],
                locked=True,
                comments=7,
            ),
            issue_payload(2, body=None),
        ],
    )
    page = client.list_open_issues("encode/httpx")
    assert page.truncated is False
    first, second = page.issues
    assert (first.github_id, first.number, first.title) == (70_003, 3, "Support HTTP/3")
    assert first.labels == ("Type: Enhancement", "good first issue")
    assert first.has_assignee and first.is_locked and first.comments == 7
    assert first.html_url == "https://github.com/o/r/issues/3"
    assert first.updated_at is not None and first.created_at is not None
    assert second.body == "" and second.has_assignee is False and second.labels == ()
    params = route.calls.last.request.url.params
    assert (params["state"], params["sort"], params["direction"]) == ("open", "updated", "desc")
    assert params["per_page"] == "100"


@respx.mock
def test_pull_requests_are_dropped(client) -> None:
    respx.get(ISSUES).respond(200, json=[issue_payload(1), pull_request(2), issue_payload(3)])
    assert [i.number for i in client.list_open_issues("encode/httpx").issues] == [1, 3]


@respx.mock
@override_settings(ISSUES_MAX_PAGES=1)
def test_page_cap_reports_truncation(client) -> None:
    respx.get(ISSUES, params={"page": "2"}).respond(200, json=[issue_payload(2)])
    respx.get(ISSUES).respond(
        200, json=[issue_payload(1)], headers={"Link": f'<{ISSUES}?page=2>; rel="next"'}
    )
    page = client.list_open_issues("encode/httpx")
    assert [i.number for i in page.issues] == [1]
    assert page.truncated is True
    assert len(respx.calls) == 1


@respx.mock
@override_settings(ISSUES_MAX_PAGES=2)
def test_more_pages_when_configured(client) -> None:
    respx.get(ISSUES, params={"page": "2"}).respond(200, json=[issue_payload(2)])
    respx.get(ISSUES).respond(
        200, json=[issue_payload(1)], headers={"Link": f'<{ISSUES}?page=2>; rel="next"'}
    )
    page = client.list_open_issues("encode/httpx")
    assert [i.number for i in page.issues] == [1, 2]
    assert page.truncated is False


@respx.mock
def test_not_modified_replays_cached_page(client) -> None:
    route = respx.get(ISSUES)
    route.side_effect = [
        httpx.Response(200, json=[issue_payload(1)], headers={"ETag": '"v1"'}),
        httpx.Response(304),
    ]
    assert [i.number for i in client.list_open_issues("encode/httpx").issues] == [1]
    assert [i.number for i in client.list_open_issues("encode/httpx").issues] == [1]
    assert route.calls[1].request.headers["If-None-Match"] == '"v1"'


@respx.mock
def test_issues_disabled_is_empty(client) -> None:
    respx.get(ISSUES).respond(410, json={"message": "Issues are disabled for this repo"})
    page = client.list_open_issues("encode/httpx")
    assert page.issues == [] and page.truncated is False


@respx.mock
def test_missing_repository_raises(client) -> None:
    respx.get(ISSUES).respond(404, json={"message": "Not Found"})
    with pytest.raises(GitHubNotFound):
        client.list_open_issues("encode/httpx")


@respx.mock
@pytest.mark.parametrize("status", [403, 429])
def test_rate_limits(client, status: int) -> None:
    respx.get(ISSUES).respond(status, headers={"Retry-After": "42"})
    with pytest.raises(GitHubRateLimited) as exc:
        client.list_open_issues("encode/httpx")
    assert exc.value.retry_after == 42


@respx.mock
def test_server_error_is_transient(client) -> None:
    respx.get(ISSUES).respond(502)
    with pytest.raises(GitHubTransientError):
        client.list_open_issues("encode/httpx")
