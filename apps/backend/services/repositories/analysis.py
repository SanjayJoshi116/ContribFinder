"""Candidate repository analysis (FR-REPO-003, design D5).

Fetches the requested data types of one repository, then writes them in one transaction and
walks the lifecycle. Repository data is shared: callers pick only the stale parts, so a fresh
repository is never fetched again for another developer.

Errors: an error that belongs to the repository itself marks it FAILED and is not raised, so
a discovery run continues with the next repository: a permanent GitHub error (404, 403, 451),
any other non-retryable 4xx (``client_error``) or a response the client cannot interpret
(``invalid_response``). Anything else (rate limit, transient failure, revoked credentials,
cancellation, a lost claim, a database or programming error) restores the previous state
and is re-raised for the caller's retry policy. A missing README, community file or label is data.
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
from django.db.models import Q
from django.utils import timezone

from issues.models import Issue
from repositories.models import Lifecycle, Repository, RepositoryReadme, RepositorySnapshot
from services.github.client import (
    CommunityProfile,
    GitHubClient,
    GitHubRepo,
    IssueData,
    IssuePage,
    PullSample,
)
from services.github.errors import (
    GitHubClientError,
    GitHubForbidden,
    GitHubInvalidResponse,
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
from services.issues.analysis import IssueInput, analyze
from services.matching.activity import WINDOW_DAYS, ActivityData, compute_activity

from . import lifecycle
from .staleness import PARTS, is_released_name, stale_parts

logger = logging.getLogger(__name__)

# Errors that belong to the repository, most specific first: the first match gives the code.
# GitHubClientError comes after its subclasses (451 keeps ``unavailable``). Rate limits,
# transient and auth errors are not here: they are about the job, not the repository.
ERROR_CODES: tuple[tuple[type[Exception], str], ...] = (
    (GitHubNotFound, "not_found"),
    (GitHubUnavailableForLegalReasons, "unavailable"),
    (GitHubForbidden, "forbidden"),
    (GitHubInvalidResponse, "invalid_response"),  # a GitHub answer the client can't read
    (GitHubClientError, "client_error"),
)
REPOSITORY_ERRORS = tuple(cls for cls, _ in ERROR_CODES)
# Issue columns written by each fetch (everything but the identity).
ISSUE_FIELDS = (
    "repository",
    "number",
    "title",
    "body",
    "raw_labels",
    "state",
    "is_locked",
    "has_assignee",
    "comments",
    "html_url",
    "github_created_at",
    "github_updated_at",
    "labels",
    "contribution_type",
    "contribution_type_evidence",
    "difficulty",
    "difficulty_evidence",
    "technologies",
    "analyzed_at",
)
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
    issues: IssuePage | None = None


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
        """Claim the repository and analyze its stale parts; ``parts`` narrows them to those
        (a queued task for one data type). A FAILED retry checks every part, and a repository
        that gave up its name fetches metadata first, by GitHub ID."""
        now = self._now or timezone.now()
        repo = lifecycle.claim(repo_id)
        if repo is None:
            return Outcome.SKIPPED
        if repo.previous_lifecycle == Lifecycle.FAILED:
            wanted = list(PARTS)  # a retry must re-check that the repository exists
        else:
            asked = None if parts is None else set(parts)
            wanted = [p for p in stale_parts(repo, now) if asked is None or p in asked]
            if is_released_name(repo.full_name) and "metadata" not in wanted:
                wanted.insert(0, "metadata")
            if not wanted and repo.previous_lifecycle != Lifecycle.STALE:
                # Refreshed by another analysis since it was queued: nothing to fetch, and
                # completing would stamp a transition that makes freshness regenerate.
                lifecycle.release(repo)
                return Outcome.SKIPPED
        fetched_name = None if "metadata" in wanted else repo.full_name
        try:
            try:
                fetched = self._fetch(repo, wanted, now)
            except REPOSITORY_ERRORS as exc:
                code = next(code for cls, code in ERROR_CODES if isinstance(exc, cls))
                logger.info(
                    "Repository %s failed: %s (%s)", repo.full_name, code, type(exc).__name__
                )
                lifecycle.fail(repo, code)
                return Outcome.FAILED
            with transaction.atomic():
                lifecycle.hold(repo, fetched_name=fetched_name)
                topics, has_dependencies = self._store(repo, fetched, now)
                lifecycle.complete(repo, now=now, topics=topics, has_dependencies=has_dependencies)
        except lifecycle.ClaimLost:
            # Reclaimed by another analysis, which owns the state now; or renamed meanwhile,
            # so the fetched data is discarded and the restored row stays due.
            lifecycle.release(repo)
            return Outcome.SKIPPED
        except BaseException:
            lifecycle.release(repo)
            raise
        return Outcome.ANALYZED

    def _between_parts(self, repo: Repository) -> None:
        self._check_cancelled()
        lifecycle.renew(repo)  # an analysis longer than the stale time is not reclaimed

    # --- fetching (no writes) --------------------------------------------------------------

    def _fetch(self, repo: Repository, parts: list[str], now: datetime) -> _Fetched:
        c, name, out = self.client, repo.full_name, _Fetched()
        if "metadata" in parts:
            self._between_parts(repo)
            out.metadata = self._metadata(repo)
            name = out.metadata.full_name  # the current name after a rename (redirect followed)
            out.languages = c.get_languages(name)
        if "readme" in parts:
            self._between_parts(repo)
            out.readme, out.readme_fetched = c.get_readme(name), True
        if "community" in parts:
            self._between_parts(repo)
            out.community = c.get_community_profile(name)
            out.labels = c.list_label_names(name)
        if "dependencies" in parts:
            self._between_parts(repo)
            out.dependencies = read_manifests(c, name)
        if "activity" in parts:
            self._between_parts(repo)
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
        if "issues" in parts:
            self._between_parts(repo)
            out.issues = c.list_open_issues(name)
        return out

    def _metadata(self, repo: Repository) -> GitHubRepo:
        """By name, or by GitHub ID when the name was given up, is gone, or now belongs to
        another repository. A 404 by ID means the repository no longer exists."""
        if not is_released_name(repo.full_name):
            try:
                found = self.client.get_repository(repo.full_name)
            except GitHubNotFound:
                pass
            else:
                if found.github_id == repo.github_id:
                    return found
        return self.client.get_repository_by_id(repo.github_id)

    # --- storing (one transaction) ---------------------------------------------------------

    def _store(
        self, repo: Repository, f: _Fetched, now: datetime
    ) -> tuple[list[str] | None, bool | None]:
        """Store the fetched parts. Returns the topics and dependency presence now stored,
        each None when that part was not fetched."""
        fields: list[str] = []
        topics: list[str] | None = None
        has_dependencies: bool | None = None
        if f.metadata is not None:
            stored = upsert_repository(f.metadata, now)
            if stored.pk != repo.pk:  # pragma: no cover - fetched by GitHub ID (_metadata)
                raise RuntimeError("Repository identity changed during analysis")
            repo.refresh_from_db()
            replace_languages(repo, f.languages or {})
            replace_topics(repo.pk, f.metadata.topics)
            topics = list(f.metadata.topics)
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
            has_dependencies = bool(f.dependencies)
            repo.dependencies_synced_at = now
            fields.append("dependencies_synced_at")
        if f.activity is not None:
            self._store_snapshot(repo, f.activity, now)
            repo.activity_synced_at = now
            fields.append("activity_synced_at")
        if f.issues is not None:
            self._store_issues(repo, f.issues.issues, now)
            repo.issues_synced_at = now
            repo.issues_truncated = f.issues.truncated
            fields += ["issues_synced_at", "issues_truncated"]
        if fields:
            repo.save(update_fields=fields)
        return topics, has_dependencies

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

    def _store_issues(self, repo: Repository, fetched: list[IssueData], now: datetime) -> None:
        """Replace the repository's issues with the fetched set: issues no longer returned
        (closed) are deleted, the others keep their row and get fresh fields and analysis."""
        limit = settings.ISSUE_BODY_MAX_CHARS
        thresholds = settings.ISSUE_DIFFICULTY
        ids = {i.github_id for i in fetched}
        # Lock every issue this replaces, deletes or updates, by pk, before touching any: the
        # order a generation's persist uses (services/locks.py), so the two never deadlock.
        touched = Issue.objects.filter(Q(repository=repo) | Q(github_id__in=ids))
        locked = list(touched.select_for_update().order_by("pk"))
        Issue.objects.filter(pk__in=[i.pk for i in locked if i.github_id not in ids]).delete()
        existing = {i.github_id: i for i in locked if i.github_id in ids}
        to_create: list[Issue] = []
        to_update: list[Issue] = []
        for data in fetched:
            body = data.body[:limit]
            result = analyze(IssueInput(data.title, body, data.labels, data.comments), thresholds)
            values = {
                "repository": repo,
                "number": data.number,
                "title": data.title[:1024],
                "body": body,
                "raw_labels": list(data.labels),
                "state": data.state,
                "is_locked": data.is_locked,
                "has_assignee": data.has_assignee,
                "comments": data.comments,
                "html_url": data.html_url,
                "github_created_at": data.created_at,
                "github_updated_at": data.updated_at,
                "labels": result.labels,
                "contribution_type": result.contribution_type,
                "contribution_type_evidence": result.contribution_type_evidence,
                "difficulty": result.difficulty,
                "difficulty_evidence": result.difficulty_evidence,
                "technologies": result.technologies,
                "analyzed_at": now,
            }
            if (issue := existing.get(data.github_id)) is not None:
                for name, value in values.items():
                    setattr(issue, name, value)
                to_update.append(issue)
            else:
                to_create.append(Issue(github_id=data.github_id, **values))
        if to_update:
            Issue.objects.bulk_update(to_update, list(ISSUE_FIELDS))
        Issue.objects.bulk_create(to_create)


__all__ = ["PARTS", "Outcome", "RepositoryAnalysisService", "normalize_label"]
