from collections.abc import Iterator
from typing import cast

import pytest
import respx
from django.core.cache import cache
from rest_framework.test import APIClient

from accounts.models import User
from github.models import GitHubAccount

from .factories import GitHubAccountFactory


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    # Throttle counters live in the cache; isolate them per test.
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _isolate_respx() -> Iterator[None]:
    # Routes registered on the global router outside an active `@respx.mock` would otherwise
    # leak into later tests. Prefer the `respx_mock` fixture for non-default options.
    yield
    respx.mock.clear()
    respx.mock.reset()


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def csrf_client() -> APIClient:
    """Client that enforces CSRF checks like a real browser session would."""
    return APIClient(enforce_csrf_checks=True)


@pytest.fixture
def github_account(db: None) -> GitHubAccount:
    return cast(GitHubAccount, GitHubAccountFactory())


@pytest.fixture
def user(github_account: GitHubAccount) -> User:
    return github_account.user


@pytest.fixture
def signed_in_client(api_client: APIClient, user: User) -> APIClient:
    api_client.force_login(user)
    return api_client
