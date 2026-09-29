"""GitHub profile sync (design D2): ordered, resumable steps persisted on the SyncJob.

Steps already ``done``/``not_found``/``skipped`` are skipped on retry, and the languages,
dependencies and contributions steps record per-repository progress, so a retried job never
re-fetches completed work. The job is re-checked for cancellation before each step and each
per-repository request. The final ``analysis`` step builds the developer profile from the
stored data without calling GitHub (Phase 3).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from accounts.models import User
from github.models import GitHubProfile
from jobs.models import SyncJob
from repositories.models import (
    Repository,
    RepositoryDependency,
    RepositoryLanguage,
    RepositoryTopic,
    UserRepository,
)
from services.profiling.analysis import ProfileAnalysisService
from services.profiling.manifests import is_manifest, parse_manifest

from .client import GitHubClient, GitHubRepo, PullRequestRef, PushRef
from .errors import GitHubClientError, GitHubForbidden, GitHubNotFound, GitHubValidationError

logger = logging.getLogger(__name__)

Step = SyncJob.StepState
STEPS = (
    "profile",
    "readme",
    "repositories",
    "languages",
    "topics",
    "dependencies",
    "contributions",
    "analysis",
)
# A single repository we may not read (404, a 403 that is not a rate limit, other 4xx) is
# skipped; rate limits and transient errors still go through the job's retry policy.
SKIPPABLE = (GitHubNotFound, GitHubForbidden, GitHubClientError)
FINISHED = {Step.DONE, Step.NOT_FOUND, Step.SKIPPED}


class JobCancelled(Exception):
    """The job was cancelled (e.g. GitHub disconnected); stop without further requests."""


def initial_steps() -> dict[str, str]:
    return dict.fromkeys(STEPS, Step.PENDING)


class GitHubSyncService:
    def __init__(
        self,
        job: SyncJob,
        client_factory: Callable[[User], GitHubClient] = GitHubClient.for_user,
    ) -> None:
        self.job = job
        self.user: User = job.user
        self._client_factory = client_factory

    def run(self) -> None:
        with self._client_factory(self.user) as client:
            for step in STEPS:
                if self.job.steps.get(step) in FINISHED:
                    continue
                self._check_cancelled()
                self._set_step(step, Step.RUNNING)
                try:
                    outcome = getattr(self, f"_step_{step}")(client)
                except Exception:
                    self._set_step(step, Step.FAILED)
                    raise
                self._set_step(step, outcome)

    # --- steps --------------------------------------------------------------------

    def _step_profile(self, client: GitHubClient) -> str:
        gh = client.get_authenticated_user()
        GitHubProfile.objects.update_or_create(
            user=self.user,
            defaults={
                "github_id": gh.github_id,
                "login": gh.login,
                "name": gh.name,
                "bio": gh.bio,
                "company": gh.company,
                "location": gh.location,
                "blog": gh.blog,
                "avatar_url": gh.avatar_url,
                "followers": gh.followers,
                "following": gh.following,
                "public_repos": gh.public_repos,
                "github_created_at": gh.created_at,
                "synced_at": timezone.now(),
            },
        )
        return Step.DONE

    def _step_readme(self, client: GitHubClient) -> str:
        profile = self._profile()
        content = client.get_profile_readme(profile.login)
        profile.has_profile_readme = content is not None
        profile.profile_readme = content or ""
        profile.save(update_fields=["has_profile_readme", "profile_readme"])
        return Step.DONE if content is not None else Step.NOT_FOUND

    def _step_repositories(self, client: GitHubClient) -> str:
        login = self._profile().login
        repos, truncated = client.list_owned_repositories(login)
        owned = [r for r in repos if r.owner_login.lower() == login.lower()]
        owned.sort(key=lambda r: r.pushed_at or timezone.now().replace(year=1970), reverse=True)
        cap = settings.GITHUB_SYNC_MAX_REPOS
        selected = owned[:cap]

        now = timezone.now()
        with transaction.atomic():
            stored = [_upsert_repository(r, now) for r in selected]
            keep = {repo.pk for repo in stored}
            links = UserRepository.objects.filter(
                user=self.user, relation=UserRepository.Relation.OWNER
            )
            links.exclude(repository_id__in=keep).delete()
            existing = set(links.values_list("repository_id", flat=True))
            UserRepository.objects.bulk_create(
                UserRepository(user=self.user, repository_id=pk) for pk in keep - existing
            )

        self._update_metadata(
            repos_total=len(owned),
            repos_capped=len(owned) > cap,
            repos_truncated=truncated,
            repo_ids=[repo.pk for repo in stored],
            repo_topics={
                str(repo.pk): list(r.topics) for repo, r in zip(stored, selected, strict=True)
            },
            languages_done=[],
        )
        return Step.DONE

    def _step_languages(self, client: GitHubClient) -> str:
        done: list[int] = list(self.job.metadata.get("languages_done", []))
        repos = Repository.objects.filter(pk__in=self.job.metadata.get("repo_ids", []))
        for repo in repos.order_by("-pushed_at"):
            if repo.pk in done:
                continue
            self._check_cancelled()
            try:
                languages = client.get_languages(repo.full_name)
            except GitHubNotFound:
                languages = {}  # deleted between listing and now: nothing to record
            with transaction.atomic():
                _replace_languages(repo, languages)
            done.append(repo.pk)
            self._update_metadata(languages_done=done)
        return Step.DONE

    def _step_topics(self, client: GitHubClient) -> str:
        topics_by_repo: dict[str, list[str]] = self.job.metadata.get("repo_topics", {})
        with transaction.atomic():
            for repo_pk, topics in topics_by_repo.items():
                _replace_topics(int(repo_pk), topics)
        return Step.DONE

    def _step_dependencies(self, client: GitHubClient) -> str:
        done: list[int] = list(self.job.metadata.get("dependencies_done", []))
        candidates = Repository.objects.filter(
            pk__in=self.job.metadata.get("repo_ids", []), is_fork=False
        ).order_by(F("pushed_at").desc(nulls_last=True), "pk")
        cap = settings.GITHUB_MANIFEST_MAX_REPOS
        total = candidates.count()
        self._update_metadata(dependencies_total=total, dependencies_capped=total > cap)
        for repo in candidates[:cap]:
            if repo.pk in done:
                continue
            self._check_cancelled()
            try:
                dependencies = _read_manifests(client, repo.full_name)
            except SKIPPABLE:
                dependencies = None  # unreadable right now: keep what we knew
            if dependencies is not None:
                with transaction.atomic():
                    RepositoryDependency.objects.filter(repository=repo).delete()
                    RepositoryDependency.objects.bulk_create(
                        RepositoryDependency(
                            repository=repo, ecosystem=eco, name=name, manifest_path=path
                        )
                        for (eco, name), path in dependencies.items()
                    )
            done.append(repo.pk)
            self._update_metadata(dependencies_done=done)
        return Step.DONE

    def _step_contributions(self, client: GitHubClient) -> str:
        login = self._profile().login
        plan: list[dict[str, Any]] | None = self.job.metadata.get("contrib_plan")
        if plan is None:
            try:
                prs, prs_truncated = client.search_merged_pull_requests(login)
            except GitHubValidationError:
                return Step.SKIPPED  # GitHub won't search this user; keep previous links
            pushes = client.list_public_pushes(login)
            plan, total = self._plan_contributions(login, prs, pushes)
            self._update_metadata(
                contrib_plan=plan,
                contrib_done={},
                contrib_repos_total=total,
                contrib_capped=total > settings.GITHUB_CONTRIB_MAX_REPOS,
                contrib_prs_truncated=prs_truncated,
            )

        # full name → stored repository pk, or None when it could not (or must not) be stored
        done: dict[str, int | None] = dict(self.job.metadata.get("contrib_done", {}))
        for item in plan:
            name = item["full_name"]
            if name in done:
                continue
            self._check_cancelled()
            done[name] = self._store_contributed_repository(client, name, login)
            self._update_metadata(contrib_done=done)

        by_pk: dict[int, dict[str, Any]] = {
            pk: item for item in plan if (pk := done.get(item["full_name"])) is not None
        }
        with transaction.atomic():
            links = UserRepository.objects.filter(
                user=self.user, relation=UserRepository.Relation.CONTRIBUTOR
            )
            links.exclude(repository_id__in=by_pk).delete()
            for pk, item in by_pk.items():
                UserRepository.objects.update_or_create(
                    user=self.user,
                    repository_id=pk,
                    relation=UserRepository.Relation.CONTRIBUTOR,
                    defaults={
                        "merged_pr_count": item["prs"],
                        "push_count": item["pushes"],
                        "last_contributed_at": _parse_dt(item["last"]),
                    },
                )
        return Step.DONE

    def _step_analysis(self, client: GitHubClient) -> str:
        ProfileAnalysisService(self.user).run()  # raises ProfileAnalysisError: not retried
        return Step.DONE

    def _store_contributed_repository(
        self, client: GitHubClient, full_name: str, login: str
    ) -> int | None:
        try:
            gh = client.get_repository(full_name)
            if gh.owner_login.lower() == login.lower():
                return None  # transferred to the user since: it is their own repository now
            languages = client.get_languages(gh.full_name)
        except SKIPPABLE:
            return None
        with transaction.atomic():
            repo = _upsert_repository(gh, timezone.now())
            _replace_languages(repo, languages)
            _replace_topics(repo.pk, gh.topics)
        return repo.pk

    def _plan_contributions(
        self, login: str, prs: list[PullRequestRef], pushes: list[PushRef]
    ) -> tuple[list[dict[str, Any]], int]:
        """Group contributions by repository, drop the user's own repositories, and keep the
        top ``GITHUB_CONTRIB_MAX_REPOS`` by merged PRs, then pushes. JSON-serializable."""
        owned = {
            name.lower()
            for name in Repository.objects.filter(
                user_links__user=self.user, user_links__relation=UserRepository.Relation.OWNER
            ).values_list("full_name", flat=True)
        }
        events = [(pr.repo_full_name, "prs", pr.merged_at) for pr in prs]
        events += [(push.repo_full_name, "pushes", push.created_at) for push in pushes]
        grouped: dict[str, dict[str, Any]] = {}
        for full_name, kind, when in events:
            key = full_name.lower()
            if key in owned or key.split("/", 1)[0] == login.lower():
                continue
            entry = grouped.setdefault(
                key, {"full_name": full_name, "prs": 0, "pushes": 0, "last": None}
            )
            entry[kind] += 1
            last = _parse_dt(entry["last"])
            if when and (last is None or when > last):
                entry["last"] = when.isoformat()
        ranked = sorted(grouped.values(), key=lambda e: (-e["prs"], -e["pushes"], e["full_name"]))
        return ranked[: settings.GITHUB_CONTRIB_MAX_REPOS], len(ranked)

    # --- helpers ----------------------------------------------------------------------

    def _profile(self) -> GitHubProfile:
        return GitHubProfile.objects.get(user=self.user)

    def _check_cancelled(self) -> None:
        status = SyncJob.objects.filter(pk=self.job.pk).values_list("status", flat=True).first()
        if status == SyncJob.Status.CANCELLED:
            raise JobCancelled()

    def _set_step(self, step: str, state: str) -> None:
        self.job.steps = {**self.job.steps, step: str(state)}
        self.job.save(update_fields=["steps", "updated_at"])

    def _update_metadata(self, **values: Any) -> None:
        self.job.metadata = {**self.job.metadata, **values}
        self.job.save(update_fields=["metadata", "updated_at"])


def _upsert_repository(gh: GitHubRepo, now: Any) -> Repository:
    # A different repo that used to have this name (deleted and recreated, or renamed away) is
    # stale; drop it so the unique full_name can move to the current repo.
    Repository.objects.filter(full_name=gh.full_name).exclude(github_id=gh.github_id).delete()
    repo, _ = Repository.objects.update_or_create(
        github_id=gh.github_id,
        defaults={
            "owner_login": gh.owner_login,
            "name": gh.name,
            "full_name": gh.full_name,
            "description": gh.description,
            "html_url": gh.html_url,
            "default_branch": gh.default_branch,
            "stars": gh.stars,
            "forks": gh.forks,
            "open_issues": gh.open_issues,
            "primary_language": gh.primary_language,
            "license_spdx": gh.license_spdx,
            "is_fork": gh.is_fork,
            "is_archived": gh.is_archived,
            "github_created_at": gh.created_at,
            "github_updated_at": gh.updated_at,
            "pushed_at": gh.pushed_at,
            "synced_at": now,
        },
    )
    return repo


def _replace_languages(repo: Repository, languages: dict[str, int]) -> None:
    RepositoryLanguage.objects.filter(repository=repo).delete()
    RepositoryLanguage.objects.bulk_create(
        RepositoryLanguage(repository=repo, language=lang, bytes=count)
        for lang, count in languages.items()
    )


def _replace_topics(repo_pk: int, topics: Iterable[str]) -> None:
    RepositoryTopic.objects.filter(repository_id=repo_pk).delete()
    RepositoryTopic.objects.bulk_create(
        RepositoryTopic(repository_id=repo_pk, topic=topic) for topic in dict.fromkeys(topics)
    )


def _read_manifests(client: GitHubClient, full_name: str) -> dict[tuple[str, str], str]:
    """``{(ecosystem, name): manifest path}`` from the repository's root manifests."""
    found: dict[tuple[str, str], str] = {}
    for entry in client.list_root_contents(full_name):
        if entry.type != "file" or not is_manifest(entry.name):
            continue
        if entry.size > settings.GITHUB_MANIFEST_MAX_BYTES:
            continue
        try:
            text = client.get_file(full_name, entry.name)
        except GitHubNotFound:
            continue  # removed between listing and fetching
        for dep in parse_manifest(entry.name, text):
            found.setdefault((dep.ecosystem, dep.name), entry.name)
    return found


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None
