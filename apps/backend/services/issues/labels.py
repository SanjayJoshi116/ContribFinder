"""Issue label normalization (spec: issue-analysis; design D4). Pure.

Raw label names vary by repository ("Type: Bug", "kind/docs", "good-first-issue"); they map to
a small set of canonical categories through an alias table. The table is a catalog, like the
skill taxonomy: bump ``ISSUE_TAXONOMY_VERSION`` on any edit. Labels that match no category
stay raw only.
"""

from __future__ import annotations

import functools
import re
from collections.abc import Iterable
from typing import NamedTuple

ISSUE_TAXONOMY_VERSION = "2026.11.1"

GOOD_FIRST_ISSUE = "good_first_issue"
HELP_WANTED = "help_wanted"
DOCUMENTATION = "documentation"
BUG = "bug"
ENHANCEMENT = "enhancement"
REFACTORING = "refactoring"
TESTING = "testing"
FRONTEND = "frontend"
BACKEND = "backend"
PERFORMANCE = "performance"
SECURITY = "security"
INFRASTRUCTURE = "infrastructure"
DESIGN = "design"

CATEGORIES = (
    GOOD_FIRST_ISSUE,
    HELP_WANTED,
    DOCUMENTATION,
    BUG,
    ENHANCEMENT,
    REFACTORING,
    TESTING,
    FRONTEND,
    BACKEND,
    PERFORMANCE,
    SECURITY,
    INFRASTRUCTURE,
    DESIGN,
)

# Normalized label form (see ``normalize``) -> canonical category.
ALIASES: dict[str, str] = {
    **dict.fromkeys(
        (
            "good first issue",
            "good first bug",
            "good first contribution",
            "good first pr",
            "first timers only",
            "first timer",
            "first timers",
            "beginner friendly",
            "newcomer friendly",
            "newcomer",
            "easy first",
        ),
        GOOD_FIRST_ISSUE,
    ),
    **dict.fromkeys(
        (
            "help wanted",
            "help needed",
            "community help wanted",
            "contributions welcome",
            "pr welcome",
            "prs welcome",
            "pull request welcome",
            "up for grabs",
        ),
        HELP_WANTED,
    ),
    **dict.fromkeys(("documentation", "docs", "doc", "readme"), DOCUMENTATION),
    **dict.fromkeys(("bug", "bugs", "defect", "regression", "crash", "bug fix", "bugfix"), BUG),
    **dict.fromkeys(
        ("enhancement", "feature", "feature request", "new feature", "improvement", "feat"),
        ENHANCEMENT,
    ),
    **dict.fromkeys(
        ("refactor", "refactoring", "cleanup", "code cleanup", "tech debt", "technical debt"),
        REFACTORING,
    ),
    **dict.fromkeys(("test", "tests", "testing", "unit tests", "test coverage"), TESTING),
    **dict.fromkeys(("frontend", "front end", "ui"), FRONTEND),
    **dict.fromkeys(("backend", "back end", "server"), BACKEND),
    **dict.fromkeys(("performance", "perf", "optimization", "optimisation", "speed"), PERFORMANCE),
    **dict.fromkeys(("security", "vulnerability", "cve"), SECURITY),
    **dict.fromkeys(
        (
            "infrastructure",
            "infra",
            "ci",
            "ci/cd",
            "build",
            "devops",
            "deployment",
            "docker",
            "packaging",
        ),
        INFRASTRUCTURE,
    ),
    **dict.fromkeys(("design", "ux", "ui/ux", "ux design"), DESIGN),
}

# Difficulty-indicating label forms (normalized, without scope) → level (``Difficulty`` values).
DIFFICULTY_FORMS: dict[str, str] = {
    **dict.fromkeys(("easy", "beginner", "starter", "trivial", "low hanging fruit"), "beginner"),
    **dict.fromkeys(("medium", "intermediate", "moderate"), "intermediate"),
    **dict.fromkeys(("hard", "complex", "expert", "advanced", "difficult"), "advanced"),
}

_SEPARATORS = re.compile(r"[\s_-]+")
# A leading "." stays: ".NET" is a technology.
_EDGES = re.compile(r"^[^a-z0-9.]+|[^a-z0-9+#]+$")
# A leading scope such as "type:", "kind/", "area/" or "[type]" (its "[" is already dropped by
# ``_EDGES``); "good first issue" has none.
_SCOPE = re.compile(r"^([a-z ]{1,20})[:/\]]\s*")
# Words under which a label states difficulty ("difficulty: easy", "E-easy", "Skill Level:
# Easy"). Any other scope ("Priority: Medium", "severity: trivial") says nothing about the work.
DIFFICULTY_SCOPES = frozenset(
    {"difficulty", "level", "complexity", "effort", "e", "exp", "experience", "skill"}
)
# Words that scope a label without punctuation ("type-bug", "E-easy", "C-feature-request",
# "skill-level-easy"; hyphens read as spaces). No alias or difficulty form starts with one (a
# test checks it).
SCOPE_WORDS = DIFFICULTY_SCOPES | {"type", "kind", "area", "category", "cat", "c", "t", "a", "lang"}


class LabelParts(NamedTuple):
    """A label read once: its normalized form, its scope ("" when none) and the rest."""

    full: str
    scope: str
    value: str


def normalize(name: str) -> str:
    """Lower case; spaces, hyphens and underscores alike; leading and trailing symbols (emoji,
    brackets) dropped."""
    return _EDGES.sub("", _SEPARATORS.sub(" ", name.lower()).strip())


@functools.lru_cache(maxsize=4096)
def parts(name: str) -> LabelParts:
    """The one label parser (categories, difficulty votes, technologies): a punctuated scope
    (``type:``, ``kind/``, ``[type]``), else the leading words in ``SCOPE_WORDS``. A lone
    one-letter word scopes only a known category or difficulty ("C-bug", "E-easy"); "C-API",
    "c extension" and "e-commerce" have no scope."""
    full = normalize(name)
    if (match := _SCOPE.match(full)) and (value := full[match.end() :].strip()):
        return LabelParts(full, match.group(1).strip(), value)
    words = full.split(" ")
    n = 0
    while n < len(words) - 1 and words[n] in SCOPE_WORDS:
        n += 1
    scope, value = " ".join(words[:n]), " ".join(words[n:])
    if not n or (len(scope) == 1 and value not in ALIASES and value not in DIFFICULTY_FORMS):
        return LabelParts(full, "", full)
    return LabelParts(full, scope, value)


def scoped_by(scope: str, words: frozenset[str]) -> bool:
    """Whether ``scope`` is made only of ``words`` ("skill level" by ``DIFFICULTY_SCOPES``);
    an empty scope is not."""
    return bool(scope) and all(w in words for w in scope.split())


def category(name: str) -> str | None:
    """The category of the normalized label, else of the same without its scope."""
    p = parts(name)
    return ALIASES.get(p.full) or ALIASES.get(p.value)


def normalize_labels(raw: Iterable[str]) -> list[str]:
    """Canonical categories of the raw labels, in ``CATEGORIES`` order, without duplicates."""
    found = {c for name in raw if (c := category(name))}
    return [c for c in CATEGORIES if c in found]
