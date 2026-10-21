"""github-error-resilience D9: the request path keeps working when Redis is down."""

import logging

import pytest
from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
from django.contrib.sessions.backends.cached_db import SessionStore as CachedDbStore
from rest_framework.test import APIClient

from core import throttling

pytestmark = [pytest.mark.django_db, pytest.mark.urls("tests.urls")]

THROTTLED = "/api/v1/_test/throttled/"  # 1/min per anonymous client


class _DownCache:
    def __init__(self) -> None:
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        raise ConnectionError("redis down")

    def set(self, *args, **kwargs):
        self.calls += 1
        raise ConnectionError("redis down")


@pytest.fixture(autouse=True)
def _reset_backoff(monkeypatch) -> None:
    monkeypatch.setattr(throttling, "_down_until", 0.0)
    throttling._local.clear()


def test_redis_down_dashboard_read_still_answers(
    signed_in_client: APIClient, monkeypatch, caplog: pytest.LogCaptureFixture
) -> None:
    down = _DownCache()
    monkeypatch.setattr(throttling, "default_cache", down)
    with caplog.at_level(logging.WARNING, logger="core.throttling"):
        first = signed_in_client.get("/api/v1/recommendations")
        calls_after_first = down.calls
        second = signed_in_client.get("/api/v1/recommendations")
    assert first.status_code == 200 and second.status_code == 200
    assert calls_after_first == 1  # the first throttle check failed, the rest were skipped
    assert down.calls == 1
    warnings = [r for r in caplog.records if r.name == "core.throttling"]
    assert len(warnings) == 1
    assert "ConnectionError" in warnings[0].getMessage()
    assert "/api/v1" not in warnings[0].getMessage()


def test_throttling_counts_locally_while_cache_is_down(api_client: APIClient, monkeypatch) -> None:
    monkeypatch.setattr(throttling, "default_cache", _DownCache())
    assert api_client.get(THROTTLED).status_code == 200
    response = api_client.get(THROTTLED)  # over the limit: still limited, in this process
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "throttled"


def test_throttling_resumes_after_backoff(api_client: APIClient, monkeypatch) -> None:
    monkeypatch.setattr(throttling, "default_cache", _DownCache())
    assert api_client.get(THROTTLED).status_code == 200

    from django.core.cache import cache

    monkeypatch.setattr(throttling, "default_cache", cache)
    monkeypatch.setattr(throttling, "_down_until", 0.0)  # the backoff has passed
    assert api_client.get(THROTTLED).status_code == 200  # counted in the shared cache again
    response = api_client.get(THROTTLED)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "throttled"


def test_throttle_bug_is_not_swallowed(api_client: APIClient, monkeypatch) -> None:
    def broken(self, request, view):
        raise RuntimeError("bug")

    monkeypatch.setattr("rest_framework.throttling.AnonRateThrottle.get_cache_key", broken)
    # Not allowed through as a cache outage: the error handler answers 500.
    assert api_client.get(THROTTLED).status_code == 500
    assert throttling._down_until == 0.0


def test_session_from_cached_db_store_still_authenticates(api_client: APIClient, user) -> None:
    store = CachedDbStore()
    store[SESSION_KEY] = str(user.pk)
    store[BACKEND_SESSION_KEY] = settings.AUTHENTICATION_BACKENDS[0]
    store[HASH_SESSION_KEY] = user.get_session_auth_hash()
    store.save()
    assert store.session_key is not None
    api_client.cookies[settings.SESSION_COOKIE_NAME] = store.session_key
    assert api_client.get("/api/v1/auth/me").status_code == 200
