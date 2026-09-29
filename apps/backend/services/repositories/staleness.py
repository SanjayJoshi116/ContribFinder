"""Per-data-type freshness of repository data (SRS-2 §24, design D8). Pure."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta

from django.conf import settings

from repositories.models import Repository

PARTS = ("metadata", "readme", "community", "dependencies", "activity")


def part_timestamps(repo: Repository) -> dict[str, datetime | None]:
    return {
        "metadata": repo.synced_at,
        "readme": repo.readme_synced_at,
        "community": repo.community_synced_at,
        "dependencies": repo.dependencies_synced_at,
        "activity": repo.activity_synced_at,
    }


def stale_parts(
    repo: Repository, now: datetime, ages: Mapping[str, int] | None = None
) -> list[str]:
    """Data types that are missing or older than their configured age (hours), in ``PARTS``
    order. A repository that was never analyzed needs every part: its metadata may come from
    a search result, which carries no languages."""
    if repo.activity_synced_at is None:
        return list(PARTS)
    ages = ages if ages is not None else settings.REPO_STALE_AFTER
    stamps = part_timestamps(repo)
    return [
        part
        for part in PARTS
        if (stamp := stamps[part]) is None or stamp < now - timedelta(hours=ages[part])
    ]
