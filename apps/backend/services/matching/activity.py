"""Repository activity signals and label (FR-REPO-004, design D6).

Activity is described by observable, dated signals and a coarse label; it is never a verdict
on whether a repository is healthy or good. Pure: no database or HTTP.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

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
    if days_since_push is None:
        return ActivityLabel.LOW_ACTIVITY
    counts_unknown = commits is None and merged_prs is None
    commits_n, merged_n = commits or 0, merged_prs or 0
    if (
        not counts_unknown
        and days_since_push <= thresholds["recent_push_days"]
        and (
            commits_n >= thresholds["recent_commits"] or merged_n >= thresholds["recent_merged_prs"]
        )
    ):
        return ActivityLabel.RECENTLY_ACTIVE
    if days_since_push <= thresholds["moderate_push_days"] and (
        counts_unknown
        or commits_n >= thresholds["moderate_commits"]
        or merged_n >= thresholds["moderate_merged_prs"]
    ):
        return ActivityLabel.MODERATELY_ACTIVE
    return ActivityLabel.LOW_ACTIVITY


def compute_activity(
    data: ActivityData, now: datetime, thresholds: Mapping[str, int] | None = None
) -> ActivitySignals:
    thresholds = thresholds if thresholds is not None else default_thresholds()
    days = max((now - data.pushed_at).days, 0) if data.pushed_at else None
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
