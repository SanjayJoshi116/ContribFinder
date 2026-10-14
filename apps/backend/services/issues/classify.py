"""Contribution type and difficulty of an issue (spec: issue-analysis; design D4). Pure.

Contribution type: canonical labels decide first, in a fixed priority order; title keywords
only when no label applies; otherwise ``unknown``.

Difficulty: every signal votes for a level or abstains. A level wins only with at least two
votes and no vote for another level, so a label alone never decides and contradicting signals
give ``unknown``. The evidence lists every signal, including abstentions.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from issues.models import ContributionType as CT
from issues.models import Difficulty

from . import labels as L

# Canonical label -> contribution type, highest priority first.
LABEL_TYPES: tuple[tuple[str, str], ...] = (
    (L.BUG, CT.BUG_FIX),
    (L.DOCUMENTATION, CT.DOCUMENTATION),
    (L.TESTING, CT.TESTING),
    (L.INFRASTRUCTURE, CT.DEVOPS),
    (L.DESIGN, CT.DESIGN),
    (L.ENHANCEMENT, CT.FEATURE),
    (L.REFACTORING, CT.CODE),
    (L.PERFORMANCE, CT.CODE),
    (L.SECURITY, CT.CODE),
    (L.FRONTEND, CT.CODE),
    (L.BACKEND, CT.CODE),
)

# Title keywords per contribution type, tried in this order when no label decides.
KEYWORD_TYPES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (CT.DOCUMENTATION, ("docs", "doc", "documentation", "readme", "typo", "typos", "docstring")),
    (CT.TESTING, ("test", "tests", "testing", "coverage")),
    (CT.DEVOPS, ("ci", "docker", "dockerfile", "workflow", "github actions", "pipeline")),
    (
        CT.BUG_FIX,
        ("bug", "bugs", "crash", "crashes", "error", "fails", "failing", "broken", "exception"),
    ),
)


def _keyword_pattern(words: Sequence[str]) -> re.Pattern[str]:
    alternation = "|".join(re.escape(w) for w in words)
    return re.compile(rf"(?<![\w-])(?:{alternation})(?![\w-])", re.IGNORECASE)


_KEYWORDS = [(ctype, _keyword_pattern(words)) for ctype, words in KEYWORD_TYPES]

# Difficulty-indicating label forms (after normalization and scope stripping).
DIFFICULTY_LABELS: dict[str, str] = {
    **dict.fromkeys(
        ("easy", "beginner", "starter", "trivial", "low hanging fruit"), Difficulty.BEGINNER
    ),
    **dict.fromkeys(("medium", "intermediate", "moderate"), Difficulty.INTERMEDIATE),
    **dict.fromkeys(("hard", "complex", "expert", "advanced", "difficult"), Difficulty.ADVANCED),
}
LEVELS = (Difficulty.BEGINNER, Difficulty.INTERMEDIATE, Difficulty.ADVANCED)
MIN_VOTES = 2


def contribution_type(canonical: Sequence[str], title: str) -> tuple[str, dict[str, Any]]:
    """``(type, evidence)``; evidence names the label or keyword that decided it."""
    present = set(canonical)
    for label, ctype in LABEL_TYPES:
        if label in present:
            return str(ctype), {"by": "label", "value": label}
    for ctype, pattern in _KEYWORDS:
        if match := pattern.search(title):
            return str(ctype), {"by": "keyword", "value": match.group(0).lower()}
    return str(CT.UNKNOWN), {}


def _vote(signal: str, vote: str | None, value: Any) -> dict[str, Any]:
    return {"signal": signal, "vote": str(vote) if vote else None, "value": value}


def _label_votes(raw: Sequence[str]) -> list[dict[str, Any]]:
    """One vote per level the labels indicate (labels naming two levels contradict)."""
    found: dict[str, str] = {}  # level -> raw label that indicated it
    for name in raw:
        if L.category(name) == L.GOOD_FIRST_ISSUE:
            found.setdefault(Difficulty.BEGINNER, name)
        for form in L.forms(name):
            if (level := DIFFICULTY_LABELS.get(form)) is not None:
                found.setdefault(level, name)
                break
    if not found:
        return [_vote("label", None, None)]
    return [_vote("label", level, found[level]) for level in LEVELS if level in found]


def difficulty(
    *,
    raw_labels: Sequence[str],
    body: str,
    technology_count: int,
    contribution_type: str,
    comments: int,
    thresholds: Mapping[str, int],
) -> tuple[str, dict[str, Any]]:
    """``(level, evidence)``. Signals: difficulty labels; description length (short votes
    beginner, long advanced, empty abstains); technologies mentioned (one votes beginner, two
    or more intermediate, ``many_technologies`` or more advanced, none abstains); a
    documentation contribution votes beginner; a long discussion votes advanced."""
    signals = _label_votes(raw_labels)

    length = len(body.strip())
    body_vote: str | None = None  # an empty description says nothing about the work
    if 0 < length < thresholds["short_body"]:
        body_vote = Difficulty.BEGINNER
    elif length > thresholds["long_body"]:
        body_vote = Difficulty.ADVANCED
    signals.append(_vote("body_length", body_vote, length))

    tech_vote: str | None = None
    if technology_count >= thresholds["many_technologies"]:
        tech_vote = Difficulty.ADVANCED
    elif technology_count >= 2:
        tech_vote = Difficulty.INTERMEDIATE
    elif technology_count == 1:
        tech_vote = Difficulty.BEGINNER
    signals.append(_vote("technology_count", tech_vote, technology_count))

    type_vote = Difficulty.BEGINNER if contribution_type == CT.DOCUMENTATION else None
    signals.append(_vote("contribution_type", type_vote, contribution_type))

    discussion_vote = Difficulty.ADVANCED if comments >= thresholds["long_discussion"] else None
    signals.append(_vote("comments", discussion_vote, comments))

    votes = {str(level): sum(s["vote"] == level for s in signals) for level in LEVELS}
    voted = [level for level, count in votes.items() if count]
    level = voted[0] if len(voted) == 1 and votes[voted[0]] >= MIN_VOTES else Difficulty.UNKNOWN
    return str(level), {"signals": signals, "votes": votes, "thresholds": dict(thresholds)}
