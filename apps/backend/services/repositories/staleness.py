"""Per-data-type freshness of repository data (SRS-2 §24, design D8). Pure."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta

from django.conf import settings

from repositories.models import Repository

# Each data type and the Repository field set when it is fetched (repositories/analysis.py).
PART_FIELDS = {
    "metadata": "synced_at",
    "readme": "readme_synced_at",
    "community": "community_synced_at",
    "dependencies": "dependencies_synced_at",
    "activity": "activity_synced_at",
    "issues": "issues_synced_at",
}
PARTS = tuple(PART_FIELDS)
# A repository that gave up its name to another GitHub ID is stored as ``{name}~{github_id}``
# (lifecycle.release_name). GitHub names never contain ``~``, so this cannot collide.
RELEASED_MARK = "~"


def is_released_name(full_name: str) -> bool:
    return RELEASED_MARK in full_name


def part_timestamps(repo: Repository) -> dict[str, datetime | None]:
    return {part: getattr(repo, field) for part, field in PART_FIELDS.items()}


def stale_parts(
    repo: Repository, now: datetime, ages: Mapping[str, int] | None = None
) -> list[str]:
    """Data types that are missing or older than their configured age (hours), in ``PARTS``
    order. A repository that was never analyzed needs every part: its metadata may come from
    a search result, which carries no languages. An analyzed repository whose issues were
    never fetched (analyzed before issues existed) has them stale. A repository that gave up
    its name has stale metadata: only a lookup by GitHub ID finds its current name."""
    if repo.activity_synced_at is None:
        return list(PARTS)
    ages = ages if ages is not None else settings.REPO_STALE_AFTER
    stamps = part_timestamps(repo)
    released = is_released_name(repo.full_name)
    return [
        part
        for part in PARTS
        if (part == "metadata" and released)
        or (stamp := stamps[part]) is None
        or stamp < now - timedelta(hours=ages[part])
    ]
