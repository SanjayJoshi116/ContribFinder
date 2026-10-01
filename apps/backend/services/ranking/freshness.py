"""Recommendation freshness (spec: recommendation-engine; design D8).

A developer's recommendations are stale when, since the last completed generation started,
their profile was re-analyzed, a repository in their pool changed lifecycle (analysis,
refresh, failure), or the active scoring configuration changed. A sweep coalesces the many
repository refreshes of a backlog batch into one regeneration per developer.
"""

from __future__ import annotations

from django.db.models import Exists, Max, OuterRef, Subquery

from developers.models import DeveloperProfile
from jobs.models import SyncJob
from recommendations.models import Recommendation, ScoringConfig
from services.jobs import RECOMMENDATIONS, start_recommendations


def due_profiles() -> list[DeveloperProfile]:
    last_generation = (
        SyncJob.objects.filter(
            user=OuterRef("user"),
            job_type=RECOMMENDATIONS,
            status=SyncJob.Status.COMPLETED,
        )
        .order_by("-started_at")
        .values("started_at")[:1]
    )
    active = ScoringConfig.objects.filter(is_active=True).values("pk")[:1]
    outdated_config = Recommendation.objects.filter(developer=OuterRef("pk")).exclude(
        scoring_config=Subquery(active)
    )
    profiles = (
        DeveloperProfile.objects.filter(candidates__isnull=False)
        .annotate(
            last_generation=Subquery(last_generation),
            pool_changed=Max("candidates__repository__lifecycle_changed_at"),
            outdated_config=Exists(outdated_config),
        )
        .select_related("user")
    )
    return [
        p
        for p in profiles
        if p.last_generation is None
        or p.outdated_config
        or p.analyzed_at > p.last_generation
        or (p.pool_changed is not None and p.pool_changed > p.last_generation)
    ]


def start_due_generations() -> int:
    """Start a generation for every due developer; an active one is reused, not duplicated."""
    started = 0
    for profile in due_profiles():
        _, created = start_recommendations(profile.user)
        started += created
    return started
