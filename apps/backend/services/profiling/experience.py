"""Approximate contribution experience (SRS-2 §17). An internal matching signal only: never
shown to the user or returned by the API.

Each signal that has data scores 0 (beginner), 1 (intermediate) or 2 (experienced) against
configurable ``[intermediate_from, experienced_from]`` thresholds; the level is the rounded
mean. With fewer than two signals the level is ``unknown``, so no single number (such as
repository count) can decide it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import timedelta
from typing import Any

from .inputs import ProfileInput

ACTIVE_WITHIN = timedelta(days=2 * 365)
MIN_SIGNALS = 2
# Every signal ``experience_signals`` can report; ``EXPERIENCE_THRESHOLDS`` needs one entry each.
SIGNALS = (
    "account_age_years",
    "active_repositories",
    "merged_external_prs",
    "contributed_repositories",
    "well_evidenced_skills",
)


def experience_signals(profile: ProfileInput, well_evidenced_skills: int) -> dict[str, float]:
    """Signal values that have data. Zero counts mean "no observable data", not "beginner"."""
    signals: dict[str, float] = {}
    if profile.account_created_at:
        age = (profile.now - profile.account_created_at).days / 365.25
        signals["account_age_years"] = round(max(age, 0.0), 2)
    counts = {
        "active_repositories": sum(
            1
            for r in profile.own_work
            if r.pushed_at and profile.now - r.pushed_at <= ACTIVE_WITHIN
        ),
        "merged_external_prs": sum(c.merged_pr_count for c in profile.contributions),
        "contributed_repositories": sum(
            1 for c in profile.contributions if c.merged_pr_count or c.push_count
        ),
        "well_evidenced_skills": well_evidenced_skills,
    }
    signals.update({name: value for name, value in counts.items() if value > 0})
    return signals


def _score(value: float, bounds: Sequence[float]) -> int:
    intermediate, experienced = bounds
    return 2 if value >= experienced else 1 if value >= intermediate else 0


def estimate_experience(
    signals: Mapping[str, float], thresholds: Mapping[str, Sequence[float]]
) -> tuple[str, dict[str, Any]]:
    scores = {name: _score(value, thresholds[name]) for name, value in signals.items()}
    audit: dict[str, Any] = {"signals": dict(signals), "scores": scores}
    if len(scores) < MIN_SIGNALS:
        return "unknown", audit
    mean = sum(scores.values()) / len(scores)
    audit["mean"] = round(mean, 3)
    if mean < 0.67:
        return "beginner", audit
    if mean < 1.34:
        return "intermediate", audit
    return "experienced", audit
