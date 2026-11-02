"""GitHub profile sync (design D2): ordered, resumable steps persisted on the SyncJob.

Steps already ``done``/``not_found``/``skipped`` are skipped on retry, and the languages,
dependencies and contributions steps record per-repository progress, so a retried job never
re-fetches completed work. The job is re-checked for cancellation before each step and each
per-repository request. The final ``analysis`` step builds the developer profile from the
stored data without calling GitHub (Phase 3).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.db.models import F, Q
from django.utils import timezone

from accounts.models import User
from github.models import GitHubAccount, GitHubProfile
from jobs.models import SyncJob
from repositories.models import (
    Repository,
    UserRepository,
)
from services.job_guard import heartbeat, job_write, merge_metadata, save_progress
from services.profiling.analysis import ProfileAnalysisService

from .client import GitHubClient, GitHubUser, PullRequestRef, PushRef, parse_dt
from .errors import GitHubClientError, GitHubForbidden, GitHubNotFound, GitHubValidationError
from .storage import (
    lock_repository,
    read_manifests,
    replace_dependencies,
    replace_languages,
    replace_topics,
    upsert_repository,
)

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
                self._set_step(step, Step.RUNNING)  # raises JobCancelled unless RUNNING
                try:
                    outcome = getattr(self, f"_step_{step}")(client)
                except Exception:
                    self._set_step(step, Step.FAILED)
                    raise
                self._set_step(step, outcome)

    # --- steps --------------------------------------------------------------------

    def _step_profile(self, client: GitHubClient) -> str:
        gh = client.get_authenticated_user()
        with job_write(self.job):
            self._store_profile(gh)
        return Step.DONE

    def _store_profile(self, gh: GitHubUser) -> None:
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
        # /auth/me serves the account's login and avatar: keep them in step with GitHub. A
        # filter-update, so an account deleted meanwhile (disconnect) is not recreated.
        GitHubAccount.objects.filter(user=self.user).update(
            username=gh.login, avatar_url=gh.avatar_url
        )

    def _step_readme(self, client: GitHubClient) -> str:
        profile = self._profile()
        try:
            content = client.get_profile_readme(profile.login)
        except SKIPPABLE:
            return Step.SKIPPED  # blocked or unreadable now: keep the README we stored before
        profile.has_profile_readme = content is not None
        profile.profile_readme = content or ""
        with job_write(self.job):
            profile.save(update_fields=["has_profile_readme", "profile_readme"])
        return Step.DONE if content is not None else Step.NOT_FOUND

    def _step_repositories(self, client: GitHubClient) -> str:
        login = self._profile().login
        repos, truncated = client.list_owned_repositories(login)
        owned = [r for r in repos if r.owner_login.lower() == login.lower()]
        owned.sort(key=lambda r: r.pushed_at or timezone.now().replace(year=1970), reverse=True)
        cap = settings.GITHUB_SYNC_MAX_REPOS
        # Chosen by push time, stored in GitHub ID order: the order of every bulk lock on
        # shared repository rows, so a sync never deadlocks with discovery (GHS-1).
        selected = sorted(owned[:cap], key=lambda r: r.github_id)

        now = timezone.now()
        with job_write(self.job):
            stored = [upsert_repository(r, now) for r in selected]
            # Topics come with the listing: stored with their rows, so no later step can find
            # a row deleted or re-pointed meanwhile.
            for repo, r in zip(stored, selected, strict=True):
                replace_topics(repo.pk, list(r.topics))
            keep = {repo.pk for repo in stored}
            links = UserRepository.objects.filter(
                user=self.user, relation=UserRepository.Relation.OWNER
            )
            links.exclude(repository_id__in=keep).delete()
            existing = set(links.values_list("repository_id", flat=True))
            UserRepository.objects.bulk_create(
                UserRepository(user=self.user, repository_id=pk) for pk in keep - existing
            )

        merge_metadata(
            self.job,
            {
                "repos_total": len(owned),
                "repos_capped": len(owned) > cap,
                "repos_truncated": truncated,
                "repo_ids": [repo.pk for repo in stored],
                "languages_done": [],
                "languages_skipped": [],
            },
        )
        return Step.DONE

    def _step_languages(self, client: GitHubClient) -> str:
        done: list[int] = list(self.job.metadata.get("languages_done", []))
        skipped: list[int] = list(self.job.metadata.get("languages_skipped", []))
        repos = Repository.objects.filter(pk__in=self.job.metadata.get("repo_ids", []))
        for repo in repos.order_by("-pushed_at"):
            if repo.pk in done:
                continue
            self._check_cancelled()
            languages: dict[str, int] | None
            try:
                languages = client.get_languages(repo.full_name)
            except GitHubNotFound:
                languages = {}  # deleted between listing and now: nothing to record
            except SKIPPABLE:
                languages = None  # blocked (403, 451) or unreadable: keep what we knew
            with job_write(self.job):
                if languages is None:
                    skipped.append(repo.pk)
                else:
                    lock_repository(repo)
                    replace_languages(repo, languages)
                done.append(repo.pk)
                merge_metadata(self.job, {"languages_done": done, "languages_skipped": skipped})
        return Step.DONE

    def _step_topics(self, client: GitHubClient) -> str:
        return Step.DONE  # stored by the repositories step; kept as a step for the progress UI

    def _step_dependencies(self, client: GitHubClient) -> str:
        done: list[int] = list(self.job.metadata.get("dependencies_done", []))
        ids: list[int] | None = self.job.metadata.get("dependencies_ids")
        if ids is None:
            # Chosen once: a retry reads the same set, whatever was pushed since (GHS-9).
            candidates = Repository.objects.filter(
                pk__in=self.job.metadata.get("repo_ids", []), is_fork=False
            ).order_by(F("pushed_at").desc(nulls_last=True), "pk")
            cap = settings.GITHUB_MANIFEST_MAX_REPOS
            total = candidates.count()
            ids = list(candidates.values_list("pk", flat=True)[:cap])
            merge_metadata(
                self.job,
                {
                    "dependencies_ids": ids,
                    "dependencies_total": total,
                    "dependencies_capped": total > cap,
                },
            )
        repos = Repository.objects.in_bulk([pk for pk in ids if pk not in done])
        for repo in (repos[pk] for pk in ids if pk in repos):  # chosen order; deleted ones gone
            self._check_cancelled()
            try:
                dependencies = read_manifests(client, repo.full_name)
            except SKIPPABLE:
                dependencies = None  # unreadable right now: keep what we knew
            if dependencies is not None:
                with job_write(self.job):
                    lock_repository(repo)
                    replace_dependencies(repo, dependencies)
            done.append(repo.pk)
            merge_metadata(self.job, {"dependencies_done": done})
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
            merge_metadata(
                self.job,
                {
                    "contrib_plan": plan,
                    "contrib_done": {},
                    "contrib_repos_total": total,
                    "contrib_capped": total > settings.GITHUB_CONTRIB_MAX_REPOS,
                    "contrib_prs_truncated": prs_truncated,
                },
            )

        # full name → stored repository pk, or None when it could not (or must not) be stored
        done: dict[str, int | None] = dict(self.job.metadata.get("contrib_done", {}))
        # names observed but unreadable this time (403, 451, ...): their links are kept (GHS-6)
        skipped: list[str] = list(self.job.metadata.get("contrib_skipped", []))
        for item in plan:
            name = item["full_name"]
            if name in done:
                continue
            self._check_cancelled()
            try:
                done[name] = self._store_contributed_repository(client, name, login)
            except SKIPPABLE:
                done[name] = None
                skipped.append(name)
            merge_metadata(self.job, {"contrib_done": done, "contrib_skipped": skipped})

        by_pk = _merge_by_repository(plan, done)
        with job_write(self.job):
            links = UserRepository.objects.filter(
                user=self.user, relation=UserRepository.Relation.CONTRIBUTOR
            )
            unreadable = Q()
            for name in skipped:
                unreadable |= Q(repository__full_name__iexact=name)
            links.exclude(repository_id__in=by_pk).exclude(unreadable).delete()
            for pk, item in by_pk.items():
                UserRepository.objects.update_or_create(
                    user=self.user,
                    repository_id=pk,
                    relation=UserRepository.Relation.CONTRIBUTOR,
                    defaults={
                        "merged_pr_count": item["prs"],
                        "push_count": item["pushes"],
                        "last_contributed_at": parse_dt(item["last"]),
                    },
                )
        return Step.DONE

    def _step_analysis(self, client: GitHubClient) -> str:
        # Raises ProfileAnalysisError (not retried), or JobCancelled after a deletion.
        ProfileAnalysisService(self.user, job=self.job).run()
        return Step.DONE

    def _store_contributed_repository(
        self, client: GitHubClient, full_name: str, login: str
    ) -> int | None:
        """The stored repository's pk, or None when it is gone (404) or now the user's own.
        Other ``SKIPPABLE`` errors propagate: the repository is observed but unreadable."""
        try:
            gh = client.get_repository(full_name)
            if gh.owner_login.lower() == login.lower():
                return None  # transferred to the user since: it is their own repository now
            languages = client.get_languages(gh.full_name)
        except GitHubNotFound:
            return None
        with job_write(self.job):
            repo = upsert_repository(gh, timezone.now())
            replace_languages(repo, languages)
            replace_topics(repo.pk, gh.topics)
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
            last = parse_dt(entry["last"])
            if when and (last is None or when > last):
                entry["last"] = when.isoformat()
        ranked = sorted(grouped.values(), key=lambda e: (-e["prs"], -e["pushes"], e["full_name"]))
        return ranked[: settings.GITHUB_CONTRIB_MAX_REPOS], len(ranked)

    # --- helpers ----------------------------------------------------------------------

    def _profile(self) -> GitHubProfile:
        return GitHubProfile.objects.get(user=self.user)

    def _check_cancelled(self) -> None:
        """Cancellation check and heartbeat: called between units of work."""
        heartbeat(self.job)  # raises JobCancelled when cancelled, deleted or reclaimed

    def _set_step(self, step: str, state: str) -> None:
        self.job.steps = {**self.job.steps, step: str(state)}
        save_progress(self.job, steps=self.job.steps)


def _merge_by_repository(
    plan: list[dict[str, Any]], done: dict[str, int | None]
) -> dict[int, dict[str, Any]]:
    """Plan items by stored pk. Two names of one repository (renamed or transferred) add up:
    PRs and pushes summed, the latest time kept (GHS-5)."""
    by_pk: dict[int, dict[str, Any]] = {}
    for item in plan:
        pk = done.get(item["full_name"])
        if pk is None:
            continue
        merged = by_pk.get(pk)
        if merged is None:
            by_pk[pk] = dict(item)
            continue
        merged["prs"] += item["prs"]
        merged["pushes"] += item["pushes"]
        last, other = parse_dt(merged["last"]), parse_dt(item["last"])
        if other is not None and (last is None or other > last):
            merged["last"] = item["last"]
    return by_pk
