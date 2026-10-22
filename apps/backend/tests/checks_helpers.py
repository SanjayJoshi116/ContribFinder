"""Helpers for system-check tests."""

from collections.abc import Iterable

from django.core.checks import CheckMessage


def ids(messages: Iterable[CheckMessage]) -> list[str]:
    """The check ids of ``messages``, in order."""
    return [m.id for m in messages if m.id is not None]
