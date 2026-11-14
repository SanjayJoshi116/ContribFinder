"""Repository discovery run (FR-REPO-001/002, design D7).

Steps, persisted on the SyncJob and resumable like the profile sync:
``queries`` (plan from the profile) → ``search`` (run queries, pre-filter, record provenance)
→ ``interactions`` (contributed repositories) → ``pool`` (provenance pruning, not_code,
eligibility re-check, retention and size cap) → ``analysis`` (shared repository analysis of
the kept pool, planned once and capped per run). Searches use the developer's token;
repository endpoints use the same token with the shared ``public`` ETag scope.
"""

from __future__ import annotations

import logging
import queue
import threading
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from datetime import datetime, timedelta
from functools import cached_property
from typing import Any

from django.conf import settings
from django.db import connections
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
from services.github.storage import lock_for_upsert, replace_topics, upsert_repository
from services.job_guard import heartbeat, job_write, merge_metadata, save_progress
from services.repositories.analysis import Outcome, RepositoryAnalysisService
from services.repositories.lifecycle import IN_PROGRESS, recheck_eligibility
from services.repositories.staleness import stale_parts

from .filters import (
    NOT_CODE,
    FilterConfig,
    has_dependencies_annotation,
    prefilter,
    stored_not_code,
    stored_result_not_code,
)
from .ordering import pool_order
from .queries import (
    DiscoveryInput,
    InterestSignal,
    PlannedQuery,
    QueryConfig,
    SkillSignal,
    band_label,
    band_of,
    plan_queries,
    star_bands,
)

logger = logging.getLogger(__name__)

Step = SyncJob.StepState
STEPS = ("queries", "search", "interactions", "pool", "analysis")
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
                self._set_step(step, Step.RUNNING)  # raises JobCancelled unless RUNNING
                try:
                    outcome = getattr(self, f"_step_{step}")()
                except Exception:
                    self._set_step(step, Step.FAILED)
                    raise
                self._set_step(step, outcome)

    # --- steps ------------------------------------------------------------------------

    def _step_queries(self) -> str:
        plan = plan_queries(self._input(), QueryConfig.from_settings())
        merge_metadata(self.job, {"plan": [q.as_json() for q in plan]})
        return Step.DONE

    def _step_search(self) -> str:
        if "search_started_at" not in self.job.metadata:
            # Every record this run writes is seen at or after this; the pool step prunes the
            # developer's older ones (queries that no longer find the repository).
            merge_metadata(self.job, {"search_started_at": self.now.isoformat()})
        plan = [PlannedQuery(**q) for q in self.job.metadata.get("plan", [])]
        if not plan:
            return Step.SKIPPED
        meta = self.job.metadata
        done: list[str] = list(meta.get("queries_done", []))
        skipped: list[str] = list(meta.get("queries_skipped", []))
        rejections: Counter[str] = Counter(meta.get("rejections", {}))
        found = int(meta.get("results_found", 0))
        # Per query key: strategy, band and what its results became (design D2). No query text.
        yields: dict[str, dict[str, Any]] = dict(meta.get("query_yield", {}))
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
                yields[query.key] = {"source": query.source, "band": query.band, "refused": True}
                merge_metadata(self.job, {"queries_skipped": skipped, "query_yield": yields})
                continue
            rejected: Counter[str] = Counter()
            recorded = 0
            kept: list[tuple[int, GitHubRepo]] = []
            for rank, gh in enumerate(results, start=1):
                reason = prefilter(gh, login=login, owned=owned, now=self.now, cfg=cfg)
                if reason:
                    rejected[reason] += 1
                else:
                    kept.append((rank, gh))
            with job_write(self.job):
                # GitHub ID order: concurrent runs storing overlapping results lock the shared
                # rows (and the rows holding their names) in the same order and never deadlock.
                lock_for_upsert([gh for _, gh in kept])
                for rank, gh in sorted(kept, key=lambda item: item[1].github_id):
                    repo = self._store_search_result(gh)
                    if stored_result_not_code(gh, repo, cfg):
                        rejected[NOT_CODE] += 1  # an analysis already found it is a list
                        continue
                    self._record(repo, query.source, query.core, rank)
                    recorded += 1
                found += len(results)
                rejections.update(rejected)
                done.append(query.key)
                yields[query.key] = {
                    "source": query.source,
                    "band": query.band,
                    "results": len(results),
                    "rejections": dict(rejected),
                    "recorded": recorded,
                }
                merge_metadata(
                    self.job,
                    {
                        "queries_done": done,
                        "rejections": dict(rejections),
                        "results_found": found,
                        "query_yield": yields,
                    },
                )
        return Step.DONE

    def _step_interactions(self) -> str:
        owned, login, cfg = self._owned(), self._login(), FilterConfig.from_settings()
        rejections: Counter[str] = Counter(self.job.metadata.get("rejections", {}))
        added = 0
        contributed = (
            Repository.objects.filter(
                user_links__user=self.user,
                user_links__relation=UserRepository.Relation.CONTRIBUTOR,
            )
            .distinct()
            .annotate(has_dependencies=has_dependencies_annotation())
            .prefetch_related("topics")
        )
        with job_write(self.job):
            for repo in contributed:
                reason = prefilter(
                    repo, login=login, owned=owned, now=self.now, cfg=cfg, check_stars=False
                )
                if reason:
                    rejections[reason] += 1
                    continue
                self._record(repo, INTERACTED, "", None)
                added += 1
        merge_metadata(self.job, {"rejections": dict(rejections), "interactions_added": added})
        return Step.DONE

    def _step_analysis(self) -> str:
        if "analysis_plan" not in self.job.metadata:
            # Chosen once: a resumed step finishes this choice, never takes the next ones.
            pending = [r for r in self._pool_repositories() if self._needs_analysis(r)]
            cap = settings.DISCOVERY_MAX_ANALYSES_PER_RUN
            merge_metadata(
                self.job,
                {
                    "analysis_plan": [r.pk for r in pending[:cap]],
                    "analysis_total": len(pending),
                    "analysis_capped": len(pending) > cap,
                },
            )
        done: list[int] = list(self.job.metadata.get("analyzed", []))
        outcomes: Counter[str] = Counter(self.job.metadata.get("analysis_outcomes", {}))
        # Kept by id so a resumed step still knows which analyses decided something (D1).
        succeeded: list[int] = list(self.job.metadata.get("analysis_succeeded", []))
        todo = [pk for pk in self.job.metadata["analysis_plan"] if pk not in done]
        for repo_id, outcome in self._analyze(todo):
            outcomes[outcome] += 1
            done.append(repo_id)
            if outcome == Outcome.ANALYZED:
                succeeded.append(repo_id)
            merge_metadata(
                self.job,
                {
                    "analyzed": done,
                    "analysis_outcomes": dict(outcomes),
                    "analysis_succeeded": succeeded,
                },
            )
        # A list this run's analysis found not to be code leaves the pool now, not at the next
        # run's pool step (spec "Candidate pool maintenance"). Fenced like the pool step.
        with job_write(self.job):
            pool = RepositoryCandidate.objects.filter(developer=self.profile)
            removed = self._remove_not_code(pool, succeeded) if succeeded else 0
        self._record_pool({"analysis_not_code": removed})
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
        # Fenced like every job write of user data: a cancelled or reclaimed run stops here.
        with job_write(self.job):
            pruned = self._prune_discoveries()
            expired, _ = pool.filter(last_seen_at__lt=cutoff).delete()
            # Re-checked including the lists removed next: their shared row becomes ineligible.
            pooled_ids = list(pool.values_list("repository_id", flat=True))
            not_code_removed = self._remove_not_code(pool, pooled_ids)
            eligibility_changed = recheck_eligibility(pooled_ids, now=self.now)
            evicted = 0
            if len(pooled_ids) - not_code_removed > settings.DISCOVERY_MAX_POOL:
                # Keep the candidates first in the pool order, which the analysis step
                # follows, so the kept pool is the one that gets analyzed.
                keep = list(
                    pool_order(pool).values_list("pk", flat=True)[: settings.DISCOVERY_MAX_POOL]
                )
                evicted, _ = pool.exclude(pk__in=keep).delete()
        self._record_pool(
            {
                "pool_pruned_discoveries": pruned,
                "pool_expired": expired,
                "pool_not_code": not_code_removed,
                "pool_eligibility_changed": eligibility_changed,
                "pool_evicted": evicted,
            }
        )
        return Step.DONE

    # --- helpers ------------------------------------------------------------------------

    def _record_pool(self, extra: dict[str, Any]) -> None:
        """Record ``extra`` with the pool's current size and band counts (design D2): after the
        pool step and again after the cleanup that ends the analysis step."""
        stars = list(
            RepositoryCandidate.objects.filter(developer=self.profile).values_list(
                "repository__stars", flat=True
            )
        )
        merge_metadata(
            self.job, {**extra, "pool_size": len(stars), "pool_bands": _band_counts(stars)}
        )

    def _prune_discoveries(self) -> int:
        """Delete the developer's discovery records this run did not see again: a rank from a
        query that no longer finds the repository must not order the pool. Candidates stay
        (retention removes them). A run that searched nothing (no plan) proves nothing about
        the old records, and a query GitHub rejected this run keeps its records."""
        started = self._search_started()
        if started is None or self.job.steps.get("search") == Step.SKIPPED:
            return 0
        skipped = set(self.job.metadata.get("queries_skipped", []))
        kept_queries = {q["core"] for q in self.job.metadata.get("plan", []) if q["key"] in skipped}
        deleted, _ = (
            CandidateDiscovery.objects.filter(
                candidate__developer=self.profile, last_seen_at__lt=started
            )
            .exclude(query__in=kept_queries)
            .delete()
        )
        return deleted

    def _remove_not_code(self, pool: Any, repo_ids: list[int]) -> int:
        """Re-check ``not_code`` on stored data for the whole pool (spec: "Candidate pool
        maintenance"): a list found before the rule, or analyzed recently, leaves the pool now.
        Only candidates are removed here; the shared repository's eligibility changes through
        the lifecycle re-check. Returns the removals."""
        cfg = FilterConfig.from_settings()
        repos = (
            Repository.objects.filter(pk__in=repo_ids)
            .annotate(has_dependencies=has_dependencies_annotation())
            .prefetch_related("topics")
        )
        flagged = [repo.pk for repo in repos if stored_not_code(repo, cfg)]
        if not flagged:
            return 0
        # delete() also counts the cascaded discovery records; report candidates only (U-3).
        _, per_model = pool.filter(repository_id__in=flagged).delete()
        removed: int = per_model.get(RepositoryCandidate._meta.label, 0)
        logger.info("Discovery for user %s removed %d not_code candidates", self.user.pk, removed)
        return removed

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
        # A search result carries no languages: it is not a metadata fetch.
        repo = upsert_repository(gh, self.now, metadata_fetched=False)
        replace_topics(repo.pk, gh.topics)
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
            previous = discovery.search_rank
            if (
                discovery.last_seen_at >= self._seen_since
                and rank is not None
                and previous is not None
            ):
                # The same query in another band this run, also in an earlier attempt (stars
                # changed between requests): keep the better rank, never the band order.
                rank = min(rank, previous)
            CandidateDiscovery.objects.filter(pk=discovery.pk).update(
                search_rank=rank, last_seen_at=self.now
            )

    @cached_property
    def _seen_since(self) -> datetime:
        """ "Seen this run" for ``_record``, read once: the search start (written before any
        record), or the attempt's clock for a run from before the key existed."""
        return self._search_started() or self.now

    def _search_started(self) -> datetime | None:
        """When this run's search started: the one boundary of "seen this run" (``_record``,
        pruning). None before the search step (or for a run from before the key existed)."""
        started = self.job.metadata.get("search_started_at")
        return datetime.fromisoformat(started) if started else None

    def _pool_repositories(self) -> list[Repository]:
        """The developer's candidate repositories in the pool order (ordering.py)."""
        candidates = pool_order(
            RepositoryCandidate.objects.filter(developer=self.profile).select_related("repository")
        )
        return [c.repository for c in candidates]

    def _needs_analysis(self, repo: Repository) -> bool:
        if repo.lifecycle in IN_PROGRESS:
            return False  # another run holds it; the candidate counts as awaiting analysis
        if repo.lifecycle in (Lifecycle.DISCOVERED, Lifecycle.STALE):
            return True
        if repo.lifecycle == Lifecycle.FAILED:
            retry_after = timedelta(hours=settings.REPO_FAILED_RETRY_HOURS)
            return repo.lifecycle_changed_at < self.now - retry_after
        return bool(stale_parts(repo, self.now))

    def _check_cancelled(self) -> None:
        """Cancellation check and heartbeat: called between units of work."""
        heartbeat(self.job)  # raises JobCancelled when cancelled, deleted or reclaimed

    def _set_step(self, step: str, state: str) -> None:
        self.job.steps = {**self.job.steps, step: str(state)}
        save_progress(self.job, steps=self.job.steps)


def _band_counts(stars: Iterable[int]) -> dict[str, int]:
    """Pool candidates per star band (design D3), by current stars: in the band whose range
    holds them; ``below`` under the lowest band (previously interacted repositories);
    ``other`` in no band (a gap between bands, or above a closed last band), present only
    when non-zero."""
    bands = star_bands()
    counts = dict.fromkeys(["below", *(band_label(b) for b in bands)], 0)
    for value in stars:
        band = band_of(value, bands)
        if band is not None:
            label = band_label(band)
        elif value < bands[0][0]:
            label = "below"
        else:
            label = "other"
        counts[label] = counts.get(label, 0) + 1
    return counts
