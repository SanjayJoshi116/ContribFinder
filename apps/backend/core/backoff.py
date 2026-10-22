"""Per-process backoff after a cache error (github-error-resilience D9, performance-cleanup D1).

A cache that is down makes every call wait for the socket timeout. After the first error a
caller skips the cache in this process for the seconds named by a setting, so later calls go
straight to their fallback. Each caller has its own instance: one failing use of the cache
never turns off another.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any, ClassVar

from django.conf import settings


class Backoff:
    _instances: ClassVar[list[Backoff]] = []

    def __init__(self, setting_name: str, what: str, logger: logging.Logger) -> None:
        self._setting_name = setting_name
        self._what = what
        self._logger = logger  # the caller's, so warnings name where the cache failed
        self._down_until = 0.0  # monotonic time
        Backoff._instances.append(self)

    def down(self) -> bool:
        return time.monotonic() < self._down_until

    def call(self, fn: Callable[..., Any], *args: Any, fallback: Callable[[], Any]) -> Any:
        """``fn(*args)``, or ``fallback()`` while the cache is down or when ``fn`` fails (which
        starts the backoff)."""
        if not self.down():
            try:
                return fn(*args)
            except Exception as exc:
                self._mark_down(exc)
        return fallback()

    def _mark_down(self, exc: Exception) -> None:
        seconds = getattr(settings, self._setting_name)
        self._down_until = time.monotonic() + seconds
        self._logger.warning(
            "%s unavailable (%s); skipping it for %s s", self._what, type(exc).__name__, seconds
        )

    @classmethod
    def reset_all(cls) -> None:
        """Forget earlier errors in every instance (tests)."""
        for backoff in cls._instances:
            backoff._down_until = 0.0
