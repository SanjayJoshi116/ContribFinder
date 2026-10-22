"""Shared repository querysets."""

from __future__ import annotations

from django.db.models import Prefetch, QuerySet

from .models import RepositorySnapshot

# Newest snapshot first; ``pk`` breaks ties between snapshots captured at the same time. The
# snapshot index has the same order, so this is an index scan.
SNAPSHOT_NEWEST_FIRST = ("-captured_at", "-pk")


def latest_snapshot(prefix: str = "") -> Prefetch[str, QuerySet[RepositorySnapshot], str]:
    """Each repository's newest snapshot only, as ``latest_snapshots`` (empty or one item).
    ``prefix`` is the path to the repository, e.g. ``"repository__"``."""
    return Prefetch(
        f"{prefix}snapshots",
        queryset=RepositorySnapshot.objects.order_by(*SNAPSHOT_NEWEST_FIRST)[:1],
        to_attr="latest_snapshots",
    )
