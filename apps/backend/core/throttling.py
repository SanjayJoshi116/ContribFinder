"""DRF throttles that keep working when the cache is unavailable (github-error-resilience D9).

Throttle counters live in the cache (Redis). Without this, a Redis outage turns every API
request into a 500 after the socket timeout, although the request itself only needs
PostgreSQL. A cache error logs a warning and moves the counters of this process to a local
in-memory cache for ``THROTTLE_CACHE_BACKOFF_SECONDS``: requests are still limited (per
process, not across processes) and don't each wait for the timeout. Only cache errors fall
back: a bug in a throttle still raises.
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.cache import cache as default_cache
from django.core.cache.backends.locmem import LocMemCache
from rest_framework import throttling

from core.backoff import Backoff

logger = logging.getLogger(__name__)

_backoff = Backoff("THROTTLE_CACHE_BACKOFF_SECONDS", "Throttle cache", logger)
_local = LocMemCache("throttle-fallback", {})


class _FallbackCache:
    """The cache calls DRF's throttles make: the shared cache, or the local one while it is
    down."""

    def get(self, key: str, default: Any = None) -> Any:
        return _backoff.call(
            default_cache.get, key, default, fallback=lambda: _local.get(key, default)
        )

    def set(self, key: str, value: Any, timeout: int | None = None) -> None:
        _backoff.call(
            default_cache.set, key, value, timeout, fallback=lambda: _local.set(key, value, timeout)
        )


class FallbackCacheMixin:
    cache: Any = _FallbackCache()  # replaces SimpleRateThrottle.cache


class AnonRateThrottle(FallbackCacheMixin, throttling.AnonRateThrottle):
    pass


class UserRateThrottle(FallbackCacheMixin, throttling.UserRateThrottle):
    pass


class ScopedRateThrottle(FallbackCacheMixin, throttling.ScopedRateThrottle):
    pass
