"""Recommendation freshness (spec: recommendation-engine; design D8).

A developer's recommendations are stale when, since the last completed generation started,
their profile was re-analyzed, a repository in their pool got new data or changed lifecycle
(analysis, refresh, failure; not a staleness mark), or the active scoring configuration
changed, or when they have recommendations but no candidates left. A sweep coalesces the
many repository refreshes of a backlog batch into one regeneration per developer. A
developer with an active generation is skipped, and one whose latest generation failed waits
``RECOMMENDATION_FAILED_RETRY_MINUTES`` before the next.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db.models import Exists, F, OuterRef, Subquery
from django.db.models.functions import Greatest
from django.utils import timezone

from developers.models import DeveloperProfile
from jobs.models import SyncJob
from recommendations.models import Recommendation, ScoringConfig
from repositories.models import Lifecycle, RepositoryCandidate
from services.jobs import RECOMMENDATIONS, start_recommendations
from services.repositories.staleness import PART_FIELDS


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
    candidates = RepositoryCandidate.objects.filter(developer=OuterRef("pk"))
    recommendations = Recommendation.objects.filter(developer=OuterRef("pk"))
    # A staleness mark or a refresh claim changes no stored data: a repository in one of those
    # states carries that time, so it is left out. Its completed refresh or failure counts.
    pool_changed = (
        candidates.exclude(repository__lifecycle__in=(Lifecycle.STALE, Lifecycle.REFRESHING))
        .order_by(F("repository__lifecycle_changed_at").desc(nulls_last=True))
        .values("repository__lifecycle_changed_at")[:1]
    )
    # When any pooled repository last got new data: a staleness mark hides an analysis's
    # lifecycle time, never its data times.
    data_changed = (
        candidates.annotate(
            fetched=Greatest(*(f"repository__{field}" for field in PART_FIELDS.values()))
        )
        .order_by(F("fetched").desc(nulls_last=True))
        .values("fetched")[:1]
    )
    # A failure that ended recently: wait before trying again (a failing setup would
    # otherwise be retried on every sweep).
    failed_recently = SyncJob.objects.filter(
        user=OuterRef("user"),
        job_type=RECOMMENDATIONS,
        status=SyncJob.Status.FAILED,
        completed_at__gte=timezone.now()
        - timedelta(minutes=settings.RECOMMENDATION_FAILED_RETRY_MINUTES),
    )
    profiles = (
        DeveloperProfile.objects.annotate(has_candidates=Exists(candidates))
        .filter(Exists(candidates) | Exists(recommendations))
        .annotate(
            last_generation=Subquery(last_generation),
            pool_changed=Subquery(pool_changed),
            data_changed=Subquery(data_changed),
            outdated_config=Exists(outdated_config),
        )
        .exclude(Exists(failed_recently))
        .select_related("user")
    )
    return [
        p
        for p in profiles
        if p.last_generation is None
        or p.outdated_config
        or p.analyzed_at > p.last_generation
        or any(t is not None and t > p.last_generation for t in (p.pool_changed, p.data_changed))
        or not p.has_candidates  # recommendations left from a pool that is now empty
    ]


def start_due_generations() -> int:
    """Start a generation for every due developer without an active one. A running one is
    left alone: it loads current inputs, and asking it to run again would repeat it."""
    started = 0
    for profile in due_profiles():
        _, created = start_recommendations(profile.user, rerun_if_running=False)
        started += created
    return started
