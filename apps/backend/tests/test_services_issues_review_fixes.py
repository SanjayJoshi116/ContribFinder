"""Issue analysis fixes from the review sweep (Bug_Backlog.md batch 57, change
services-issues-review-fixes)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from django.conf import settings
from django.test import override_settings

from core.checks import issue_config_check
from e2e.builders import make_candidate_repo
from issues.models import Issue
from services.issues import classify, labels
from services.issues.analysis import IssueInput
from services.issues.analysis import analyze as analyze_issue
from services.issues.technologies import detect
from services.profiling.text import strip_code_fences

from .checks_helpers import ids
from .repo_fixtures import analyze, issue_payload, mock_repo_api
from .shared_fixtures import public_client  # noqa: F401

THRESHOLDS = dict(settings.ISSUE_DIFFICULTY)


def assess(
    raw_labels: list[str], body: str = "Short report.", technologies: int = 1
) -> tuple[str, dict[str, Any]]:
    return classify.difficulty(
        raw_labels=raw_labels,
        body=body,
        technology_count=technologies,
        contribution_type="bug_fix",
        comments=0,
        thresholds=THRESHOLDS,
    )


def level(raw_labels: list[str], body: str = "Short report.", technologies: int = 1) -> str:
    return assess(raw_labels, body, technologies)[0]


def label_votes(name: str) -> list[Any]:
    return [s["vote"] for s in classify._label_votes([name])]


# --- ISV-1, ISV-10: one label parser -----------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("type-bug", labels.BUG),
        ("C-feature-request", labels.ENHANCEMENT),
        ("kind-documentation", labels.DOCUMENTATION),
        ("area_frontend", labels.FRONTEND),
        ("Type: Bug", labels.BUG),
        ("[Type] Bug", labels.BUG),
    ],
)
def test_scoped_labels_map_to_their_category(name: str, expected: str) -> None:
    assert labels.category(name) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("good first issue", labels.GOOD_FIRST_ISSUE),
        ("good-first-issue", labels.GOOD_FIRST_ISSUE),
        ("help wanted", labels.HELP_WANTED),
        ("bug fix", labels.BUG),
        ("test coverage", labels.TESTING),
        ("ci/cd", labels.INFRASTRUCTURE),
    ],
)
def test_labels_that_only_look_scoped_keep_their_category(name: str, expected: str) -> None:
    assert labels.category(name) == expected


def test_no_alias_or_difficulty_form_starts_with_a_scope_word() -> None:
    forms = [*labels.ALIASES, *classify.DIFFICULTY_LABELS]
    clashes = [f for f in forms if " " in f and f.split(" ", 1)[0] in labels.SCOPE_WORDS]
    assert clashes == []


def test_label_parts() -> None:
    assert labels.parts("E-easy") == labels.LabelParts("e easy", "e", "easy")
    assert labels.parts("Priority: Medium") == ("priority: medium", "priority", "medium")
    assert labels.parts("a11y") == ("a11y", "", "a11y")  # a scope needs its own word
    assert labels.parts("type") == ("type", "", "type")
    assert labels.parts("skill-level-easy") == ("skill level easy", "skill level", "easy")
    # A lone letter scopes only a known category or difficulty.
    assert labels.parts("C-bug").scope == "c"
    assert labels.parts("C-API").scope == ""
    assert labels.parts("e-commerce").scope == ""


@pytest.mark.parametrize(
    ("name", "vote"),
    [
        ("Skill Level: Easy", "beginner"),
        ("Difficulty Level: Hard", "advanced"),
        ("skill-level-easy", "beginner"),
        ("Priority Level: Medium", None),  # every scope word must be a difficulty word
    ],
)
def test_multi_word_difficulty_scope_votes(name: str, vote: str | None) -> None:
    assert label_votes(name) == [vote]


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        (".NET", ["dotnet"]),
        ("C-API", ["c"]),
        ("c extension", ["c"]),
        ("Rust: async", ["rust"]),
        ("go/rust", ["go", "rust"]),
        ("C-bug", []),
        ("lang: go", ["go"]),
    ],
)
def test_label_technologies_keep_the_technology(label: str, expected: list[str]) -> None:
    assert slugs(raw_labels=(label,)) == expected


def test_body_consumers_read_it_through_issue_input() -> None:
    # classify.difficulty and technologies.detect expect IssueInput.body (no HTML comments).
    services = Path(__file__).resolve().parents[1] / "services"
    call = re.compile(
        r"\b(?:classify\.difficulty|technologies\.detect)\("
        r"|^from \S*(?:classify|technologies) import [^\n]*\b(?:difficulty|detect)\b",
        re.M,
    )
    callers = {
        path.relative_to(services).as_posix()
        for path in services.rglob("*.py")
        if call.search(path.read_text(encoding="utf-8"))
    }
    assert callers == {"issues/analysis.py"}


def test_issue_input_strips_before_the_cap() -> None:
    issue = IssueInput("", "<!-- template -->Report", (), 0, max_chars=3)
    assert issue.body == "Rep"


# --- ISV-2: difficulty only from difficulty scopes ---------------------------------------------


def test_priority_label_does_not_contradict_good_first_issue() -> None:
    assert label_votes("Priority: Medium") == [None]
    assert label_votes("severity: trivial") == [None]
    assert level(["good first issue", "Priority: Medium"]) == "beginner"


@pytest.mark.parametrize(
    ("name", "vote"),
    [
        ("E-easy", "beginner"),
        ("skill-easy", "beginner"),  # every difficulty scope is a scope word
        ("experience-hard", "advanced"),
        ("difficulty: hard", "advanced"),
        ("level/medium", "intermediate"),
        ("easy", "beginner"),
        ("type: good first issue", "beginner"),
    ],
)
def test_difficulty_scopes_and_unscoped_labels_vote(name: str, vote: str) -> None:
    assert label_votes(name) == [vote]


def test_e_easy_supported_by_other_signals_is_beginner() -> None:
    assert level(["E-easy"]) == "beginner"


# --- ISV-3, ISV-4: technologies ----------------------------------------------------------------


def slugs(title: str = "", raw_labels: tuple[str, ...] = (), body: str = "") -> list[str]:
    return [t["slug"] for t in detect(title, raw_labels, body)]


def test_scope_word_is_not_a_technology() -> None:
    assert slugs(raw_labels=("C-bug", "C-feature-request")) == []


def test_ambiguous_word_in_the_label_value_counts() -> None:
    found = detect("", ["lang: go", "React Hooks", "C", "python: crash"], "")
    assert found == [
        {"slug": "go", "source": "label"},
        {"slug": "react", "source": "label"},
        {"slug": "c", "source": "label"},
        {"slug": "python", "source": "label"},
    ]


def test_template_comment_adds_no_technology() -> None:
    # Removed once by IssueInput, for every consumer.
    def found(body: str) -> list[str]:
        result = analyze_issue(IssueInput("", body, (), 0), THRESHOLDS)
        return [t["slug"] for t in result.technologies]

    assert found("<!-- e.g. Python >= 3.10, Node.js 20 -->\nThe button does nothing") == []
    assert found("It fails. <!-- Python version? (unterminated") == []
    assert found("Fails on Node.js 20") == ["nodejs"]


# --- ISV-6: fenced code is not the description -------------------------------------------------


def test_strip_code_fences() -> None:
    # A shorter run does not close a longer fence; an unclosed fence runs to the end.
    text = "Before\n````python\nimport x\n```\nstill code\n````\nAfter\n~~~\nopen to the end"
    assert strip_code_fences(text) == "Before\nAfter"
    # Backticks after a backtick run make it inline code, not a fence.
    assert (
        strip_code_fences("```npm test``` fails.\nMore text") == "```npm test``` fails.\nMore text"
    )


def test_pasted_traceback_does_not_make_a_long_description() -> None:
    trace = "Traceback (most recent call last):\n" + "  File x, line 1\n" * 300
    body = f"Clicking save crashes.\n```\n{trace}```\n"
    assert len(body) > THRESHOLDS["long_body"]
    _, evidence = assess([], body)
    body_signal = next(s for s in evidence["signals"] if s["signal"] == "body_length")
    assert body_signal == {"signal": "body_length", "vote": "beginner", "value": 22}


# --- ISV-7: stored body without template comments ----------------------------------------------


@pytest.mark.django_db
@pytest.mark.respx(assert_all_called=False)
def test_long_template_comments_do_not_push_the_report_out(client, respx_mock) -> None:
    repo = make_candidate_repo(7, "encode/httpx")
    report = "Steps:\n1. Open the page\n2. It crashes"
    body = "<!-- " + "Please describe the bug. " * 500 + "-->\n" + report
    assert len(body) > settings.ISSUE_BODY_MAX_CHARS
    mock_repo_api(respx_mock, "encode/httpx", 7, issues=[issue_payload(1, body=body)])

    analyze(client, repo)

    assert Issue.objects.get(repository=repo).body.strip() == report


# --- ISV-5, ISV-7: startup checks --------------------------------------------------------------


def test_default_issue_settings_pass() -> None:
    assert "core.E040" not in ids(issue_config_check())


@pytest.mark.parametrize(
    "overrides",
    [
        {"ISSUE_DIFFICULTY": {**THRESHOLDS, "several_technologies": 3, "many_technologies": 3}},
        {"ISSUE_BODY_MAX_CHARS": THRESHOLDS["long_body"]},
    ],
    ids=["equal-technology-thresholds", "cap-at-long-body"],
)
def test_impossible_difficulty_settings_refused(overrides: dict[str, Any]) -> None:
    with override_settings(**overrides):
        assert "core.E040" in ids(issue_config_check())
