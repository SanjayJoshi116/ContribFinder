"""Issue label normalization (spec: issue-analysis; design D4). Pure.

Raw label names vary by repository ("Type: Bug", "kind/docs", "good-first-issue"); they map to
a small set of canonical categories through an alias table. The table is a catalog, like the
skill taxonomy: bump ``ISSUE_TAXONOMY_VERSION`` on any edit. Labels that match no category
stay raw only.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

ISSUE_TAXONOMY_VERSION = "2026.10.2"

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

_SEPARATORS = re.compile(r"[\s_-]+")
_EDGES = re.compile(r"^[^a-z0-9]+|[^a-z0-9+#]+$")
# A leading scope such as "type:", "kind/" or "area/" ("good first issue" has none).
_SCOPE = re.compile(r"^[a-z ]{1,20}[:/]\s*")


def normalize(name: str) -> str:
    """Lower case; spaces, hyphens and underscores alike; leading and trailing symbols (emoji,
    brackets) dropped."""
    return _EDGES.sub("", _SEPARATORS.sub(" ", name.lower()).strip())


def forms(name: str) -> tuple[str, ...]:
    """The normalized label, then the same without its scope prefix when it has one."""
    full = normalize(name)
    stripped = _SCOPE.sub("", full, count=1).strip()
    return (full, stripped) if stripped and stripped != full else (full,)


def category(name: str) -> str | None:
    for form in forms(name):
        if found := ALIASES.get(form):
            return found
    return None


def normalize_labels(raw: Iterable[str]) -> list[str]:
    """Canonical categories of the raw labels, in ``CATEGORIES`` order, without duplicates."""
    found = {c for name in raw if (c := category(name))}
    return [c for c in CATEGORIES if c in found]
