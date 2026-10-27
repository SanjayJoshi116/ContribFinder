"""When each area of a user's derived data last changed (data versions).

Read-only: built from times the writers already store, so no writer has to remember to bump a
version. The SPA compares two reads and refetches only the areas that differ.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.db.models import Max, Q

from accounts.models import User
from developers.models import DeveloperProfile
from feedback.models import SavedRepository
from jobs.models import SyncJob
from recommendations.models import Recommendation
from repositories.models import Repository
from services.jobs import RECOMMENDATIONS, SYNC
from services.repositories.staleness import PART_FIELDS


@dataclass(frozen=True)
class DataVersions:
    github: datetime | None
    profile: datetime | None
    recommendations: datetime | None


def versions(user: User) -> DataVersions:
    """Three reads: both job times in one aggregate, the profile, the repository times."""
    finished = SyncJob.objects.filter(user=user, completed_at__isnull=False).aggregate(
        # A failed sync may already have stored GitHub data, so it counts; a cancelled one (data
        # deletion, disconnect) does not. A failed generation stores nothing.
        sync=Max(
            "completed_at",
            filter=Q(job_type=SYNC, status__in=(SyncJob.Status.COMPLETED, SyncJob.Status.FAILED)),
        ),
        generation=Max(
            "completed_at",
            filter=Q(job_type=RECOMMENDATIONS, status=SyncJob.Status.COMPLETED),
        ),
    )
    profile = DeveloperProfile.objects.filter(user=user).values("id", "analyzed_at").first()
    return DataVersions(
        github=finished["sync"],
        profile=profile["analyzed_at"] if profile else None,
        recommendations=_latest(
            finished["generation"],
            _repository_data_time(user, profile["id"] if profile else None),
        ),
    )


def _repository_data_time(user: User, profile_id: int | None) -> datetime | None:
    """Newest stored data time of any repository the user has a recommendation or a saved
    entry for. Two ``id__in`` subqueries, not an OR across two joins (which multiplies rows)."""
    recommended = Recommendation.objects.filter(developer_id=profile_id).values("repository_id")
    saved = SavedRepository.objects.filter(user=user).values("repository_id")
    times = Repository.objects.filter(Q(id__in=recommended) | Q(id__in=saved)).aggregate(
        **{part: Max(field) for part, field in PART_FIELDS.items()}
    )
    return _latest(*times.values())


def _latest(*times: datetime | None) -> datetime | None:
    return max((t for t in times if t is not None), default=None)
