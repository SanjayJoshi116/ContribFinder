from dataclasses import replace
from datetime import UTC, datetime, timedelta

from django.conf import settings

from services.matching.activity import ActivityData, compute_activity, thresholds_version

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
