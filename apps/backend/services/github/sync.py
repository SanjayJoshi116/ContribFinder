"""GitHub profile sync (design D2): ordered, resumable steps persisted on the SyncJob.

Steps already ``done``/``not_found`` are skipped on retry, and the languages step records
per-repository progress, so a retried job never re-fetches completed work. The job is
re-checked for cancellation before each step and each language request.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from github.models import GitHubProfile
from jobs.models import SyncJob
from repositories.models import Repository, RepositoryLanguage, RepositoryTopic, UserRepository

from .client import GitHubClient, GitHubRepo
from .errors import GitHubNotFound

logger = logging.getLogger(__name__)

Step = SyncJob.StepState
STEPS = ("profile", "readme", "repositories", "languages", "topics")
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
                RepositoryLanguage.objects.filter(repository=repo).delete()
                RepositoryLanguage.objects.bulk_create(
                    RepositoryLanguage(repository=repo, language=lang, bytes=count)
                    for lang, count in languages.items()
                )
            done.append(repo.pk)
            self._update_metadata(languages_done=done)
        return Step.DONE

    def _step_topics(self, client: GitHubClient) -> str:
        topics_by_repo: dict[str, list[str]] = self.job.metadata.get("repo_topics", {})
        with transaction.atomic():
            for repo_pk, topics in topics_by_repo.items():
                RepositoryTopic.objects.filter(repository_id=int(repo_pk)).delete()
                RepositoryTopic.objects.bulk_create(
                    RepositoryTopic(repository_id=int(repo_pk), topic=topic)
                    for topic in dict.fromkeys(topics)
                )
        return Step.DONE

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
