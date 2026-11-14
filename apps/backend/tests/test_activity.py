from dataclasses import replace
from datetime import UTC, datetime, timedelta

from django.conf import settings

from services.matching.activity import (
    ActivityData,
    compute_activity,
    current,
    thresholds_version,
)

NOW = datetime(2026, 9, 29, tzinfo=UTC)
T = dict(settings.ACTIVITY_THRESHOLDS)

BASE = ActivityData(
    pushed_at=NOW - timedelta(days=3),
    stars=900,
    forks=40,
    open_issues=12,
    commits_90d=42,
    prs_opened_90d=12,
    prs_merged_90d=9,
    prs_sample_capped=False,
    contributors=57,
    latest_release_at=NOW - timedelta(days=20),
)


def label(**changes) -> str:
    return compute_activity(replace(BASE, **changes), NOW, T).activity_label


def test_signals_stored_as_given() -> None:
    signals = compute_activity(BASE, NOW, T)
    assert signals.days_since_push == 3
    assert (signals.commits_90d, signals.prs_opened_90d, signals.prs_merged_90d) == (42, 12, 9)
    assert signals.contributors == 57
    assert signals.latest_release_at == NOW - timedelta(days=20)
    assert signals.captured_at == NOW


def test_recently_active() -> None:
    assert label() == "recently_active"


def test_recently_active_through_merged_prs() -> None:
    assert label(commits_90d=2, prs_merged_90d=5) == "recently_active"


def test_moderately_active() -> None:
    assert label(pushed_at=NOW - timedelta(days=60), commits_90d=3) == "moderately_active"
    assert label(commits_90d=2, prs_merged_90d=0) == "moderately_active"


def test_low_activity_after_200_days() -> None:
    assert label(pushed_at=NOW - timedelta(days=200)) == "low_activity"


def test_low_activity_without_recent_work() -> None:
    assert label(pushed_at=NOW - timedelta(days=60), commits_90d=0, prs_merged_90d=0) == (
        "low_activity"
    )


def test_counts_unknown_uses_push_date_and_is_never_recent() -> None:
    assert label(commits_90d=None, prs_merged_90d=None) == "moderately_active"
    assert (
        label(pushed_at=NOW - timedelta(days=120), commits_90d=None, prs_merged_90d=None)
        == "low_activity"
    )


def test_one_count_unknown_is_never_zero() -> None:
    pushed = NOW - timedelta(days=5)
    assert label(pushed_at=pushed, commits_90d=None, prs_merged_90d=0) == "moderately_active"
    assert label(pushed_at=pushed, commits_90d=None, prs_merged_90d=9) == "recently_active"
    assert label(pushed_at=pushed, commits_90d=42, prs_merged_90d=None) == "recently_active"
    assert label(pushed_at=pushed, commits_90d=0, prs_merged_90d=None) == "moderately_active"
    old = NOW - timedelta(days=120)
    assert label(pushed_at=old, commits_90d=None, prs_merged_90d=9) == "low_activity"


def test_current_ages_the_push_since_capture() -> None:
    captured = NOW - timedelta(days=40)
    # Repository push time known: measured from it.
    assert current(0, captured, captured, 42, 9, NOW, T) == (40, "moderately_active")
    # Unknown on the row: the snapshot's days aged by the days since capture.
    assert current(2, captured, None, 42, 9, NOW, T) == (42, "moderately_active")
    # Part of a day since capture counts whole: never a push younger than it was (CR5-5).
    half = NOW - timedelta(days=7, hours=12)
    assert current(0, half, None, 42, 9, NOW, T)[0] == 8
    assert current(None, captured, None, 42, 9, NOW, T) == (None, "low_activity")
    stricter = {**T, "recent_commits": 50, "recent_merged_prs": 50}
    pushed = NOW - timedelta(days=3)
    assert current(3, NOW, pushed, 42, 9, NOW, stricter) == (3, "moderately_active")


def test_unknown_contributors_stay_unknown() -> None:
    assert compute_activity(replace(BASE, contributors=None), NOW, T).contributors is None


def test_threshold_change_relabels_and_changes_version() -> None:
    stricter = {**T, "recent_commits": 50, "recent_merged_prs": 50}
    before, after = compute_activity(BASE, NOW, T), compute_activity(BASE, NOW, stricter)
    assert (before.activity_label, after.activity_label) == ("recently_active", "moderately_active")
    assert before.thresholds_version != after.thresholds_version


def test_deterministic() -> None:
    assert compute_activity(BASE, NOW, T) == compute_activity(BASE, NOW, T)
    assert thresholds_version(T) == thresholds_version(dict(reversed(list(T.items()))))
