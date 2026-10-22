"""Small text helpers for template-built sentences (summaries, reasons)."""

from __future__ import annotations

from collections.abc import Sequence


def join_names(names: Sequence[str]) -> str:
    """``a``, ``a and b``, ``a, b and c``."""
    if len(names) <= 1:
        return "".join(names)
    return f"{', '.join(names[:-1])} and {names[-1]}"
