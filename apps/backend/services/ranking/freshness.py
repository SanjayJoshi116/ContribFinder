"""Recommendation freshness (spec: recommendation-engine; design D8).

A developer's recommendations are stale when, since the last completed generation started,
their profile was re-analyzed, a repository in their pool got new data or changed lifecycle
(analysis, refresh, failure; not a staleness mark), or the active scoring configuration
changed (also when the last generation, run under another configuration, stored nothing),
or when they have recommendations but no candidates left. A sweep coalesces the many
repository refreshes of a backlog batch into one regeneration per developer. A developer with
an active generation is skipped, and one whose latest finished generation failed waits
``RECOMMENDATION_FAILED_RETRY_MINUTES`` before the next.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Exists, F, OuterRef, Q, Subquery
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Greatest
from django.utils import timezone

from developers.models import DeveloperProfile
from jobs.models import SyncJob
from recommendations.models import Recommendation, ScoringConfig
from repositories.models import Lifecycle, RepositoryCandidate
from services.jobs import RECOMMENDATIONS, start_recommendations
from services.repositories.staleness import PART_FIELDS

logger = logging.getLogger(__name__)


def due_profiles() -> list[DeveloperProfile]:
    completed = SyncJob.objects.filter(
        user=OuterRef("user"),
        job_type=RECOMMENDATIONS,
        status=SyncJob.Status.COMPLETED,
    ).order_by("-started_at")
    last_generation = completed.values("started_at")[:1]
    # The configuration the last completed generation ran under (NULL for a job from before
    # it was recorded): a change makes the developer due even if that run stored nothing.
    last_config = completed.annotate(config=KeyTextTransform("config_version", "metadata")).values(
        "config"
    )[:1]
    active = ScoringConfig.objects.filter(is_active=True).values("pk")[:1]
    active_version = ScoringConfig.objects.filter(is_active=True).values("version")[:1]
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
    # The latest finished generation failed recently: wait before trying again (a failing
    # setup would otherwise be retried on every sweep). A later success ends the wait.
    latest_finished = (
        SyncJob.objects.filter(
            user=OuterRef(OuterRef("user")),
            job_type=RECOMMENDATIONS,
            status__in=(SyncJob.Status.COMPLETED, SyncJob.Status.FAILED),
        )
        .order_by(F("completed_at").desc(nulls_last=True))
        .values("pk")[:1]
    )
    failed_recently = SyncJob.objects.filter(
        pk=Subquery(latest_finished),
        status=SyncJob.Status.FAILED,
        completed_at__gte=timezone.now()
        - timedelta(minutes=settings.RECOMMENDATION_FAILED_RETRY_MINUTES),
    )
    profiles = (
        DeveloperProfile.objects.filter(Exists(candidates) | Exists(recommendations))
        # Aliases, not annotations: used only here, each correlated subquery runs once per
        # profile. GREATEST ignores NULLs (no pool or data time); analyzed_at is never NULL.
        .alias(
            last_generation=Subquery(last_generation),
            last_config=Subquery(last_config),
            changed=Greatest(F("analyzed_at"), Subquery(pool_changed), Subquery(data_changed)),
        )
        .exclude(Exists(failed_recently))
        .filter(
            Q(last_generation__isnull=True)
            | Q(changed__gt=F("last_generation"))
            | Exists(outdated_config)
            | (Q(last_config__isnull=False) & ~Q(last_config=Subquery(active_version)))
            | ~Exists(candidates)  # recommendations left from a pool that is now empty
        )
        .select_related("user")
    )
    return list(profiles)


def start_due_generations() -> int:
    """Start a generation for every due developer without an active one. A running one is
    left alone: it loads current inputs, and asking it to run again would repeat it."""
    started = 0
    for profile in due_profiles():
        try:
            _, created = start_recommendations(profile.user, rerun_if_running=False)
        except Exception:
            # One developer's job that cannot be queued (a broker error) must not stop the
            # sweep for the others; a job left PENDING is re-sent by job recovery.
            logger.exception("Could not start the generation for user %s", profile.user_id)
            continue
        started += created
    return started
