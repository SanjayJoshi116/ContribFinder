"""Candidate repository analysis (FR-REPO-003, design D5).

Fetches the requested data types of one repository, then writes them in one transaction and
walks the lifecycle. Repository data is shared: callers pick only the stale parts, so a fresh
repository is never fetched again for another developer.

Errors: a permanent GitHub error for the repository itself (404, 403, 451) marks it FAILED
and is not raised, so a discovery run continues with the next repository. Anything else (rate
limit, transient failure, revoked credentials, cancellation) restores the previous state and
is re-raised for the caller's retry policy. A missing README, community file or label is data.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from repositories.models import Lifecycle, Repository, RepositoryReadme, RepositorySnapshot
from services.github.client import CommunityProfile, GitHubClient, GitHubRepo, PullSample
from services.github.errors import (
    GitHubForbidden,
    GitHubNotFound,
    GitHubUnavailableForLegalReasons,
)
from services.github.storage import (
    read_manifests,
    replace_dependencies,
    replace_languages,
    replace_topics,
    upsert_repository,
)
from services.matching.activity import WINDOW_DAYS, ActivityData, compute_activity

from . import lifecycle
from .staleness import PARTS, stale_parts

logger = logging.getLogger(__name__)

PERMANENT_ERRORS = (GitHubNotFound, GitHubUnavailableForLegalReasons, GitHubForbidden)
ERROR_CODES: dict[type[Exception], str] = {
    GitHubNotFound: "not_found",
    GitHubUnavailableForLegalReasons: "unavailable",
    GitHubForbidden: "forbidden",
}
GOOD_FIRST_ISSUE = "good first issue"
HELP_WANTED = "help wanted"


class Outcome(StrEnum):
    ANALYZED = "analyzed"
    FAILED = "failed"
    SKIPPED = "skipped"  # another analysis holds the repository


@dataclass
class _Fetched:
    metadata: GitHubRepo | None = None
    languages: dict[str, int] | None = None
    readme: str | None = None
    readme_fetched: bool = False
    community: CommunityProfile | None = None
    labels: list[str] | None = None
    dependencies: dict[tuple[str, str], str] | None = None
    activity: ActivityData | None = None


def normalize_label(name: str) -> str:
    return re.sub(r"[\s_-]+", " ", name.lower()).strip()


class RepositoryAnalysisService:
    def __init__(
        self,
        client: GitHubClient,
        *,
        check_cancelled: Callable[[], None] | None = None,
        now: datetime | None = None,
    ) -> None:
        self.client = client
        self._check_cancelled = check_cancelled or (lambda: None)
        self._now = now

    def run(self, repo_id: int, parts: Iterable[str] | None = None) -> Outcome:
        """Claim the repository and analyze ``parts`` (default: its stale parts)."""
        now = self._now or timezone.now()
        repo = lifecycle.claim(repo_id)
        if repo is None:
            return Outcome.SKIPPED
        if parts is not None:
            wanted = list(parts)
        elif repo.previous_lifecycle == Lifecycle.FAILED:
            wanted = list(PARTS)  # a retry must re-check that the repository exists
        else:
            wanted = stale_parts(repo, now)
        try:
            fetched = self._fetch(repo, wanted, now)
        except PERMANENT_ERRORS as exc:
            code = ERROR_CODES[type(exc)]
            logger.info("Repository %s unavailable: %s", repo.full_name, code)
            lifecycle.fail(repo.pk, code)
            return Outcome.FAILED
        except BaseException:
            lifecycle.release(repo.pk)
            raise
        try:
            with transaction.atomic():
                self._store(repo, fetched, now)
                lifecycle.complete(repo, now=now)
        except BaseException:
            lifecycle.release(repo.pk)
            raise
        return Outcome.ANALYZED

    # --- fetching (no writes) --------------------------------------------------------------

    def _fetch(self, repo: Repository, parts: list[str], now: datetime) -> _Fetched:
        c, name, out = self.client, repo.full_name, _Fetched()
        if "metadata" in parts:
            self._check_cancelled()
            out.metadata = c.get_repository(name)
            name = out.metadata.full_name  # follows renames
            out.languages = c.get_languages(name)
        if "readme" in parts:
            self._check_cancelled()
            out.readme, out.readme_fetched = c.get_readme(name), True
        if "community" in parts:
            self._check_cancelled()
            out.community = c.get_community_profile(name)
            out.labels = c.list_label_names(name)
        if "dependencies" in parts:
            self._check_cancelled()
            out.dependencies = read_manifests(c, name)
        if "activity" in parts:
            self._check_cancelled()
            since = now - timedelta(days=WINDOW_DAYS)
            commits = c.count_commits_since(name, since)
            pulls: PullSample = c.recent_pull_requests(name, since)
            contributors = c.count_contributors(name)
            release = c.get_latest_release_date(name)
            meta = out.metadata
            out.activity = ActivityData(
                pushed_at=meta.pushed_at if meta else repo.pushed_at,
                stars=meta.stars if meta else repo.stars,
                forks=meta.forks if meta else repo.forks,
                open_issues=meta.open_issues if meta else repo.open_issues,
                commits_90d=commits,
                prs_opened_90d=pulls.opened,
                prs_merged_90d=pulls.merged,
                prs_sample_capped=pulls.capped,
                contributors=contributors,
                latest_release_at=release,
            )
        return out

    # --- storing (one transaction) ---------------------------------------------------------

    def _store(self, repo: Repository, f: _Fetched, now: datetime) -> None:
        fields: list[str] = []
        if f.metadata is not None:
            stored = upsert_repository(f.metadata, now)
            if stored.pk != repo.pk:  # pragma: no cover - github_id is stable per repository
                raise RuntimeError("Repository identity changed during analysis")
            repo.refresh_from_db()
            replace_languages(repo, f.languages or {})
            replace_topics(repo.pk, f.metadata.topics)
        if f.readme_fetched:
            self._store_readme(repo, f.readme, now)
            repo.readme_synced_at = now
            fields.append("readme_synced_at")
        if f.community is not None:
            labels = {normalize_label(label) for label in f.labels or []}
            repo.has_contributing = f.community.has_contributing
            repo.has_code_of_conduct = f.community.has_code_of_conduct
            repo.has_issue_templates = f.community.has_issue_template
            repo.has_pull_request_template = f.community.has_pull_request_template
            repo.has_good_first_issue_label = GOOD_FIRST_ISSUE in labels
            repo.has_help_wanted_label = HELP_WANTED in labels
            repo.community_synced_at = now
            fields += [
                "has_contributing",
                "has_code_of_conduct",
                "has_issue_templates",
                "has_pull_request_template",
                "has_good_first_issue_label",
                "has_help_wanted_label",
                "community_synced_at",
            ]
        if f.dependencies is not None:
            replace_dependencies(repo, f.dependencies)
            repo.dependencies_synced_at = now
            fields.append("dependencies_synced_at")
        if f.activity is not None:
            self._store_snapshot(repo, f.activity, now)
            repo.activity_synced_at = now
            fields.append("activity_synced_at")
        if fields:
            repo.save(update_fields=fields)

    def _store_readme(self, repo: Repository, content: str | None, now: datetime) -> None:
        if content is None:
            RepositoryReadme.objects.filter(repository=repo).delete()
            return
        raw = content.encode()
        limit = settings.REPO_README_MAX_BYTES
        RepositoryReadme.objects.update_or_create(
            repository=repo,
            defaults={
                "content": raw[:limit].decode(errors="ignore"),
                "size": len(raw),
                "truncated": len(raw) > limit,
                "fetched_at": now,
            },
        )

    def _store_snapshot(self, repo: Repository, data: ActivityData, now: datetime) -> None:
        signals = compute_activity(data, now)
        RepositorySnapshot.objects.create(repository=repo, **vars(signals))
        keep = settings.REPO_SNAPSHOT_HISTORY
        old = RepositorySnapshot.objects.filter(repository=repo).order_by("-captured_at", "-pk")
        stale_ids = list(old.values_list("pk", flat=True)[keep:])
        if stale_ids:
            RepositorySnapshot.objects.filter(pk__in=stale_ids).delete()


__all__ = ["PARTS", "Outcome", "RepositoryAnalysisService", "normalize_label"]
