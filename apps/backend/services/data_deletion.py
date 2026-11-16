"""Deletion of GitHub-derived data (spec: data-controls; design D5).

One routine shared by "delete GitHub data", GitHub disconnect and account deletion, so the
three can never drift apart. It keeps the user and the GitHub connection; callers decide what
happens to those.
"""

from __future__ import annotations

import logging
from fnmatch import fnmatchcase
from typing import Any

from django.conf import settings
from django.core.cache import caches
from django.core.cache.backends.locmem import LocMemCache
from django.core.cache.backends.redis import RedisCache
from django.db import transaction
from django.db.models import Exists, F, OuterRef

from accounts.models import User
from developers.models import DeveloperProfile, InterestEvidence, SkillEvidence
from feedback.models import DismissedRepository, RecommendationFeedback, SavedRepository
from github.models import GitHubProfile
from jobs.models import SyncJob
from recommendations.models import Recommendation
from repositories.models import Repository, RepositoryCandidate, UserRepository

from . import jobs
from .locks import lock_developer

logger = logging.getLogger(__name__)


def _touched_repository_ids(user: User) -> set[int]:
    ids: set[int] = set()
    for queryset in (
        UserRepository.objects.filter(user=user),
        SkillEvidence.objects.filter(developer_skill__profile__user=user, repository__isnull=False),
        InterestEvidence.objects.filter(
            developer_interest__profile__user=user, repository__isnull=False
        ),
        RepositoryCandidate.objects.filter(developer__user=user),
        Recommendation.objects.filter(developer__user=user),
        SavedRepository.objects.filter(user=user),
        DismissedRepository.objects.filter(user=user),
    ):
        ids.update(queryset.values_list("repository_id", flat=True))
    return ids


def delete_github_data(user: User) -> dict[str, int]:
    """Cancel the user's jobs and delete everything derived from GitHub for them, including
    shared repositories nobody else references. Returns counts for the audit entry (no
    content). The user's cached GitHub responses are purged after commit; the generation bump
    makes a client built before the deletion drop any entry it writes afterwards."""
    # Account deletion deletes the user before this commits: ``user.pk`` is None by then.
    user_id = user.pk
    jobs.cancel_active_syncs(user)
    with transaction.atomic():
        # Profile first, as every recommendation and feedback write does (services/locks.py);
        # the cascade below would otherwise lock recommendations before the profile.
        lock_developer(user_id)
        repository_ids = _touched_repository_ids(user)
        # The developer profile cascades skills, interests, evidence, candidates, discoveries,
        # recommendations and reasons.
        _, cascaded = DeveloperProfile.objects.filter(user=user).delete()
        counts = {
            "developer_profiles": cascaded.get("developers.DeveloperProfile", 0),
            "skills": cascaded.get("developers.DeveloperSkill", 0),
            "candidates": cascaded.get("repositories.RepositoryCandidate", 0),
            "recommendations": cascaded.get("recommendations.Recommendation", 0),
            "github_profiles": GitHubProfile.objects.filter(user=user).delete()[0],
            "repository_links": UserRepository.objects.filter(user=user).delete()[0],
            "saved": SavedRepository.objects.filter(user=user).delete()[0],
            "dismissed": DismissedRepository.objects.filter(user=user).delete()[0],
            "feedback": RecommendationFeedback.objects.filter(user=user).delete()[0],
            "jobs": SyncJob.objects.filter(user=user).delete()[0],
        }
        counts["repositories"] = _delete_orphans(repository_ids)
        # The display name comes from the GitHub profile; the next sign-in sets it again.
        User.objects.filter(pk=user_id).update(
            display_name="", github_cache_generation=F("github_cache_generation") + 1
        )
        # In step with the row, so a later full save of ``user`` cannot undo the bump.
        user.refresh_from_db(fields=["display_name", "github_cache_generation"])
        transaction.on_commit(lambda: _purge(user_id), robust=True)
    return counts


def _purge(user_id: int) -> None:
    """Purge at commit; if that fails (a brief cache outage), queue retries. The generation
    covers entries written after the deletion, not the ones that were already there."""
    if not purge_user_github_cache(user_id):
        from github.tasks import purge_user_cache  # avoid import cycle

        purge_user_cache.apply_async((user_id,), countdown=settings.GITHUB_CACHE_BACKOFF_SECONDS)


def _delete_orphans(repository_ids: set[int]) -> int:
    """Delete the given shared repositories that no link, candidate, recommendation, save or
    dismissal references any more. Their analysis rows cascade."""
    if not repository_ids:
        return 0
    # Discovery search upserts (and so locks) a repository before recording its candidate: lock
    # first and decide in a later statement, which sees links those writers committed. GitHub ID
    # order, as every bulk repository lock, so the two never deadlock. A writer that only inserts
    # a row pointing at the repository takes no lock until its commit; it fails its deferred
    # foreign key there instead (rare, loud, nothing lost).
    list(
        Repository.objects.select_for_update()
        .filter(pk__in=repository_ids)
        .order_by("github_id")
        .values_list("pk", flat=True)
    )
    orphans = Repository.objects.filter(pk__in=repository_ids)
    for model in (
        UserRepository,
        RepositoryCandidate,
        Recommendation,
        SavedRepository,
        DismissedRepository,
    ):
        orphans = orphans.exclude(Exists(model.objects.filter(repository=OuterRef("pk"))))
    return orphans.delete()[1].get("repositories.Repository", 0)


def purge_user_github_cache(user_id: int) -> bool:
    """Delete the user-scope GitHub response cache (``github:etag:{pk}:*``). ``public``
    entries are shared and expire on their own. Failures are logged, never raised; returns
    False after one, so the caller can try again (entries expire within ``GITHUB_ETAG_TTL``)."""
    cache = caches["default"]
    try:
        # Written before 0.12.10 (one-hour TTL). Remove this delete in a later release.
        cache.delete(f"github:ratelimit:{user_id}")
        pattern = cache.make_key(f"github:etag:{user_id}:*")
        if isinstance(cache, RedisCache):
            client = cache._cache.get_client(write=True)
            keys = list(client.scan_iter(match=pattern, count=500))
            if keys:
                client.delete(*keys)
        elif isinstance(cache, LocMemCache):
            locmem: Any = cache  # private internals, not in the stubs
            with locmem._lock:
                for key in [k for k in locmem._cache if fnmatchcase(k, pattern)]:
                    locmem._delete(key)
        else:
            # A retry cannot help: report done.
            logger.warning("GitHub cache purge not supported for %s", type(cache).__name__)
    except Exception as exc:
        logger.warning("GitHub cache purge failed: %s", type(exc).__name__)
        return False
    return True
