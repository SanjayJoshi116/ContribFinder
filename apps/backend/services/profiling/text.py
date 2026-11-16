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
        # Case-folded keys: IGNORECASE also matches variants whose lower() is not the catalog
        # phrase (dotless i U+0131, long s U+017F, Kelvin sign U+212A); casefold() maps the
        # last two back, and find() skips what still misses (PROF-1).
        self._slugs = {p.casefold(): slug for p, slug in phrases.items()}
        ordered = sorted(self._slugs, key=len, reverse=True)  # longest phrase wins
        alternation = "|".join(re.escape(p) for p in ordered)
        self._pattern = re.compile(f"{_BEFORE}(?:{alternation}){_AFTER}", re.IGNORECASE)

    def find(self, text: str) -> dict[str, str]:
        """``{slug: first matched phrase}`` in order of first appearance. Never raises: a
        match whose case-fold is not a catalog phrase is skipped."""
        found: dict[str, str] = {}
        if not self._slugs:
            return found
        for match in self._pattern.finditer(text):
            if (slug := self._slugs.get(match.group(0).casefold())) is not None:
                found.setdefault(slug, match.group(0).lower())
        return found


# Ends as the HTML parser does: ``-->`` or ``--!>``, and ``<!-->`` / ``<!--->`` are empty.
_HTML_COMMENT = re.compile(r"<!--(?:-?>|.*?(?:--!?>|\Z))", re.S)


def strip_html_comments(text: str) -> str:
    """``text`` without ``<!-- … -->`` comments (HTML, Markdown and XML alike); an unterminated
    ``<!--`` hides the rest, as GitHub renders it. The one stripper for profile READMEs,
    manifests and issue bodies: commented-out content is never evidence (PROF-3, PROF-6)."""
    return _HTML_COMMENT.sub("", text)


# CommonMark fences: an opening run of 3+ backticks or tildes (an info string may follow, without
# a backtick after a backtick run: "```npm test``` fails" is inline code); only a run of the same
# character, at least as long and with nothing after it, closes it.
FENCE = re.compile(r"^\s{0,3}(`{3,}(?=[^`]*$)|~{3,})(.*)$")


def closes_fence(marker: re.Match[str] | None, fence: str) -> bool:
    """Whether the ``FENCE`` match ``marker`` closes the open fence ``fence`` (its marker run)."""
    return bool(
        marker
        and marker.group(1)[0] == fence[0]
        and len(marker.group(1)) >= len(fence)
        and not marker.group(2).strip()
    )


def strip_code_fences(text: str) -> str:
    """``text`` without fenced code blocks, fences included (pasted logs, stack traces); an
    unclosed fence runs to the end, as CommonMark renders it."""
    kept: list[str] = []
    fence = ""
    for line in text.splitlines():
        marker = FENCE.match(line)
        if fence:
            if closes_fence(marker, fence):
                fence = ""
        elif marker:
            fence = marker.group(1)
        else:
            kept.append(line)
    return "\n".join(kept)


def plain_text(markdown: str) -> str:
    """Markdown/HTML reduced to prose: URLs, link targets and tags removed."""
    text = _MD_LINK_TARGET.sub("]", markdown)
    text = _HTML_TAG.sub(" ", text)
    return _URL.sub(" ", text)
