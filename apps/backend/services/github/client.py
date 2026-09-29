"""GitHub REST client used by the sync layer (design D3).

The only place that decrypts a user's token (``GitHubClient.for_user``). It handles
pagination, ETag conditional requests (cached in the Django cache), rate-limit detection and
error mapping, and returns normalized dataclasses instead of raw GitHub JSON.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from django.conf import settings
from django.core.cache import cache

from accounts.models import User
from github.models import GitHubAccount
from services.crypto import decrypt_token

from .errors import (
    GitHubAuthError,
    GitHubClientError,
    GitHubConflict,
    GitHubForbidden,
    GitHubNotFound,
    GitHubRateLimited,
    GitHubTransientError,
    GitHubUnavailableForLegalReasons,
    GitHubValidationError,
)

logger = logging.getLogger(__name__)

API_VERSION = "2022-11-28"
JSON = "application/vnd.github+json"
RAW = "application/vnd.github.raw+json"
PER_PAGE = 100
# GitHub serves at most 3 pages (300 events, ~90 days) of a user's public events.
EVENTS_MAX_PAGES = 3
LABELS_MAX_PAGES = 3
# GitHub asks clients to wait at least a minute on a secondary limit without Retry-After.
SECONDARY_LIMIT_DEFAULT_WAIT = 60
# ETag cache scope for public repository data, shared by every client (Phase 4).
PUBLIC_SCOPE = "public"


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


@dataclass(frozen=True)
class GitHubUser:
    github_id: int
    login: str
    name: str
    bio: str
    company: str
    location: str
    blog: str
    avatar_url: str
    followers: int
    following: int
    public_repos: int
    created_at: datetime | None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> GitHubUser:
        return cls(
            github_id=int(data["id"]),
            login=str(data["login"]),
            name=data.get("name") or "",
            bio=data.get("bio") or "",
            company=data.get("company") or "",
            location=data.get("location") or "",
            blog=data.get("blog") or "",
            avatar_url=data.get("avatar_url") or "",
            followers=int(data.get("followers") or 0),
            following=int(data.get("following") or 0),
            public_repos=int(data.get("public_repos") or 0),
            created_at=_dt(data.get("created_at")),
        )


@dataclass(frozen=True)
class GitHubRepo:
    github_id: int
    owner_login: str
    name: str
    full_name: str
    description: str
    html_url: str
    default_branch: str
    stars: int
    forks: int
    open_issues: int
    primary_language: str
    license_spdx: str
    is_fork: bool
    is_archived: bool
    created_at: datetime | None
    updated_at: datetime | None
    pushed_at: datetime | None
    topics: tuple[str, ...]

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> GitHubRepo:
        license_info = data.get("license") or {}
        return cls(
            github_id=int(data["id"]),
            owner_login=str(data["owner"]["login"]),
            name=str(data["name"]),
            full_name=str(data["full_name"]),
            description=data.get("description") or "",
            html_url=str(data["html_url"]),
            default_branch=data.get("default_branch") or "",
            stars=int(data.get("stargazers_count") or 0),
            forks=int(data.get("forks_count") or 0),
            open_issues=int(data.get("open_issues_count") or 0),
            primary_language=data.get("language") or "",
            license_spdx=license_info.get("spdx_id") or "",
            is_fork=bool(data.get("fork")),
            is_archived=bool(data.get("archived")),
            created_at=_dt(data.get("created_at")),
            updated_at=_dt(data.get("updated_at")),
            pushed_at=_dt(data.get("pushed_at")),
            topics=tuple(data.get("topics") or ()),
        )


@dataclass(frozen=True)
class ContentEntry:
    """An entry of a repository directory listing."""

    name: str
    type: str  # "file", "dir", "symlink" or "submodule"
    size: int


@dataclass(frozen=True)
class PullRequestRef:
    """A merged pull request the user authored in a repository they do not own."""

    repo_full_name: str
    merged_at: datetime | None


@dataclass(frozen=True)
class PushRef:
    """A public push by the user to a repository they do not own."""

    repo_full_name: str
    created_at: datetime | None


@dataclass(frozen=True)
class CommunityProfile:
    """Presence of community files (``/community/profile``)."""

    has_contributing: bool
    has_code_of_conduct: bool
    has_issue_template: bool
    has_pull_request_template: bool


@dataclass(frozen=True)
class PullSample:
    """Pull request counts over a window, from one page of recently updated PRs.
    ``capped`` is True when the page was full and older PRs in the window may be missing."""

    opened: int
    merged: int
    capped: bool


def _repo_from_api_url(url: str) -> str:
    """``https://api.github.com/repos/owner/name`` → ``owner/name``."""
    return "/".join(httpx.URL(url).path.split("/")[2:4])


@dataclass(frozen=True)
class Page:
    """Result of a paginated listing; ``truncated`` is True when the page cap stopped it."""

    items: list[dict[str, Any]]
    truncated: bool


@dataclass(frozen=True)
class _Response:
    status: int
    text: str
    link: str

    def json(self) -> Any:
        return json.loads(self.text)


class GitHubClient:
    def __init__(
        self, token: str | None = None, *, cache_scope: str, auth_header: str | None = None
    ) -> None:
        if (token is None) == (auth_header is None):
            raise ValueError("Pass exactly one of token or auth_header")
        self._auth = auth_header or f"Bearer {token}"
        self._scope = cache_scope
        self._http = httpx.Client(
            base_url=settings.GITHUB_API_BASE_URL,
            timeout=settings.GITHUB_HTTP_TIMEOUT,
            headers={"X-GitHub-Api-Version": API_VERSION, "User-Agent": "ContribFinder"},
        )

    @classmethod
    def for_user(cls, user: User, *, cache_scope: str | None = None) -> GitHubClient:
        """Build a client with the user's decrypted token. Raises GitHubAuthError if the
        user has no connected GitHub account.

        ``cache_scope`` defaults to the user; pass ``PUBLIC_SCOPE`` for public repository
        endpoints so their ETags are shared with other users and the app client."""
        account = GitHubAccount.objects.filter(user=user).first()
        if account is None:
            raise GitHubAuthError("No connected GitHub account")
        return cls(
            decrypt_token(account.access_token_encrypted), cache_scope=cache_scope or str(user.pk)
        )

    @classmethod
    def for_app(cls) -> GitHubClient:
        """Client authenticated with the OAuth app's client credentials, for public data that
        belongs to no user (background repository refresh). Raises GitHubAuthError when the
        credentials are not configured."""
        client_id, secret = settings.GITHUB_CLIENT_ID, settings.GITHUB_CLIENT_SECRET
        if not client_id or not secret:
            raise GitHubAuthError("GitHub client credentials are not configured")
        basic = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
        return cls(auth_header=f"Basic {basic}", cache_scope=PUBLIC_SCOPE)

    def __repr__(self) -> str:
        return f"<GitHubClient scope={self._scope}>"

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> GitHubClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- public API -----------------------------------------------------------

    def get_authenticated_user(self) -> GitHubUser:
        return GitHubUser.from_api(self._get("/user").json())

    def list_owned_repositories(self, login: str) -> tuple[list[GitHubRepo], bool]:
        page = self._paginate(f"/users/{login}/repos", {"type": "owner", "sort": "pushed"})
        return [GitHubRepo.from_api(item) for item in page.items], page.truncated

    def get_languages(self, full_name: str) -> dict[str, int]:
        data = self._get(f"/repos/{full_name}/languages").json()
        return {str(lang): int(count) for lang, count in data.items()}

    def get_profile_readme(self, login: str) -> str | None:
        try:
            return self._get(f"/repos/{login}/{login}/readme", accept=RAW).text
        except GitHubNotFound:
            return None

    def get_repository(self, full_name: str) -> GitHubRepo:
        return GitHubRepo.from_api(self._get(f"/repos/{full_name}").json())

    def list_root_contents(self, full_name: str) -> list[ContentEntry]:
        """Top-level entries of the default branch; ``[]`` for an empty repository."""
        try:
            data = self._get(f"/repos/{full_name}/contents/").json()
        except GitHubNotFound:
            return []
        if not isinstance(data, list):
            return []
        return [
            ContentEntry(str(e.get("name", "")), str(e.get("type", "")), int(e.get("size") or 0))
            for e in data
        ]

    def get_file(self, full_name: str, path: str) -> str:
        return self._get(f"/repos/{full_name}/contents/{quote(path)}", accept=RAW).text

    def search_merged_pull_requests(self, login: str) -> tuple[list[PullRequestRef], bool]:
        """Public merged PRs authored by ``login`` in repositories it does not own, most
        recently updated first. Raises GitHubValidationError (422) when GitHub refuses to
        search the user."""
        query = f"type:pr author:{login} is:merged is:public -user:{login}"
        limit = settings.GITHUB_CONTRIB_MAX_PRS
        page = self._paginate(
            "/search/issues",
            {"q": query, "sort": "updated", "order": "desc"},
            items_key="items",
            max_pages=max(1, -(-limit // PER_PAGE)),
        )
        refs = [
            PullRequestRef(
                repo_full_name=_repo_from_api_url(str(item["repository_url"])),
                merged_at=_dt((item.get("pull_request") or {}).get("merged_at")),
            )
            for item in page.items[:limit]
        ]
        return refs, page.truncated or len(page.items) > limit

    def list_public_pushes(self, login: str) -> list[PushRef]:
        """Recent public pushes by ``login`` to repositories it does not own."""
        page = self._paginate(f"/users/{login}/events/public", {}, max_pages=EVENTS_MAX_PAGES)
        pushes = []
        for event in page.items:
            repo = str((event.get("repo") or {}).get("name", ""))
            owner = repo.split("/", 1)[0]
            if event.get("type") == "PushEvent" and repo and owner.lower() != login.lower():
                pushes.append(PushRef(repo, _dt(event.get("created_at"))))
        return pushes

    # --- candidate repositories (Phase 4) -------------------------------------------

    def search_repositories(self, query: str, limit: int) -> list[GitHubRepo]:
        """First page (best match) of a repository search, at most ``limit`` (≤ 100) results.
        Raises GitHubValidationError (422) for a query GitHub rejects."""
        params = urlencode({"q": query, "per_page": min(limit, PER_PAGE)})
        data = self._get(f"/search/repositories?{params}").json()
        return [GitHubRepo.from_api(item) for item in data.get("items", [])[:limit]]

    def get_readme(self, full_name: str) -> str | None:
        try:
            return self._get(f"/repos/{full_name}/readme", accept=RAW).text
        except GitHubNotFound:
            return None

    def get_community_profile(self, full_name: str) -> CommunityProfile:
        try:
            files = self._get(f"/repos/{full_name}/community/profile").json().get("files") or {}
        except GitHubNotFound:
            files = {}
        return CommunityProfile(
            has_contributing=bool(files.get("contributing")),
            has_code_of_conduct=bool(
                files.get("code_of_conduct_file") or files.get("code_of_conduct")
            ),
            has_issue_template=bool(files.get("issue_template")),
            has_pull_request_template=bool(files.get("pull_request_template")),
        )

    def list_label_names(self, full_name: str) -> list[str]:
        page = self._paginate(f"/repos/{full_name}/labels", {}, max_pages=LABELS_MAX_PAGES)
        return [str(label.get("name", "")) for label in page.items]

    def count_commits_since(self, full_name: str, since: datetime) -> int:
        """Default-branch commits since ``since`` (truncated to the UTC day, so the URL and
        its ETag are stable within a day). An empty repository (409) has 0."""
        day = since.astimezone(UTC).strftime("%Y-%m-%dT00:00:00Z")
        try:
            response = self._get(
                f"/repos/{full_name}/commits?{urlencode({'since': day, 'per_page': 1})}"
            )
        except GitHubConflict:
            return 0
        return _count_from_single_item_page(response)

    def count_contributors(self, full_name: str) -> int | None:
        """Contributors (anonymous included), or None when GitHub will not list them (403 for
        very large repositories)."""
        try:
            response = self._get(
                f"/repos/{full_name}/contributors?{urlencode({'per_page': 1, 'anon': 1})}"
            )
        except GitHubForbidden:
            return None
        if response.status == 204:  # empty repository
            return 0
        return _count_from_single_item_page(response)

    def recent_pull_requests(self, full_name: str, since: datetime) -> PullSample:
        params = urlencode(
            {"state": "all", "sort": "updated", "direction": "desc", "per_page": PER_PAGE}
        )
        items: list[dict[str, Any]] = self._get(f"/repos/{full_name}/pulls?{params}").json()
        opened = merged = 0
        for pr in items:
            created, merged_at = _dt(pr.get("created_at")), _dt(pr.get("merged_at"))
            opened += bool(created and created >= since)
            merged += bool(merged_at and merged_at >= since)
        oldest = _dt(items[-1].get("updated_at")) if items else None
        capped = len(items) >= PER_PAGE and oldest is not None and oldest >= since
        return PullSample(opened=opened, merged=merged, capped=capped)

    def get_latest_release_date(self, full_name: str) -> datetime | None:
        try:
            data = self._get(f"/repos/{full_name}/releases/latest").json()
        except GitHubNotFound:
            return None
        return _dt(data.get("published_at") or data.get("created_at"))

    # --- transport ------------------------------------------------------------

    def _paginate(
        self,
        path: str,
        params: dict[str, str],
        *,
        items_key: str | None = None,
        max_pages: int | None = None,
    ) -> Page:
        """Follow ``Link: rel="next"`` up to ``max_pages`` (never more than
        ``GITHUB_MAX_PAGES``). ``items_key`` selects the list in object responses (search)."""
        limit = min(max_pages or settings.GITHUB_MAX_PAGES, settings.GITHUB_MAX_PAGES)
        url: str | None = f"{path}?{urlencode({**params, 'per_page': PER_PAGE})}"
        items: list[dict[str, Any]] = []
        pages = 0
        while url is not None:
            if pages >= limit:
                return Page(items=items, truncated=True)
            response = self._get(url)
            data = response.json()
            items.extend(data[items_key] if items_key else data)
            pages += 1
            url = _next_link(response.link)
        return Page(items=items, truncated=False)

    def _cache_key(self, url: str, accept: str) -> str:
        digest = hashlib.sha256(f"{accept} {url}".encode()).hexdigest()
        return f"github:etag:{self._scope}:{digest}"

    def _get(self, url: str, *, accept: str = JSON) -> _Response:
        key = self._cache_key(url, accept)
        cached: dict[str, Any] | None = cache.get(key)
        headers = {"Accept": accept, "Authorization": self._auth}
        if cached:
            headers["If-None-Match"] = cached["etag"]

        path = httpx.URL(url).path
        try:
            response = self._http.get(url, headers=headers)
        except httpx.TransportError as exc:
            raise GitHubTransientError(f"GET {path}: {type(exc).__name__}") from None

        self._record_rate_limit(response)

        if response.status_code == 304 and cached:
            return _Response(status=200, text=cached["body"], link=cached.get("link", ""))
        if response.status_code == 204:
            return _Response(status=204, text="", link="")
        if response.status_code == 200:
            result = _Response(200, response.text, response.headers.get("Link", ""))
            if etag := response.headers.get("ETag"):
                cache.set(
                    key,
                    {"etag": etag, "body": result.text, "link": result.link},
                    settings.GITHUB_ETAG_TTL,
                )
            return result
        raise _error_for(response, path)

    def _record_rate_limit(self, response: httpx.Response) -> None:
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is None:
            return
        cache.set(
            f"github:ratelimit:{self._scope}",
            {
                "limit": response.headers.get("X-RateLimit-Limit"),
                "remaining": remaining,
                "reset": response.headers.get("X-RateLimit-Reset"),
                "resource": response.headers.get("X-RateLimit-Resource"),
            },
            60 * 60,
        )


def _count_from_single_item_page(response: _Response) -> int:
    """Total items of a ``per_page=1`` listing: the page number of ``rel="last"``, or the
    number of items on the only page."""
    for part in response.link.split(","):
        section = part.split(";")
        if len(section) >= 2 and 'rel="last"' in section[1]:
            page = httpx.URL(section[0].strip().strip("<>")).params.get("page")
            if page and page.isdigit():
                return int(page)
    data = response.json() if response.text else []
    return len(data) if isinstance(data, list) else 0


def _next_link(link_header: str) -> str | None:
    for part in link_header.split(","):
        section = part.split(";")
        if len(section) >= 2 and 'rel="next"' in section[1]:
            url = section[0].strip().strip("<>")
            # Only ever follow links on the API host: the Authorization header goes with them.
            if httpx.URL(url).host != httpx.URL(settings.GITHUB_API_BASE_URL).host:
                raise GitHubClientError("Pagination link points outside the GitHub API host")
            return url
    return None


def _error_for(response: httpx.Response, path: str) -> Exception:
    status = response.status_code
    where = f"GET {path} returned {status}"
    if status == 401:
        return GitHubAuthError(where)
    if status in (403, 429):
        retry_after = response.headers.get("Retry-After")
        if retry_after and retry_after.isdigit():
            return GitHubRateLimited(where, int(retry_after))
        if response.headers.get("X-RateLimit-Remaining") == "0":
            reset = response.headers.get("X-RateLimit-Reset", "")
            wait = (
                int(reset) - int(time.time()) if reset.isdigit() else SECONDARY_LIMIT_DEFAULT_WAIT
            )
            return GitHubRateLimited(where, max(wait, 1))
        if status == 429:
            return GitHubRateLimited(where, SECONDARY_LIMIT_DEFAULT_WAIT)
        return GitHubForbidden(where)
    if status == 404:
        return GitHubNotFound(where)
    if status == 409:
        return GitHubConflict(where)
    if status == 451:
        return GitHubUnavailableForLegalReasons(where)
    if status == 422:
        return GitHubValidationError(where)
    if status >= 500:
        return GitHubTransientError(where)
    return GitHubClientError(where)
