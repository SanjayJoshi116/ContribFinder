"""GitHubClient methods for candidate repositories (Phase 4), against recorded fixtures."""

import base64
import logging
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx
from django.test import override_settings

from services.github.client import PUBLIC_SCOPE, GitHubClient
from services.github.errors import (
    GitHubAuthError,
    GitHubRateLimited,
    GitHubUnavailableForLegalReasons,
    GitHubValidationError,
)

from .test_github_client import API, TOKEN, repo_json

NOW = datetime(2026, 9, 29, 15, 30, tzinfo=UTC)
SINCE = NOW - timedelta(days=90)


@pytest.fixture
def client():
    with GitHubClient(TOKEN, cache_scope="t3") as c:
        yield c


def link(path: str, **rels: int) -> str:
    return ", ".join(f'<{API}{path}&page={page}>; rel="{rel}"' for rel, page in rels.items())


@respx.mock
def test_search_repositories(client) -> None:
    route = respx.get(f"{API}/search/repositories").respond(
        200, json={"total_count": 3, "items": [repo_json(1), repo_json(2), repo_json(3)]}
    )
    repos = client.search_repositories("language:Python stars:>=20", limit=2)
    assert [r.full_name for r in repos] == ["octocat/r1", "octocat/r2"]
    assert repos[0].topics == ("django",)
    assert repos[0].license_spdx == "MIT"
    params = route.calls.last.request.url.params
    assert params["q"] == "language:Python stars:>=20"
    assert params["per_page"] == "2"


@respx.mock
def test_search_repositories_422(client) -> None:
    respx.get(f"{API}/search/repositories").respond(422, json={"message": "Validation Failed"})
    with pytest.raises(GitHubValidationError):
        client.search_repositories("topic:", limit=30)


@respx.mock
def test_search_repositories_secondary_limit(client) -> None:
    respx.get(f"{API}/search/repositories").respond(
        403, headers={"Retry-After": "30"}, json={"message": "secondary rate limit"}
    )
    with pytest.raises(GitHubRateLimited) as exc:
        client.search_repositories("language:Go", limit=30)
    assert exc.value.retry_after == 30


@respx.mock
def test_community_profile(client) -> None:
    respx.get(f"{API}/repos/o/r/community/profile").respond(
        200,
        json={
            "health_percentage": 71,
            "files": {
                "contributing": {"url": "x"},
                "code_of_conduct_file": {"url": "y"},
                "code_of_conduct": None,
                "issue_template": None,
                "pull_request_template": {"url": "z"},
                "readme": {"url": "r"},
            },
        },
    )
    profile = client.get_community_profile("o/r")
    assert profile.has_contributing
    assert profile.has_code_of_conduct
    assert not profile.has_issue_template
    assert profile.has_pull_request_template


@respx.mock
def test_community_profile_missing_is_absent(client) -> None:
    respx.get(f"{API}/repos/o/r/community/profile").respond(404, json={"message": "Not Found"})
    profile = client.get_community_profile("o/r")
    assert not any(vars(profile).values())


@respx.mock
def test_label_names(client) -> None:
    respx.get(f"{API}/repos/o/r/labels").respond(
        200, json=[{"name": "Good First Issue"}, {"name": "help-wanted"}]
    )
    assert client.list_label_names("o/r") == ["Good First Issue", "help-wanted"]


@respx.mock
def test_readme_present_and_missing(client) -> None:
    respx.get(f"{API}/repos/o/r/readme").respond(200, text="# Project")
    assert client.get_readme("o/r") == "# Project"
    assert "raw" in respx.calls.last.request.headers["Accept"]
    respx.get(f"{API}/repos/o/none/readme").respond(404, json={"message": "Not Found"})
    assert client.get_readme("o/none") is None


@respx.mock
def test_commit_count_from_last_link(client) -> None:
    route = respx.get(f"{API}/repos/o/r/commits").respond(
        200,
        json=[{"sha": "a"}],
        headers={"Link": link("/repositories/1/commits?per_page=1", next=2, last=42)},
    )
    assert client.count_commits_since("o/r", SINCE) == 42
    params = route.calls.last.request.url.params
    assert params["since"] == "2026-07-01T00:00:00Z"  # truncated to the day
    assert params["per_page"] == "1"


@respx.mock
def test_commit_count_single_page_and_empty_repository(client) -> None:
    respx.get(f"{API}/repos/o/one/commits").respond(200, json=[{"sha": "a"}])
    respx.get(f"{API}/repos/o/none/commits").respond(200, json=[])
    respx.get(f"{API}/repos/o/empty/commits").respond(
        409, json={"message": "Git Repository is empty."}
    )
    assert client.count_commits_since("o/one", SINCE) == 1
    assert client.count_commits_since("o/none", SINCE) == 0
    assert client.count_commits_since("o/empty", SINCE) == 0


@respx.mock
def test_contributors(client) -> None:
    respx.get(f"{API}/repos/o/r/contributors").respond(
        200,
        json=[{"login": "a"}],
        headers={"Link": link("/repositories/1/contributors?per_page=1&anon=1", next=2, last=57)},
    )
    respx.get(f"{API}/repos/o/huge/contributors").respond(
        403, json={"message": "The history or contributor list is too large"}
    )
    respx.get(f"{API}/repos/o/empty/contributors").respond(204)
    assert client.count_contributors("o/r") == 57
    assert client.count_contributors("o/huge") is None
    assert client.count_contributors("o/empty") == 0


def pr(created_days: int, merged_days: int | None, updated_days: int) -> dict[str, object]:
    def ts(days: int) -> str:
        return (NOW - timedelta(days=days)).isoformat()

    return {
        "created_at": ts(created_days),
        "merged_at": ts(merged_days) if merged_days is not None else None,
        "updated_at": ts(updated_days),
    }


@respx.mock
def test_recent_pull_requests(client) -> None:
    route = respx.get(f"{API}/repos/o/r/pulls").respond(
        200, json=[pr(5, 2, 1), pr(10, None, 3), pr(200, 30, 30), pr(300, 250, 200)]
    )
    sample = client.recent_pull_requests("o/r", SINCE)
    assert (sample.opened, sample.merged, sample.capped) == (2, 2, False)
    params = route.calls.last.request.url.params
    assert (params["state"], params["sort"], params["direction"]) == ("all", "updated", "desc")


@respx.mock
def test_recent_pull_requests_capped(client) -> None:
    respx.get(f"{API}/repos/o/r/pulls").respond(200, json=[pr(5, 1, 1)] * 100)
    sample = client.recent_pull_requests("o/r", SINCE)
    assert sample.capped
    assert sample.merged == 100


@respx.mock
def test_latest_release(client) -> None:
    respx.get(f"{API}/repos/o/r/releases/latest").respond(
        200, json={"published_at": "2026-09-09T00:00:00Z"}
    )
    respx.get(f"{API}/repos/o/none/releases/latest").respond(404, json={"message": "Not Found"})
    assert client.get_latest_release_date("o/r") == datetime(2026, 9, 9, tzinfo=UTC)
    assert client.get_latest_release_date("o/none") is None


@respx.mock
def test_451_is_its_own_error(client) -> None:
    respx.get(f"{API}/repos/o/dmca").respond(451, json={"message": "Repository access blocked"})
    with pytest.raises(GitHubUnavailableForLegalReasons):
        client.get_repository("o/dmca")


@respx.mock
@override_settings(GITHUB_CLIENT_ID="Iv1.clientid", GITHUB_CLIENT_SECRET="s3cr3t-client-secret")
def test_app_client_uses_basic_auth_and_never_logs_secret(
    caplog: pytest.LogCaptureFixture,
) -> None:
    respx.get(f"{API}/repos/o/r/readme").respond(500)
    with caplog.at_level(logging.DEBUG), GitHubClient.for_app() as app:
        assert "s3cr3t" not in repr(app)
        with pytest.raises(Exception) as exc:
            app.get_readme("o/r")
    header = respx.calls.last.request.headers["Authorization"]
    expected = base64.b64encode(b"Iv1.clientid:s3cr3t-client-secret").decode()
    assert header == f"Basic {expected}"
    assert "s3cr3t" not in str(exc.value)
    assert expected not in caplog.text
    assert "s3cr3t" not in caplog.text


@override_settings(GITHUB_CLIENT_ID="", GITHUB_CLIENT_SECRET="")
def test_app_client_requires_credentials() -> None:
    with pytest.raises(GitHubAuthError):
        GitHubClient.for_app()


@respx.mock
def test_public_scope_shares_etags_between_users() -> None:
    route = respx.get(f"{API}/repos/o/r/languages")
    route.side_effect = [
        httpx.Response(200, json={"Go": 1}, headers={"ETag": '"v1"'}),
        httpx.Response(304),
    ]
    with (
        GitHubClient(TOKEN, cache_scope=PUBLIC_SCOPE) as a,
        GitHubClient("gho_OtherUserToken0000000000000000000", cache_scope=PUBLIC_SCOPE) as b,
    ):
        assert a.get_languages("o/r") == {"Go": 1}
        assert b.get_languages("o/r") == {"Go": 1}
    assert route.calls[1].request.headers["If-None-Match"] == '"v1"'


def test_redaction_masks_authorization_values() -> None:
    from core.logging import redact

    assert "abc123def456" not in redact("Authorization: Bearer abc123def456ghi")
    assert "QmFzaWNzZWNyZXQ=" not in redact("Basic QmFzaWNzZWNyZXQ=")
