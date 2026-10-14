"""Technologies an issue mentions (spec: issue-analysis; design D4). Pure.

Uses the skill catalog and its context rules: ambiguous words ("Go", "Rust") count in labels,
which are curated tags like a README's tech section, but never in free text (title, body).
Markup (HTML, CSS) is left out: nearly every web issue mentions it, so it says little about the
work, and it would inflate both technology matches and the difficulty technology count.
"""

from __future__ import annotations

from collections.abc import Iterable

from services.profiling.readme import ALL_MATCHER, PLAIN_MATCHER
from services.profiling.taxonomy import MARKUP
from services.profiling.text import plain_text

TITLE = "title"
LABEL = "label"
BODY = "body"


def detect(title: str, raw_labels: Iterable[str], body: str) -> list[dict[str, str]]:
    """``[{slug, source}]`` in order of first appearance: title, then labels, then body.
    A technology keeps the first place it was found."""
    found: dict[str, str] = {}
    for slug in PLAIN_MATCHER.find(title):
        found.setdefault(slug, TITLE)
    for label in raw_labels:
        for slug in ALL_MATCHER.find(label.replace("-", " ").replace("_", " ")):
            found.setdefault(slug, LABEL)
    for slug in PLAIN_MATCHER.find(plain_text(body)):
        found.setdefault(slug, BODY)
    return [
        {"slug": slug, "source": source} for slug, source in found.items() if slug not in MARKUP
    ]
