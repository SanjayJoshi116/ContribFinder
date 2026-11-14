"""Shared repository querysets."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from django.db.models import (
    Case,
    CharField,
    DurationField,
    ExpressionWrapper,
    F,
    FloatField,
    Func,
    IntegerField,
    Prefetch,
    Q,
    QuerySet,
    Value,
    When,
)
from django.db.models.expressions import Combinable
from django.db.models.functions import Cast, Ceil, ExtractDay, Greatest

from .models import ActivityLabel, RepositorySnapshot

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


def with_current_activity(
    snapshots: QuerySet[RepositorySnapshot], now: datetime, thresholds: Mapping[str, int]
) -> QuerySet[RepositorySnapshot]:
    """Snapshots annotated with ``current_days`` and ``current_label``: the SQL form of
    ``services.matching.activity.current`` (push age measured at ``now`` from the repository's
    push time, else the snapshot's age rounded up; label under ``thresholds``), for lists that
    filter and page in the database. A test keeps the two in step."""
    since_push = ExpressionWrapper(Value(now) - F("repository__pushed_at"), DurationField())
    since_capture = ExpressionWrapper(Value(now) - F("captured_at"), DurationField())
    aged = F("days_since_push") + Ceil(_epoch(since_capture) / 86400.0)
    days = Case(
        When(repository__pushed_at__isnull=False, then=Greatest(ExtractDay(since_push), 0)),
        When(days_since_push__isnull=False, then=Greatest(Cast(aged, IntegerField()), 0)),
        default=None,
        output_field=IntegerField(),
    )

    def meets(field: str, key: str) -> Q:
        return Q(**{f"{field}__gte": thresholds[key]})  # NULL never meets

    recent = Q(current_days__lte=thresholds["recent_push_days"]) & (
        meets("commits_90d", "recent_commits") | meets("prs_merged_90d", "recent_merged_prs")
    )
    moderate = Q(current_days__lte=thresholds["moderate_push_days"]) & (
        Q(commits_90d__isnull=True)
        | Q(prs_merged_90d__isnull=True)
        | meets("commits_90d", "moderate_commits")
        | meets("prs_merged_90d", "moderate_merged_prs")
    )
    return snapshots.annotate(current_days=days).annotate(
        current_label=Case(
            When(current_days__isnull=True, then=Value(ActivityLabel.LOW_ACTIVITY)),
            When(recent, then=Value(ActivityLabel.RECENTLY_ACTIVE)),
            When(moderate, then=Value(ActivityLabel.MODERATELY_ACTIVE)),
            default=Value(ActivityLabel.LOW_ACTIVITY),
            output_field=CharField(),
        )
    )


def _epoch(interval: Combinable) -> Func:
    return Func(interval, template="EXTRACT(EPOCH FROM %(expressions)s)", output_field=FloatField())
