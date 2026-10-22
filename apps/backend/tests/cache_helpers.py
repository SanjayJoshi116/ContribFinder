"""Fake caches for cache-outage tests."""

from typing import Any


class DownCache:
    """A cache whose server is unreachable: every call raises and is counted."""

    def __init__(self) -> None:
        self.calls = 0

    def _fail(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        raise ConnectionError("redis down")

    get = set = touch = _fail
