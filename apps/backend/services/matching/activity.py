"""Repository activity signals and label (FR-REPO-004, design D6).

Activity is described by observable, dated signals and a coarse label; it is never a verdict
on whether a repository is healthy or good. Pure: no database or HTTP.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings

from repositories.models import ActivityLabel

WINDOW_DAYS = 90


@dataclass(frozen=True)
class ActivityData:
    """Raw fetch results. ``None`` means GitHub could not tell us (unknown, not zero)."""

    pushed_at: datetime | None
    stars: int
    forks: int
    open_issues: int
    commits_90d: int | None
    prs_opened_90d: int | None
    prs_merged_90d: int | None
    prs_sample_capped: bool
    contributors: int | None
    latest_release_at: datetime | None


@dataclass(frozen=True)
class ActivitySignals:
    captured_at: datetime
    stars: int
    forks: int
    open_issues: int
    days_since_push: int | None
    commits_90d: int | None
    prs_opened_90d: int | None
    prs_merged_90d: int | None
    prs_sample_capped: bool
    contributors: int | None
    latest_release_at: datetime | None
    activity_label: str
    thresholds_version: str


def default_thresholds() -> dict[str, int]:
    return dict(settings.ACTIVITY_THRESHOLDS)


def thresholds_version(thresholds: Mapping[str, int]) -> str:
    """Short, stable hash of the thresholds: traces a label to the config that produced it."""
    payload = json.dumps(dict(thresholds), sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()[:12]


def activity_label(
    days_since_push: int | None,
    commits: int | None,
    merged_prs: int | None,
    thresholds: Mapping[str, int],
) -> str:
    """An unknown count (None) is never 0: ``recently_active`` needs a known count meeting its
    threshold; ``moderately_active`` accepts an unknown count, as with both unknown."""
    if days_since_push is None:
        return ActivityLabel.LOW_ACTIVITY
    if days_since_push <= thresholds["recent_push_days"] and (
        _meets(commits, thresholds["recent_commits"])
        or _meets(merged_prs, thresholds["recent_merged_prs"])
    ):
        return ActivityLabel.RECENTLY_ACTIVE
    if days_since_push <= thresholds["moderate_push_days"] and (
        commits is None
        or merged_prs is None
        or _meets(commits, thresholds["moderate_commits"])
        or _meets(merged_prs, thresholds["moderate_merged_prs"])
    ):
        return ActivityLabel.MODERATELY_ACTIVE
    return ActivityLabel.LOW_ACTIVITY


def current(
    snapshot_days: int | None,
    captured_at: datetime,
    pushed_at: datetime | None,
    commits: int | None,
    merged_prs: int | None,
    now: datetime,
    thresholds: Mapping[str, int],
) -> tuple[int | None, str]:
    """Days since the last push measured at ``now`` and the label under ``thresholds``
    (change services-matching-review-fixes, D1). The repository's ``pushed_at`` when known;
    otherwise the snapshot's days aged by the days since its capture, rounded up."""
    if pushed_at is not None:
        days: int | None = _days_since(pushed_at, now)
    elif snapshot_days is not None:
        # The capture floored its push age, so the true age may be a day more: round the time
        # since capture up, never claiming a push younger than it was (CR5-5).
        days = snapshot_days + _whole_days_up(captured_at, now)
    else:
        days = None
    return days, activity_label(days, commits, merged_prs, thresholds)


def _meets(count: int | None, threshold: int) -> bool:
    return count is not None and count >= threshold


def _days_since(then: datetime, now: datetime) -> int:
    """Whole days from ``then`` to ``now``, never negative."""
    return max((now - then).days, 0)


def _whole_days_up(then: datetime, now: datetime) -> int:
    """Days from ``then`` to ``now`` with any part of a day counted whole, never negative."""
    return max(math.ceil((now - then) / timedelta(days=1)), 0)


def compute_activity(
    data: ActivityData, now: datetime, thresholds: Mapping[str, int] | None = None
) -> ActivitySignals:
    thresholds = thresholds if thresholds is not None else default_thresholds()
    days = _days_since(data.pushed_at, now) if data.pushed_at else None
    return ActivitySignals(
        captured_at=now,
        stars=data.stars,
        forks=data.forks,
        open_issues=data.open_issues,
        days_since_push=days,
        commits_90d=data.commits_90d,
        prs_opened_90d=data.prs_opened_90d,
        prs_merged_90d=data.prs_merged_90d,
        prs_sample_capped=data.prs_sample_capped,
        contributors=data.contributors,
        latest_release_at=data.latest_release_at,
        activity_label=activity_label(days, data.commits_90d, data.prs_merged_90d, thresholds),
        thresholds_version=thresholds_version(thresholds),
    )
