"""Feedback report (change feedback-report): ``build`` on plain events, then the command."""

import itertools
import json
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from feedback.models import RecommendationFeedback
from services.evaluation import feedback_report
from services.evaluation.feedback_report import Event, build

from .factories import UserFactory

# Every helper event concerns its own repository, so each decisive one is its own outcome.
_repositories = itertools.count(1)


def repo() -> str:
    return f"owner/repo-{next(_repositories)}"


def events(version: str, rank: int, action: str, n: int, *, user: int = 1) -> list[Event]:
    return [Event(user, action, version, rank, repository=repo()) for _ in range(n)]


def test_shares_per_configuration_and_bucket() -> None:
    found = [
        *[Event(u, "saved", "v2-deterministic", 3, repository=repo()) for u in range(12)],
        *[Event(u, "dismissed", "v2-deterministic", 1, repository=repo()) for u in range(8)],
    ]
    report = build(found)

    (config,) = report.configs
    (row,) = config.buckets
    assert config.version == "v2-deterministic"
    assert row.bucket == (1, 5)
    assert (row.counts["saved"], row.counts["dismissed"], row.users) == (12, 8, 12)
    assert row.share == pytest.approx(0.60)
    assert config.raw_share == pytest.approx(0.60)


def test_position_adjustment() -> None:
    found = [
        *events("a", 1, "saved", 32),
        *events("a", 1, "dismissed", 8),
        *events("a", 7, "opened_repository", 4),
        *events("a", 7, "dismissed", 6),
        *events("b", 2, "saved", 8),
        *events("b", 2, "dismissed", 2),
        *events("b", 9, "opened_issue", 16),
        *events("b", 9, "dismissed", 24),
    ]
    a, b = build(found).configs

    assert a.raw_share == pytest.approx(0.72) and b.raw_share == pytest.approx(0.48)
    assert a.adjusted_share == pytest.approx(0.60) and b.adjusted_share == pytest.approx(0.60)
    assert a.coverage == pytest.approx(1.0) and b.coverage == pytest.approx(1.0)


def test_partial_coverage() -> None:
    found = [
        *events("a", 1, "saved", 30),
        *events("a", 1, "dismissed", 20),  # a: a share at ranks 1-5 only, 50 of 100 decisive
        *events("a", 7, "saved", 2),  # below the minimum
        *events("b", 8, "saved", 24),
        *events("b", 8, "dismissed", 24),
    ]
    a, b = build(found).configs
    assert a.adjusted_share == pytest.approx(0.60) and a.coverage == pytest.approx(0.50)
    assert b.coverage == pytest.approx(0.50)  # ranks 6-10: 2 of a plus 48 of b


def test_no_adjusted_share_has_no_coverage() -> None:
    (config,) = build(events("a", 1, "saved", 3)).configs
    assert config.adjusted_share is None and config.coverage is None


# --- outcomes, not events (services-evaluation-review-fixes, EVL-3) ---------------------------


def test_repeated_and_undone_actions() -> None:
    v2 = "v2-deterministic"
    found = [
        *[Event(1, "opened_repository", v2, 2, repository="o/x") for _ in range(6)],
        Event(1, "dismissed", v2, 3, repository="o/y"),
        Event(1, "dismissed", v2, 4, repository="o/z"),
        Event(1, "saved", v2, 5, repository="o/w"),
        Event(1, "unsaved", v2, 5, repository="o/w"),
    ]
    (config,) = build(found, minimum=1).configs
    (row,) = config.buckets
    counts = {k: v for k, v in row.counts.items() if v}
    assert counts == {"opened_repository": 6, "dismissed": 2, "saved": 1, "unsaved": 1}
    assert (row.positive, row.decisive) == (1, 3)
    assert row.share == pytest.approx(1 / 3) and config.raw_share == pytest.approx(1 / 3)


def test_save_then_unsave_leaves_no_outcome() -> None:
    found = [
        Event(1, "saved", "a", 1, repository="o/w"),
        Event(1, "unsaved", "a", 1, repository="o/w"),
    ]
    (row,) = build(found, minimum=1).configs[0].buckets
    assert (row.positive, row.decisive, row.share) == (0, 0, None)


def test_undo_without_a_rank_still_undoes() -> None:
    found = [
        Event(1, "saved", "a", 1, repository="o/w"),
        Event(1, "unsaved", "a", None, repository="o/w"),
    ]
    report = build(found, minimum=1)
    assert report.configs[0].buckets[0].decisive == 0
    assert report.unattributed == {"unsaved": 1}


def test_dismiss_undismiss_then_open_is_positive() -> None:
    found = [
        Event(1, "dismissed", "a", 1, repository="o/w"),
        Event(1, "undismissed", "a", 1, repository="o/w"),
        Event(1, "opened_repository", "a", 1, repository="o/w"),
    ]
    (row,) = build(found, minimum=1).configs[0].buckets
    assert (row.positive, row.decisive, row.share) == (1, 1, 1.0)


def test_outcome_falls_in_the_bucket_and_label_of_its_event() -> None:
    found = [
        Event(1, "saved", "a", 3, "strong", repository="o/w"),
        Event(1, "dismissed", "a", 8, "good", repository="o/w"),
    ]
    (config,) = build(found, minimum=1).configs
    top, lower = config.buckets
    assert (top.bucket, top.decisive) == ((1, 5), 0)
    assert (lower.bucket, lower.positive, lower.decisive) == ((6, 10), 0, 1)
    strong, good = config.labels
    assert (strong.decisive, good.decisive) == (0, 1)


def test_outcomes_are_per_user_repository_and_version() -> None:
    found = [
        Event(1, "saved", "a", 1, repository="o/w"),
        Event(2, "dismissed", "a", 1, repository="o/w"),
        Event(1, "dismissed", "b", 1, repository="o/w"),
    ]
    a, b = build(found, minimum=1).configs
    assert (a.buckets[0].positive, a.buckets[0].decisive) == (1, 2)
    assert (b.buckets[0].positive, b.buckets[0].decisive) == (0, 1)


# --- stored values no longer offered (EVL-7) --------------------------------------------------


def test_reason_no_longer_offered_is_listed_after_the_current_ones() -> None:
    found = [
        *dismissed("a", "inactive", 1),
        *dismissed("a", "not_interested", 2),
        *dismissed("a", "", 1),
    ]
    (config,) = build(found).configs
    assert list(config.dismiss_reasons.items()) == [
        ("inactive", 1),
        ("not_interested", 2),
        ("none", 1),
    ]


def test_label_no_longer_offered_gets_a_row_outside_calibration() -> None:
    found = [*labeled("strong", 7, 3), *labeled("good", 5, 5), *labeled("weak", 10, 0)]
    (config,) = build(found).configs
    assert [row.label for row in config.labels] == ["strong", "good", "weak"]
    assert config.labels[2].share == 1.0
    assert config.calibration.verdict == "ordered"


def test_group_below_the_minimum() -> None:
    found = [
        *events("a", 1, "saved", 16),
        *events("a", 1, "dismissed", 4),
        *events("a", 12, "saved", 1),
        *events("a", 12, "dismissed", 3),  # 4 decisive actions
    ]
    (config,) = build(found).configs
    _, low = config.buckets

    assert low.counts["saved"] == 1 and low.share is None
    assert config.adjusted_share == pytest.approx(0.80)  # the 1-5 bucket alone


def test_no_bucket_at_the_minimum() -> None:
    (config,) = build(events("a", 1, "saved", 3), minimum=10).configs
    assert config.raw_share is None and config.adjusted_share is None


def test_neutral_actions_are_counted_but_outside_shares() -> None:
    found = [
        *events("a", 1, "saved", 10),
        *events("a", 1, "viewed", 50),
        *events("a", 1, "unsaved", 5),
        *events("a", 1, "undismissed", 2),
    ]
    (row,) = build(found).configs[0].buckets
    assert (row.counts["viewed"], row.counts["unsaved"], row.counts["undismissed"]) == (50, 5, 2)
    assert row.share == 1.0


def test_events_without_a_snapshot_are_unattributed() -> None:
    found = [
        *events("a", 1, "saved", 10),
        Event(1, "dismissed", "", None),
        Event(2, "saved", "a", None),
    ]
    report = build(found)
    assert report.unattributed == {"saved": 1, "dismissed": 1}
    assert report.configs[0].buckets[0].counts["dismissed"] == 0
    assert report.configs[0].raw_share == 1.0


@pytest.mark.parametrize("rank", [21, 300])
def test_open_ended_bucket(rank: int) -> None:
    (row,) = build(events("a", rank, "saved", 1)).configs[0].buckets
    assert row.bucket == (21, None)


def test_minimum_must_be_positive() -> None:
    with pytest.raises(ValueError):
        build([], minimum=0)


# --- match labels (feedback-report-labels) ---------------------------------------------------


def labeled(label: str, positive: int, dismissed: int, *, rank: int = 1) -> list[Event]:
    return [
        *[Event(1, "saved", "a", rank, label, repository=repo()) for _ in range(positive)],
        *[Event(2, "dismissed", "a", rank, label, repository=repo()) for _ in range(dismissed)],
    ]


def test_labels_in_order() -> None:
    found = [*labeled("strong", 7, 3), *labeled("good", 11, 9), *labeled("partial", 4, 6)]
    (config,) = build(found).configs

    assert [row.label for row in config.labels] == ["strong", "good", "partial"]
    assert [row.share for row in config.labels] == pytest.approx([0.70, 0.55, 0.40])
    assert config.labels[0].users == 2
    assert config.calibration.verdict == "ordered"


@pytest.mark.parametrize(
    ("found", "higher", "lower"),
    [
        ([*labeled("strong", 9, 11), *labeled("good", 6, 4)], "strong", "good"),
        ([*labeled("strong", 6, 4), *labeled("partial", 7, 3)], "strong", "partial"),
        ([*labeled("good", 4, 6), *labeled("partial", 6, 4)], "good", "partial"),
    ],
)
def test_labels_out_of_order(found, higher, lower) -> None:
    calibration = build(found).configs[0].calibration
    assert (calibration.verdict, calibration.higher, calibration.lower) == (
        "not ordered",
        higher,
        lower,
    )


def test_tied_labels_are_ordered() -> None:
    (config,) = build([*labeled("strong", 5, 5), *labeled("good", 5, 5)]).configs
    assert config.calibration.verdict == "ordered"


def test_one_label_with_a_share_is_not_enough() -> None:
    (config,) = build([*labeled("strong", 8, 2), *labeled("good", 1, 1)]).configs
    assert config.labels[1].share is None
    assert config.calibration.verdict == "not enough data"


def test_unlabeled_events_stay_out_of_label_rows_only() -> None:
    found = [*labeled("strong", 6, 4), *events("a", 1, "saved", 10)]  # events() has no label
    (config,) = build(found).configs

    (strong,) = config.labels
    assert strong.counts["saved"] == 6
    assert config.buckets[0].counts["saved"] == 16


def test_labels_leave_bucket_shares_unchanged() -> None:
    plain = [*events("a", 1, "saved", 12), *events("a", 8, "dismissed", 10)]
    with_labels = [e._replace(match_label="good") for e in plain]
    before, after = build(plain).configs[0], build(with_labels).configs[0]
    assert (before.buckets, before.raw_share, before.adjusted_share) == (
        after.buckets,
        after.raw_share,
        after.adjusted_share,
    )


def dismissed(version: str, reason: str, n: int, *, rank: int = 2) -> list[Event]:
    return [e._replace(dismiss_reason=reason) for e in events(version, rank, "dismissed", n)]


def test_dismiss_reasons_per_configuration() -> None:
    saved = events("v2-deterministic", 1, "saved", 12)
    with_reasons = [
        *saved,
        *dismissed("v2-deterministic", "inactive", 6),
        *dismissed("v2-deterministic", "not_my_stack", 3),
        *dismissed("v2-deterministic", "", 4, rank=8),
    ]
    plain = [e._replace(dismiss_reason="") for e in with_reasons]
    before, after = build(plain).configs[0], build(with_reasons).configs[0]

    assert after.dismiss_reasons == {"inactive": 6, "not_my_stack": 3, "none": 4}
    assert before.dismiss_reasons == {"none": 13}
    assert (after.buckets, after.raw_share, after.adjusted_share) == (
        before.buckets,
        before.raw_share,
        before.adjusted_share,
    )


def test_unattributed_dismissals_count_for_no_configuration() -> None:
    found = [
        *events("v2-deterministic", 1, "saved", 2),
        Event(1, "dismissed", "", None, dismiss_reason="too_big"),
        Event(1, "dismissed", "v2-deterministic", None, dismiss_reason="too_big"),
    ]
    report = build(found)

    assert report.configs[0].dismiss_reasons == {}
    assert report.unattributed == {"dismissed": 2}
    assert report.unattributed_dismiss_reasons == {"too_big": 2}


def test_rank_zero_is_unattributed() -> None:
    report = build([*events("a", 1, "saved", 10), *events("a", 0, "dismissed", 3)])
    (config,) = report.configs
    assert [row.bucket for row in config.buckets] == [(1, 5)]
    assert config.buckets[0].counts["dismissed"] == 0
    assert report.unattributed == {"dismissed": 3}


# --- command (group 2) ---------------------------------------------------------------------


def stored(
    user,
    version: str,
    rank: int | None,
    action: str,
    n: int = 1,
    *,
    label: str = "",
    reason: str = "",
    repository: str = "",
) -> None:
    """``n`` events, each on its own repository unless ``repository`` is given."""
    for _ in range(n):
        RecommendationFeedback.objects.create(
            user=user,
            repository_full_name=repository or f"secret-owner/secret-repo-{next(_repositories)}",
            action=action,
            config_version=version,
            rank=rank,
            match_label=label,
            dismiss_reason=reason,
        )


def run(*args: str) -> str:
    out = StringIO()
    call_command("feedback_report", *args, stdout=out)
    return out.getvalue()


@pytest.mark.django_db
def test_command_prints_label_calibration() -> None:
    user = UserFactory()
    for label, saved, dismissed in (("strong", 9, 11), ("good", 6, 4)):
        stored(user, "v2-deterministic", 1, "saved", saved, label=label)
        stored(user, "v2-deterministic", 1, "dismissed", dismissed, label=label)

    output = run()

    assert "  strong " in output and "  good " in output
    assert "calibration: not ordered (strong below good)" in output
    assert "not adjusted for rank" in output


@pytest.mark.django_db
def test_command_prints_dismiss_reasons() -> None:
    user = UserFactory()
    stored(user, "v2-deterministic", 1, "dismissed", 6, reason="inactive")
    stored(user, "v2-deterministic", 1, "dismissed", 3, reason="not_my_stack")
    stored(user, "v2-deterministic", 1, "dismissed", 4)
    stored(user, "v1-deterministic", 1, "saved", 2)

    output = run()

    assert output.count("dismiss reasons:") == 1
    assert "dismiss reasons: inactive 6, not_my_stack 3, none 4" in output

    stored(user, "", None, "dismissed", 2, reason="too_big")
    output = run()
    assert "Without a recommendation snapshot (in no share): dismissed 2" in output
    assert "  dismiss reasons: too_big 2" in output


@pytest.mark.django_db
def test_command_prints_shares_per_configuration(tmp_path) -> None:
    one, two = UserFactory(), UserFactory()
    stored(one, "v2-deterministic", 2, "saved", 6)
    stored(two, "v2-deterministic", 4, "saved", 6)
    stored(two, "v2-deterministic", 1, "dismissed", 8)
    stored(one, "v1-deterministic", 15, "opened_repository", 3)
    stored(one, "", None, "viewed")
    before = RecommendationFeedback.objects.count()

    output = run()

    assert "v1-deterministic" in output and "v2-deterministic" in output
    assert "position-adjusted 0.6000" in output
    assert "Without a recommendation snapshot (in no share): viewed 1" in output
    assert "not of recommendations shown" in output
    assert RecommendationFeedback.objects.count() == before


@pytest.mark.django_db
def test_command_filters_by_window_and_version() -> None:
    user = UserFactory()
    stored(user, "v1-deterministic", 1, "saved", 10)
    stored(user, "v2-deterministic", 1, "saved", 10)
    RecommendationFeedback.objects.filter(config_version="v1-deterministic").update(
        created_at=timezone.now() - timedelta(days=40)
    )

    assert "v1-deterministic" not in run("--since", "30")
    only = run("--config", "v1-deterministic")
    assert "v1-deterministic" in only and "v2-deterministic" not in only
    assert "No feedback events." in run("--config", "v9-missing")


@pytest.mark.django_db
@pytest.mark.parametrize("args", [["--minimum", "0"], ["--since", "0"]])
def test_command_rejects_bad_options(args) -> None:
    with pytest.raises(CommandError):
        run(*args)


@pytest.mark.django_db
def test_json_report_is_aggregates_only(tmp_path) -> None:
    user = UserFactory()
    stored(user, "v2-deterministic", 3, "saved", 10)
    stored(user, "v2-deterministic", 25, "opened_issue", 2)
    stored(user, "v2-deterministic", 4, "dismissed", 2, reason="too_big")
    out = tmp_path / "reports" / "feedback.json"

    run("--json", str(out))

    raw = out.read_text(encoding="utf-8")
    report = json.loads(raw)
    assert set(report) == {
        "since_days",
        "minimum",
        "configs",
        "unattributed",
        "unattributed_dismiss_reasons",
    }
    (config,) = report["configs"]
    assert set(config) == {
        "version",
        "raw_share",
        "adjusted_share",
        "coverage",
        "buckets",
        "labels",
        "calibration",
        "dismiss_reasons",
    }
    assert config["dismiss_reasons"] == {"too_big": 2}
    assert config["calibration"] == {"verdict": "not enough data", "higher": None, "lower": None}
    assert [b["ranks"] for b in config["buckets"]] == ["1-5", "21+"]
    assert set(config["buckets"][0]) == {
        "ranks",
        "counts",
        "users",
        "positive",
        "decisive",
        "share",
    }
    assert "secret" not in raw and user.username not in raw
    identifying = {"user", "user_id", "repository", "repository_full_name", "recommendation"}
    assert not keys(report) & (identifying | {"issue", "issue_number"})


def keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in keys(v)}
    return set()


@pytest.mark.django_db
def test_command_reads_undo_events_in_order() -> None:
    user = UserFactory()
    for action in ("saved", "unsaved", "dismissed", "undismissed", "opened_repository"):
        stored(user, "v2-deterministic", 1, action, repository="owner/one")
    (config,) = feedback_report.build(feedback_report.load(None), minimum=1).configs
    (row,) = config.buckets
    assert (row.positive, row.decisive) == (1, 1)
    assert "position-adjusted 1.0000 (coverage 1.0000)" in run("--minimum", "1")
