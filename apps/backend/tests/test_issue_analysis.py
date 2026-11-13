"""Issue label normalization, contribution type, difficulty and technologies (Phase 7, group 3).
Pure functions: no database."""

import pytest
from django.conf import settings

from services.issues import classify, labels
from services.issues.analysis import IssueInput, analyze
from services.issues.technologies import detect

THRESHOLDS = {
    "short_body": 600,
    "long_body": 4000,
    "several_technologies": 2,
    "many_technologies": 3,
    "long_discussion": 15,
    "min_votes": 2,
}


# --- labels -------------------------------------------------------------------------------


@pytest.mark.parametrize(("alias", "expected"), sorted(labels.ALIASES.items()))
def test_every_alias_maps_to_its_category(alias: str, expected: str) -> None:
    assert expected in labels.CATEGORIES
    assert labels.category(alias) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Type: Bug", "bug"),
        ("type:bug", "bug"),
        ("[Type] Bug", "bug"),
        ("[area] docs", "documentation"),
        ("kind/docs", "documentation"),
        ("area/frontend", "frontend"),
        ("area: Front-End", "frontend"),
        ("good-first-issue", "good_first_issue"),
        ("Good First Issue", "good_first_issue"),
        ("good_first_issue", "good_first_issue"),
        ("beginner friendly", "good_first_issue"),
        ("status: help wanted", "help_wanted"),
        ("🐛 bug", "bug"),
        ("[docs]", "documentation"),
        ("CI/CD", "infrastructure"),
        ("feature", "enhancement"),
        ("ci", "infrastructure"),
    ],
)
def test_prefix_and_alias_forms(raw: str, expected: str) -> None:
    assert labels.category(raw) == expected


def test_unknown_label_has_no_category() -> None:
    assert labels.category("needs-triage") is None
    assert labels.normalize_labels(["needs-triage"]) == []


def test_spec_scenario_prefixed_and_aliased_labels() -> None:
    raw = ["Type: Bug", "docs", "good-first-issue"]
    assert labels.normalize_labels(raw) == ["good_first_issue", "documentation", "bug"]
    assert raw == ["Type: Bug", "docs", "good-first-issue"]  # raw labels unchanged


def test_duplicate_categories_collapse() -> None:
    assert labels.normalize_labels(["docs", "documentation", "kind/doc"]) == ["documentation"]


# --- contribution type --------------------------------------------------------------------


@pytest.mark.parametrize(("label", "expected"), classify.LABEL_TYPES)
def test_each_label_rule(label: str, expected: str) -> None:
    ctype, evidence = classify.contribution_type([label], "Anything")
    assert ctype == expected
    assert evidence == {"by": "label", "value": label}


def test_label_priority() -> None:
    ctype, evidence = classify.contribution_type(["enhancement", "bug", "documentation"], "x")
    assert (ctype, evidence["value"]) == ("bug_fix", "bug")


def test_approachability_labels_do_not_decide_type() -> None:
    assert classify.contribution_type(["good_first_issue", "help_wanted"], "Rename x")[0] == (
        "unknown"
    )


@pytest.mark.parametrize(
    ("title", "expected", "keyword"),
    [
        ("Fix typo in README", "documentation", "typo"),
        ("Add docs for the CLI", "documentation", "docs"),
        ("Increase test coverage of parser", "testing", "test"),
        ("Run CI on Python 3.13", "devops", "ci"),
        ("Publish a Docker image", "devops", "docker"),
        ("App crashes on startup", "bug_fix", "crashes"),
        ("[Bug]: Avatar flashes during transition", "bug_fix", "bug"),
        ("Import fails with unicode paths", "bug_fix", "fails"),
        # The earliest keyword wins (D-11): a [Bug]: prefix beats a later "docs".
        ("[Bug]: docs build crashes", "bug_fix", "bug"),
        ("Add tests for error handling", "testing", "tests"),
        ("Docs: explain error codes", "documentation", "docs"),
    ],
)
def test_keyword_rules(title: str, expected: str, keyword: str) -> None:
    ctype, evidence = classify.contribution_type([], title)
    assert ctype == expected
    assert evidence == {"by": "keyword", "value": keyword}


def test_keywords_match_whole_words_only() -> None:
    assert classify.contribution_type([], "Add contest mode for decision making")[0] == "unknown"


def test_no_evidence_is_unknown() -> None:
    assert classify.contribution_type([], "Rename the settings module") == ("unknown", {})


# --- difficulty ---------------------------------------------------------------------------


def difficulty(raw=(), body="", techs=0, ctype="unknown", comments=0, **thresholds):
    return classify.difficulty(
        raw_labels=list(raw),
        body=body,
        technology_count=techs,
        contribution_type=ctype,
        comments=comments,
        thresholds={**THRESHOLDS, **thresholds},
    )


def votes_of(evidence) -> dict[str, str | None]:
    return {s["signal"]: s["vote"] for s in evidence["signals"]}


def test_beginner_with_support() -> None:
    level, evidence = difficulty(["good first issue"], body="Short description.", techs=1)
    assert level == "beginner"
    assert votes_of(evidence) == {
        "label": "beginner",
        "body_length": "beginner",
        "technology_count": "beginner",
        "contribution_type": None,
        "comments": None,
    }
    assert evidence["votes"] == {"beginner": 3, "intermediate": 0, "advanced": 0}
    assert evidence["signals"][0]["value"] == "good first issue"


def test_label_alone_is_unknown() -> None:
    level, evidence = difficulty(["good first issue"], body="x" * 1000, techs=0)
    assert level == "unknown"
    assert evidence["votes"]["beginner"] == 1


def test_contradicting_signals_are_unknown() -> None:
    level, evidence = difficulty(["good first issue"], body="x" * 5000, techs=4)
    assert level == "unknown"
    assert evidence["votes"] == {"beginner": 1, "intermediate": 0, "advanced": 2}


def test_intermediate() -> None:
    level, _ = difficulty(["difficulty: medium"], body="x" * 1000, techs=2)
    assert level == "intermediate"


def test_advanced() -> None:
    level, evidence = difficulty(["hard"], body="x" * 5000, techs=3, comments=20)
    assert level == "advanced"
    assert evidence["votes"]["advanced"] == 4


def test_advanced_without_labels() -> None:
    assert difficulty(body="x" * 5000, comments=15)[0] == "advanced"


def test_documentation_votes_beginner() -> None:
    assert difficulty(body="Fix the typo.", ctype="documentation")[0] == "beginner"


def test_labels_naming_two_levels_contradict() -> None:
    level, evidence = difficulty(["easy", "hard"], body="short", techs=1)
    assert level == "unknown"
    assert [s["vote"] for s in evidence["signals"] if s["signal"] == "label"] == [
        "beginner",
        "advanced",
    ]


def test_empty_body_and_no_technology_abstain() -> None:
    level, evidence = difficulty(["good first issue"])
    assert level == "unknown"
    assert votes_of(evidence)["body_length"] is None
    assert votes_of(evidence)["technology_count"] is None


def test_template_comments_do_not_count_as_description() -> None:
    # Longer than long_body (4000) with the comments, short without them.
    # Removed once by IssueInput, for every consumer.
    template = "<!-- Describe the bug in detail. Include steps, versions and logs. -->\n" * 60
    result = analyze(IssueInput("", template + "Typo in README", (), 0), THRESHOLDS)
    assert votes_of(result.difficulty_evidence)["body_length"] == "beginner"
    result = analyze(IssueInput("", template, (), 0), THRESHOLDS)
    assert votes_of(result.difficulty_evidence)["body_length"] is None


def test_thresholds_are_recorded() -> None:
    assert difficulty()[1]["thresholds"] == THRESHOLDS


def test_defaults_are_the_former_fixed_values() -> None:
    # Two technologies voted intermediate and a level needed two votes before both were
    # configurable; the defaults keep every stored analysis valid.
    assert settings.ISSUE_DIFFICULTY == THRESHOLDS


def test_several_technologies_threshold() -> None:
    _, evidence = difficulty(techs=2, several_technologies=3)
    assert votes_of(evidence)["technology_count"] is None
    _, evidence = difficulty(techs=3, several_technologies=3, many_technologies=4)
    assert votes_of(evidence)["technology_count"] == "intermediate"


def test_min_votes_threshold() -> None:
    args = {"raw": ["good first issue"], "body": "Short description."}
    assert difficulty(**args)[0] == "beginner"  # two votes
    level, evidence = difficulty(**args, min_votes=3)
    assert level == "unknown"
    assert evidence["votes"]["beginner"] == 2


@pytest.mark.parametrize(
    ("args", "level"),
    [
        (
            {"raw": ["good first issue"], "body": "Short.", "techs": 1, "ctype": "documentation"},
            "beginner",
        ),
        ({"raw": ["intermediate"], "techs": 2}, "intermediate"),
        ({"raw": ["advanced"], "body": "x" * 5000, "techs": 3, "comments": 20}, "advanced"),
    ],
)
def test_level_voters_match_the_classifier(args, level: str) -> None:
    # LEVEL_VOTERS bounds min_votes at startup (core.E040, core.W004): every signal it lists
    # must vote for the level at once, so the level wins at its full capacity.
    voters = classify.LEVEL_VOTERS[level]
    found, evidence = difficulty(**args, min_votes=len(voters))
    assert found == level
    assert tuple(s for s, vote in votes_of(evidence).items() if vote == level) == voters


# --- technologies -------------------------------------------------------------------------


def test_technology_in_title() -> None:
    assert {"slug": "django", "source": "title"} in detect(
        "Support async views in Django 5", [], ""
    )


def test_first_source_wins_and_order_is_title_labels_body() -> None:
    found = detect("Django admin", ["lang: python"], "Uses PostgreSQL and Django.")
    assert found == [
        {"slug": "django", "source": "title"},
        {"slug": "python", "source": "label"},
        {"slug": "postgresql", "source": "body"},
    ]


def test_ambiguous_words_only_in_labels() -> None:
    assert detect("Go to the settings page and rust stops", [], "Go ahead.") == []
    assert detect("Port the server", ["lang: go"], "") == [{"slug": "go", "source": "label"}]


def test_markup_is_not_a_technology() -> None:
    found = detect("Fix CSS in the Django admin", ["html"], "Broken HTML and CSS markup.")
    assert found == [{"slug": "django", "source": "title"}]


def test_body_urls_and_tags_ignored() -> None:
    assert detect("", [], "See https://github.com/django/django/issues/1 <react>") == []


# --- whole analysis -----------------------------------------------------------------------


def test_analysis_is_deterministic() -> None:
    issue = IssueInput(
        title="Fix typo in Django docs",
        body="The tutorial says djnago.",
        raw_labels=["kind/docs", "good-first-issue"],
        comments=1,
    )
    first, second = analyze(issue, THRESHOLDS), analyze(issue, THRESHOLDS)
    assert first == second
    assert first.labels == ["good_first_issue", "documentation"]
    assert first.contribution_type == "documentation"
    assert first.contribution_type_evidence["by"] == "label"
    assert first.contribution_type_evidence["taxonomy"] == labels.ISSUE_TAXONOMY_VERSION
    assert first.technologies == [{"slug": "django", "source": "title"}]
    assert first.difficulty == "beginner"


def test_analysis_of_unclassifiable_issue() -> None:
    result = analyze(IssueInput("Rename module", "", [], 0), THRESHOLDS)
    # The taxonomy version is recorded for an unknown type too (ISV-8).
    assert (result.contribution_type, result.contribution_type_evidence) == (
        "unknown",
        {"taxonomy": labels.ISSUE_TAXONOMY_VERSION},
    )
    assert result.difficulty == "unknown"
    assert result.labels == [] and result.technologies == []
