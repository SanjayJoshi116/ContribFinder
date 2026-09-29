import logging
import time

import httpx
import pytest
import respx
from django.test import override_settings

from services.github.client import GitHubClient
from services.github.errors import (
    GitHubAuthError,
    GitHubClientError,
    GitHubForbidden,
    GitHubNotFound,
    GitHubRateLimited,
    GitHubTransientError,
)

API = "https://api.github.com"
TOKEN = "gho_ClientTestToken000000000000000000000"


def repo_json(n: int, **extra: object) -> dict[str, object]:
    return {
        "id": n,
        "name": f"r{n}",
        "full_name": f"octocat/r{n}",
        "owner": {"login": "octocat"},
        "html_url": f"https://github.com/octocat/r{n}",
        "stargazers_count": n,
        "fork": False,
        "archived": False,
        "topics": ["django"],
        "license": {"spdx_id": "MIT"},
        "pushed_at": "2026-09-01T10:00:00Z",
        **extra,
    }


@pytest.fixture
def client():
    with GitHubClient(TOKEN, cache_scope="t1") as c:
        yield c


@respx.mock
def test_authenticated_user_normalized(client) -> None:
    respx.get(f"{API}/user").respond(
        200,
        json={
            "id": 7,
            "login": "octocat",
            "name": None,
            "bio": "Builds tools",
            "followers": 3,
            "public_repos": 12,
            "created_at": "2011-01-25T18:44:36Z",
        },
    )
    user = client.get_authenticated_user()
    assert (user.github_id, user.login, user.name, user.bio) == (7, "octocat", "", "Builds tools")
    assert user.public_repos == 12
    assert user.created_at is not None and user.created_at.year == 2011
    request = respx.calls.last.request
    assert request.headers["Authorization"] == f"Bearer {TOKEN}"
    assert request.headers["X-GitHub-Api-Version"] == "2022-11-28"


@respx.mock
def test_pagination_follows_link_headers(client) -> None:
    base = f"{API}/users/octocat/repos"
    respx.get(base, params={"page": "2"}).respond(
        200,
        json=[repo_json(3)],
        headers={"Link": f'<{base}?page=3>; rel="next"'},
    )
    respx.get(base, params={"page": "3"}).respond(200, json=[repo_json(4)])
    respx.get(base).respond(
        200,
        json=[repo_json(1), repo_json(2)],
        headers={"Link": f'<{base}?page=2>; rel="next", <{base}?page=3>; rel="last"'},
    )
    repos, truncated = client.list_owned_repositories("octocat")
    assert [r.github_id for r in repos] == [1, 2, 3, 4]
    assert truncated is False
    assert repos[0].topics == ("django",)
    assert repos[0].license_spdx == "MIT"
    first = respx.calls[0].request.url.params
    assert (first["type"], first["sort"], first["per_page"]) == ("owner", "pushed", "100")


@respx.mock
@override_settings(GITHUB_MAX_PAGES=2)
def test_pagination_cap_reports_truncation(client) -> None:
    base = f"{API}/users/octocat/repos"
    for page in (2, 3):
        respx.get(base, params={"page": str(page)}).respond(
            200, json=[repo_json(page)], headers={"Link": f'<{base}?page={page + 1}>; rel="next"'}
        )
    respx.get(base).respond(
        200, json=[repo_json(1)], headers={"Link": f'<{base}?page=2>; rel="next"'}
    )
    repos, truncated = client.list_owned_repositories("octocat")
    assert [r.github_id for r in repos] == [1, 2]
    assert truncated is True
    assert len(respx.calls) == 2


@respx.mock
def test_pagination_refuses_foreign_host(client) -> None:
    respx.get(f"{API}/users/octocat/repos").respond(
        200, json=[repo_json(1)], headers={"Link": '<https://evil.example/steal>; rel="next"'}
    )
    with pytest.raises(GitHubClientError):
        client.list_owned_repositories("octocat")
    assert len(respx.calls) == 1


@respx.mock
def test_conditional_request_reuses_cached_body(client) -> None:
    route = respx.get(f"{API}/repos/octocat/r1/languages")
    route.side_effect = [
        httpx.Response(200, json={"Python": 7000}, headers={"ETag": '"abc"'}),
        httpx.Response(304),
    ]
    assert client.get_languages("octocat/r1") == {"Python": 7000}
    assert client.get_languages("octocat/r1") == {"Python": 7000}
    assert route.calls[1].request.headers["If-None-Match"] == '"abc"'


@respx.mock
def test_etag_cache_is_scoped_per_user() -> None:
    route = respx.get(f"{API}/repos/octocat/r1/languages")
    route.side_effect = [
        httpx.Response(200, json={"Python": 1}, headers={"ETag": '"a"'}),
        httpx.Response(200, json={"Python": 1}, headers={"ETag": '"a"'}),
    ]
    with GitHubClient(TOKEN, cache_scope="u1") as a, GitHubClient(TOKEN, cache_scope="u2") as b:
        a.get_languages("octocat/r1")
        b.get_languages("octocat/r1")
    assert "If-None-Match" not in route.calls[1].request.headers


@respx.mock
def test_readme_raw_and_missing(client) -> None:
    respx.get(f"{API}/repos/octocat/octocat/readme").respond(200, text="## Skills\nPython")
    assert client.get_profile_readme("octocat") == "## Skills\nPython"
    assert "raw" in respx.calls.last.request.headers["Accept"]

    respx.get(f"{API}/repos/ghost/ghost/readme").respond(404, json={"message": "Not Found"})
    assert client.get_profile_readme("ghost") is None


@respx.mock
def test_401_is_auth_error(client) -> None:
    respx.get(f"{API}/user").respond(401, json={"message": "Bad credentials"})
    with pytest.raises(GitHubAuthError):
        client.get_authenticated_user()


@respx.mock
@pytest.mark.parametrize("status", [403, 429])
def test_retry_after_header(client, status: int) -> None:
    respx.get(f"{API}/user").respond(status, headers={"Retry-After": "60"})
    with pytest.raises(GitHubRateLimited) as exc:
        client.get_authenticated_user()
    assert exc.value.retry_after == 60


@respx.mock
def test_primary_limit_exhausted_uses_reset(client) -> None:
    reset = int(time.time()) + 600
    respx.get(f"{API}/user").respond(
        403, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset)}
    )
    with pytest.raises(GitHubRateLimited) as exc:
        client.get_authenticated_user()
    assert 590 <= exc.value.retry_after <= 600


@respx.mock
def test_secondary_429_without_headers_waits_a_minute(client) -> None:
    respx.get(f"{API}/user").respond(429)
    with pytest.raises(GitHubRateLimited) as exc:
        client.get_authenticated_user()
    assert exc.value.retry_after == 60


@respx.mock
def test_plain_403_is_forbidden(client) -> None:
    respx.get(f"{API}/user").respond(403, headers={"X-RateLimit-Remaining": "4000"})
    with pytest.raises(GitHubForbidden):
        client.get_authenticated_user()


@respx.mock
def test_404_not_found(client) -> None:
    respx.get(f"{API}/repos/octocat/gone/languages").respond(404)
    with pytest.raises(GitHubNotFound):
        client.get_languages("octocat/gone")


@respx.mock
@pytest.mark.parametrize(
    "outcome",
    [httpx.Response(502), httpx.Response(503), httpx.ConnectTimeout("t"), httpx.ReadError("r")],
    ids=["502", "503", "timeout", "read-error"],
)
def test_transient_failures(client, outcome) -> None:
    route = respx.get(f"{API}/user")
    if isinstance(outcome, httpx.Response):
        route.mock(return_value=outcome)
    else:
        route.mock(side_effect=outcome)
    with pytest.raises(GitHubTransientError):
        client.get_authenticated_user()


@respx.mock
def test_rate_limit_headers_recorded(client) -> None:
    from django.core.cache import cache

    respx.get(f"{API}/user").respond(
        200,
        json={"id": 1, "login": "o"},
        headers={"X-RateLimit-Remaining": "4999", "X-RateLimit-Limit": "5000"},
    )
    client.get_authenticated_user()
    assert cache.get("github:ratelimit:t1")["remaining"] == "4999"


@respx.mock
def test_errors_and_logs_never_contain_token(client, caplog: pytest.LogCaptureFixture) -> None:
    respx.get(f"{API}/user").respond(401)
    respx.get(f"{API}/repos/o/r/languages").mock(side_effect=httpx.ConnectTimeout("t"))
    messages = []
    with caplog.at_level(logging.DEBUG):
        for call in (client.get_authenticated_user, lambda: client.get_languages("o/r")):
            with pytest.raises(Exception) as exc:
                call()
            messages.append(str(exc.value))
    assert all(TOKEN not in m for m in messages)
    assert TOKEN not in caplog.text
    assert TOKEN not in repr(client)


@pytest.mark.django_db
def test_for_user_requires_connected_account(user) -> None:
    from github.models import GitHubAccount

    GitHubAccount.objects.filter(user=user).delete()
    with pytest.raises(GitHubAuthError):
        GitHubClient.for_user(user)
