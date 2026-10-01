"""Repository discovery run (FR-REPO-001/002, design D7).

Steps, persisted on the SyncJob and resumable like the profile sync:
``queries`` (plan from the profile) → ``search`` (run queries, pre-filter, record provenance)
→ ``interactions`` (contributed repositories) → ``analysis`` (shared repository analysis,
capped per run) → ``pool`` (retention and size cap). Searches use the developer's token;
repository endpoints use the same token with the shared ``public`` ETag scope.
"""

from __future__ import annotations

import logging
import queue
import threading
from collections import Counter
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.db import connections, transaction
from django.db.models import Exists, F, Min, OuterRef
from django.utils import timezone

from accounts.models import User
from developers.models import DeveloperInterest, DeveloperProfile, DeveloperSkill
from github.models import GitHubProfile
from jobs.models import SyncJob
from repositories.models import (
    CandidateDiscovery,
    DiscoverySource,
    Lifecycle,
    Repository,
    RepositoryCandidate,
    UserRepository,
)
from services.errors import PermanentJobError
from services.github.client import PUBLIC_SCOPE, GitHubClient, GitHubRepo
from services.github.errors import GitHubValidationError
from services.github.storage import replace_topics, upsert_repository
from services.github.sync import JobCancelled
from services.repositories.analysis import RepositoryAnalysisService
from services.repositories.lifecycle import IN_PROGRESS
from services.repositories.staleness import stale_parts

from .filters import FilterConfig, prefilter
from .queries import (
    DiscoveryInput,
    InterestSignal,
    PlannedQuery,
    QueryConfig,
    SkillSignal,
    plan_queries,
)

logger = logging.getLogger(__name__)

Step = SyncJob.StepState
STEPS = ("queries", "search", "interactions", "analysis", "pool")
FINISHED = {Step.DONE, Step.NOT_FOUND, Step.SKIPPED}
INTERACTED = DiscoverySource.PREVIOUSLY_INTERACTED


class NotAnalyzed(PermanentJobError):
    code = "not_analyzed"


ClientFactory = Callable[..., GitHubClient]


class DiscoveryService:
    def __init__(
        self,
        job: SyncJob,
        client_factory: ClientFactory = GitHubClient.for_user,
        now: datetime | None = None,
    ) -> None:
        self.job = job
        self.user: User = job.user
        self._client_factory = client_factory
        self._now = now

    def run(self) -> None:
        profile = DeveloperProfile.objects.filter(user=self.user).first()
        if profile is None:
            raise NotAnalyzed("No analyzed developer profile")
        self.profile = profile
        self.now = self._now or timezone.now()
        with (
            self._client_factory(self.user) as search_client,
            self._client_factory(self.user, cache_scope=PUBLIC_SCOPE) as repo_client,
        ):
            self.search_client, self.repo_client = search_client, repo_client
            for step in STEPS:
                if self.job.steps.get(step) in FINISHED:
                    continue
                self._check_cancelled()
                self._set_step(step, Step.RUNNING)
                try:
                    outcome = getattr(self, f"_step_{step}")()
                except Exception:
                    self._set_step(step, Step.FAILED)
                    raise
                self._set_step(step, outcome)

    # --- steps ------------------------------------------------------------------------

    def _step_queries(self) -> str:
        plan = plan_queries(self._input(), QueryConfig.from_settings())
        self._update_metadata(plan=[q.as_json() for q in plan])
        return Step.DONE

    def _step_search(self) -> str:
        plan = [PlannedQuery(**q) for q in self.job.metadata.get("plan", [])]
        if not plan:
            return Step.SKIPPED
        meta = self.job.metadata
        done: list[str] = list(meta.get("queries_done", []))
        skipped: list[str] = list(meta.get("queries_skipped", []))
        rejections: Counter[str] = Counter(meta.get("rejections", {}))
        found = int(meta.get("results_found", 0))
        owned, login, cfg = self._owned(), self._login(), FilterConfig.from_settings()
        for query in plan:
            if query.key in done or query.key in skipped:
                continue
            self._check_cancelled()
            try:
                results = self.search_client.search_repositories(
                    query.q, settings.DISCOVERY_RESULTS_PER_QUERY
                )
            except GitHubValidationError:
                skipped.append(query.key)
                self._update_metadata(queries_skipped=skipped)
                continue
            with transaction.atomic():
                for rank, gh in enumerate(results, start=1):
                    reason = prefilter(gh, login=login, owned=owned, now=self.now, cfg=cfg)
                    if reason:
                        rejections[reason] += 1
                        continue
                    repo = self._store_search_result(gh)
                    self._record(repo, query.source, query.core, rank)
            found += len(results)
            done.append(query.key)
            self._update_metadata(
                queries_done=done, rejections=dict(rejections), results_found=found
            )
        return Step.DONE

    def _step_interactions(self) -> str:
        owned, login, cfg = self._owned(), self._login(), FilterConfig.from_settings()
        rejections: Counter[str] = Counter(self.job.metadata.get("rejections", {}))
        added = 0
        contributed = Repository.objects.filter(
            user_links__user=self.user, user_links__relation=UserRepository.Relation.CONTRIBUTOR
        ).distinct()
        with transaction.atomic():
            for repo in contributed:
                reason = prefilter(
                    repo, login=login, owned=owned, now=self.now, cfg=cfg, check_stars=False
                )
                if reason:
                    rejections[reason] += 1
                    continue
                if repo.lifecycle_changed_at is None:
                    Repository.objects.filter(pk=repo.pk).update(lifecycle_changed_at=self.now)
                self._record(repo, INTERACTED, "", None)
                added += 1
        self._update_metadata(rejections=dict(rejections), interactions_added=added)
        return Step.DONE

    def _step_analysis(self) -> str:
        done: list[int] = list(self.job.metadata.get("analyzed", []))
        outcomes: Counter[str] = Counter(self.job.metadata.get("analysis_outcomes", {}))
        pending = [r for r in self._pool_repositories() if self._needs_analysis(r)]
        cap = settings.DISCOVERY_MAX_ANALYSES_PER_RUN
        self._update_metadata(analysis_total=len(pending), analysis_capped=len(pending) > cap)
        todo = [r.pk for r in pending[:cap] if r.pk not in done]
        for repo_id, outcome in self._analyze(todo):
            outcomes[outcome] += 1
            done.append(repo_id)
            self._update_metadata(analyzed=done, analysis_outcomes=dict(outcomes))
        return Step.DONE

    def _analyze(self, repo_ids: list[int]) -> Iterator[tuple[int, str]]:
        """Analyze repositories, yielding ``(repo_id, outcome)`` as each finishes. Runs
        ``DISCOVERY_ANALYSIS_CONCURRENCY`` threads, each with its own GitHub client and database
        connection; this (the job's) thread records progress. Kept low: GitHub asks for a
        user's requests to be mostly serial, and concurrency trips secondary rate limits."""
        workers = min(settings.DISCOVERY_ANALYSIS_CONCURRENCY, len(repo_ids))
        if workers <= 1:
            service = RepositoryAnalysisService(
                self.repo_client, check_cancelled=self._check_cancelled, now=self.now
            )
            for repo_id in repo_ids:
                self._check_cancelled()
                yield repo_id, service.run(repo_id)
            return

        todo: queue.SimpleQueue[int] = queue.SimpleQueue()
        for repo_id in repo_ids:
            todo.put(repo_id)
        results: queue.SimpleQueue[tuple[int, str] | BaseException] = queue.SimpleQueue()
        stop = threading.Event()

        def work() -> None:
            try:
                with self._client_factory(self.user, cache_scope=PUBLIC_SCOPE) as client:
                    service = RepositoryAnalysisService(
                        client, check_cancelled=self._check_cancelled, now=self.now
                    )
                    while not stop.is_set():
                        try:
                            repo_id = todo.get_nowait()
                        except queue.Empty:
                            return
                        self._check_cancelled()
                        results.put((repo_id, service.run(repo_id)))
            except BaseException as exc:  # handed to the job's thread, which re-raises it
                stop.set()
                results.put(exc)
            finally:
                connections.close_all()

        threads = [
            threading.Thread(target=work, name=f"discovery-analysis-{i}", daemon=True)
            for i in range(workers)
        ]
        for thread in threads:
            thread.start()
        error: BaseException | None = None
        try:
            while any(t.is_alive() for t in threads) or not results.empty():
                try:
                    item = results.get(timeout=1)
                except queue.Empty:
                    continue
                if isinstance(item, BaseException):
                    error = error or item  # the others finish their current repository
                else:
                    yield item
        finally:
            stop.set()
            for thread in threads:
                thread.join()
        if error is not None:
            raise error

    def _step_pool(self) -> str:
        pool = RepositoryCandidate.objects.filter(developer=self.profile)
        cutoff = self.now - timedelta(days=settings.DISCOVERY_CANDIDATE_RETENTION_DAYS)
        expired, _ = pool.filter(last_seen_at__lt=cutoff).delete()
        evicted = 0
        if pool.count() > settings.DISCOVERY_MAX_POOL:
            # Keep the best candidates in analysis order (previously interacted, best search
            # rank, most recently seen), so the kept pool is the one that gets analyzed.
            keep = list(
                pool.annotate(
                    interacted=Exists(_interacted_discoveries()),
                    best_rank=Min("discoveries__search_rank"),
                )
                .order_by(
                    F("interacted").desc(),
                    F("best_rank").asc(nulls_last=True),
                    F("last_seen_at").desc(),
                    "repository__full_name",
                )
                .values_list("pk", flat=True)[: settings.DISCOVERY_MAX_POOL]
            )
            evicted, _ = pool.exclude(pk__in=keep).delete()
        self._update_metadata(pool_expired=expired, pool_evicted=evicted, pool_size=pool.count())
        return Step.DONE

    # --- helpers ------------------------------------------------------------------------

    def _input(self) -> DiscoveryInput:
        skills = []
        developer_skills = (
            DeveloperSkill.objects.filter(profile=self.profile)
            .select_related("skill")
            .prefetch_related("evidence")
        )
        for ds in developer_skills:
            sources = frozenset(e.source for e in ds.evidence.all())
            skills.append(SkillSignal(ds.skill.slug, ds.confidence, sources))
        interests = tuple(
            InterestSignal(di.interest.slug, di.strength)
            for di in DeveloperInterest.objects.filter(profile=self.profile).select_related(
                "interest"
            )
        )
        owned = Repository.objects.filter(
            user_links__user=self.user,
            user_links__relation=UserRepository.Relation.OWNER,
            is_fork=False,
        ).prefetch_related("topics")
        topics = tuple(tuple(t.topic for t in repo.topics.all()) for repo in owned)
        return DiscoveryInput(
            login=self._login(),
            skills=tuple(skills),
            interests=interests,
            own_repository_topics=topics,
            now=self.now,
        )

    def _login(self) -> str:
        profile = GitHubProfile.objects.filter(user=self.user).first()
        if profile is not None:
            return profile.login
        account = getattr(self.user, "github_account", None)
        return account.username if account is not None else ""

    def _owned(self) -> set[str]:
        return {
            name.lower()
            for name in Repository.objects.filter(
                user_links__user=self.user, user_links__relation=UserRepository.Relation.OWNER
            ).values_list("full_name", flat=True)
        }

    def _store_search_result(self, gh: GitHubRepo) -> Repository:
        repo = upsert_repository(gh, self.now)
        replace_topics(repo.pk, gh.topics)
        if repo.lifecycle_changed_at is None:
            repo.lifecycle_changed_at = self.now
            repo.save(update_fields=["lifecycle_changed_at"])
        return repo

    def _record(self, repo: Repository, source: str, query: str, rank: int | None) -> None:
        candidate, created = RepositoryCandidate.objects.get_or_create(
            developer=self.profile,
            repository=repo,
            defaults={"first_discovered_at": self.now, "last_seen_at": self.now},
        )
        if not created:
            RepositoryCandidate.objects.filter(pk=candidate.pk).update(last_seen_at=self.now)
        discovery, created = CandidateDiscovery.objects.get_or_create(
            candidate=candidate,
            source=source,
            query=query,
            defaults={"search_rank": rank, "first_seen_at": self.now, "last_seen_at": self.now},
        )
        if not created:
            CandidateDiscovery.objects.filter(pk=discovery.pk).update(
                search_rank=rank, last_seen_at=self.now
            )

    def _pool_repositories(self) -> list[Repository]:
        """The developer's candidate repositories in analysis order: previously interacted
        first, then by best search rank, then name."""
        candidates = (
            RepositoryCandidate.objects.filter(developer=self.profile)
            .annotate(
                interacted=Exists(_interacted_discoveries()),
                best_rank=Min("discoveries__search_rank"),
            )
            .select_related("repository")
            .order_by(
                F("interacted").desc(),
                F("best_rank").asc(nulls_last=True),
                "repository__full_name",
            )
        )
        return [c.repository for c in candidates]

    def _needs_analysis(self, repo: Repository) -> bool:
        if repo.lifecycle in IN_PROGRESS:
            return False  # another run holds it; the candidate counts as awaiting analysis
        if repo.lifecycle in (Lifecycle.DISCOVERED, Lifecycle.STALE):
            return True
        if repo.lifecycle == Lifecycle.FAILED:
            retry_after = timedelta(hours=settings.REPO_FAILED_RETRY_HOURS)
            return repo.lifecycle_changed_at is None or (
                repo.lifecycle_changed_at < self.now - retry_after
            )
        return bool(stale_parts(repo, self.now))

    def _check_cancelled(self) -> None:
        """Cancellation check and heartbeat: called between units of work."""
        if self.job.heartbeat() in (SyncJob.Status.CANCELLED, None):
            raise JobCancelled()

    def _set_step(self, step: str, state: str) -> None:
        self.job.steps = {**self.job.steps, step: str(state)}
        self.job.save(update_fields=["steps", "updated_at"])

    def _update_metadata(self, **values: Any) -> None:
        self.job.metadata = {**self.job.metadata, **values}
        self.job.save(update_fields=["metadata", "updated_at"])


def _interacted_discoveries() -> Any:
    return CandidateDiscovery.objects.filter(candidate=OuterRef("pk"), source=INTERACTED)
