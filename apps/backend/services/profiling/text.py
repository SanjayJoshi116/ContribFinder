"""Case-insensitive, word-boundary phrase matching shared by README skill and interest
extraction."""

from __future__ import annotations

import re
from collections.abc import Mapping

# A phrase must not touch letters, digits or the symbols that change a technology's name
# ("c" must not match inside "c++" or "c#"). A trailing "." (end of sentence) is allowed.
_BEFORE = r"(?<![\w+#.])"
_AFTER = r"(?![\w+#])"

_URL = re.compile(r"https?://\S+|www\.\S+")
_HTML_TAG = re.compile(r"<[^>]+>")
_MD_LINK_TARGET = re.compile(r"\]\([^)]*\)")


class PhraseMatcher:
    """Finds catalog phrases in text and maps each to its slug."""

    def __init__(self, phrases: Mapping[str, str]) -> None:
        self._slugs = {p.lower(): slug for p, slug in phrases.items()}
        ordered = sorted(self._slugs, key=len, reverse=True)  # longest phrase wins
        alternation = "|".join(re.escape(p) for p in ordered)
        self._pattern = re.compile(f"{_BEFORE}(?:{alternation}){_AFTER}", re.IGNORECASE)

    def find(self, text: str) -> dict[str, str]:
        """``{slug: first matched phrase}`` in order of first appearance."""
        found: dict[str, str] = {}
        if not self._slugs:
            return found
        for match in self._pattern.finditer(text):
            phrase = match.group(0).lower()
            found.setdefault(self._slugs[phrase], phrase)
        return found


def plain_text(markdown: str) -> str:
    """Markdown/HTML reduced to prose: URLs, link targets and tags removed."""
    text = _MD_LINK_TARGET.sub("]", markdown)
    text = _HTML_TAG.sub(" ", text)
    return _URL.sub(" ", text)
