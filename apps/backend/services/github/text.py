"""GitHub text made storable (spec "Stored GitHub text"): the one cleaner for the API client and
the OAuth identity fetch, which cannot import the client (the client imports ``oauth``)."""

from __future__ import annotations

import json
import re
from typing import Any

_UNSTORABLE = re.compile("[\x00\ud800-\udfff]")
# The JSON escapes that parse into a character ``_UNSTORABLE`` matches (a raw NUL is invalid JSON
# and a raw surrogate cannot come from decoded bytes).
_UNSTORABLE_ESCAPE = re.compile(r"\\u(?:0000|[dD][89a-fA-F])")


def storable(text: str) -> str:
    """``text`` without what PostgreSQL cannot store: NUL removed, unpaired surrogates (from a
    ``\\ud800`` escape in JSON; a valid pair is already one character) replaced by U+FFFD."""
    return _UNSTORABLE.sub(lambda m: "" if m.group() == "\x00" else "�", text)


def storable_json(value: Any) -> Any:
    """Every string of a parsed JSON body, keys included, made ``storable``."""
    if isinstance(value, str):
        return storable(value)
    if isinstance(value, list):
        return [storable_json(item) for item in value]
    if isinstance(value, dict):
        return {storable(k): storable_json(v) for k, v in value.items()}
    return value


def parse_json(text: str) -> Any:
    """``json.loads(text)`` with every string storable. Only a ``\\u0000`` or lone-surrogate
    escape can parse into an unstorable string: the body is walked (and copied) only then."""
    parsed = json.loads(text)
    return storable_json(parsed) if _UNSTORABLE_ESCAPE.search(text) else parsed
