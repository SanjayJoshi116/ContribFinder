"""Recommendation generation (spec: recommendation-engine; design D7).

Stages run in memory on stored data: load → ``rank_pool`` (technologies → signals → issue
matching for candidates that pass the relevance gate → score → rank) → explain.
The result replaces the developer's recommendations in one transaction, upserted per
repository so ids survive regenerations. No GitHub or AI calls.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.conf import settings
from django.utils import timezone

from developers.models import DeveloperProfile
from feedback.models import DismissedRepository
from issues.models import Issue, RecommendedIssue
from jobs.models import SyncJob
from recommendations.models import (
    Recommendation,
    RecommendationReason,
    RepositorySize,
    ScoringConfig,
)
from services.errors import PermanentJobError
from services.job_guard import heartbeat, job_write, save_progress
from services.locks import lock_developer
from services.matching.features import DeveloperFeatures, load_candidates, load_developer
from services.matching.issues import load_issues
from services.matching.issues import snapshot as issue_snapshot
from services.matching.technologies import Tech

from . import config as scoring_config
from .explain import reasons
from .pipeline import rank_pool
from .score import Scored

STEP = "recommendations"
Step = SyncJob.StepState


class NotAnalyzed(PermanentJobError):
    code = "not_analyzed"


class NoScoringConfig(PermanentJobError):
    code = "no_scoring_config"


class IssuesKeepChanging(PermanentJobError):
    code = "issues_changed"


class IssuesChanged(Exception):
    """A matched issue was deleted or re-analyzed between ranking and storing: rank again
    (design D5)."""


# Rankings tried before a generation gives up on issues that keep disappearing.
MAX_ATTEMPTS = 3


def repository_size(contributors: int | None, thresholds: dict[str, int]) -> str:
    if contributors is None:
        return RepositorySize.UNKNOWN
    if contributors < thresholds["small"]:
        return RepositorySize.SMALL
    if contributors < thresholds["medium"]:
        return RepositorySize.MEDIUM
    return RepositorySize.LARGE


def technologies_json(techs: dict[str, Tech], dev: DeveloperFeatures) -> list[dict[str, Any]]:
    """Stored on the recommendation for filters and cards; most used first."""
    ordered = sorted(techs.values(), key=lambda t: (-t.weight, t.name.lower()))
    return [
        {
            "slug": t.slug,
            "name": t.name,
            "category": t.category,
            "matched": dev.confidence(t.slug) > 0,
        }
        for t in ordered
    ]


def active_config() -> ScoringConfig:
    config = ScoringConfig.objects.filter(is_active=True).first()
    if config is None:
        raise NoScoringConfig("No active scoring configuration")
    if errors := scoring_config.validate(config.weights, config.params, stored=True):
        raise NoScoringConfig(f"Active scoring configuration is invalid: {'; '.join(errors)}")
    return config


class RecommendationService:
    def __init__(self, job: SyncJob, now: datetime | None = None) -> None:
        self.job = job
        self._now = now

    def run(self) -> None:
        profile = DeveloperProfile.objects.filter(user=self.job.user).first()
        if profile is None:
            raise NotAnalyzed("No analyzed developer profile")
        config = active_config()
        # The reference time is taken before loading, so a repository refreshed while this
        # run works is newer than the result and the freshness sweep catches it.
        now = self._now or timezone.now()
        self._set_step(Step.RUNNING)
        try:
            dev = load_developer(profile)
            # Only matched issues can make an attempt fail, so candidates are loaded once.
            candidates = load_candidates(profile)
            for _ in range(MAX_ATTEMPTS):
                self._check_cancelled()
                # Uncut: dismissals made while ranking are dropped before the top N is taken.
                ranked = rank_pool(
                    dev,
                    candidates,
                    config.weights,
                    config.params,
                    lambda ids: load_issues(ids, now, settings.ISSUE_MAX_AGE_DAYS),
                    min_score=settings.RECOMMENDATION_MIN_SCORE,
                    top_n=None,
                )
                try:
                    kept = self._persist(profile, config, dev, ranked, now)
                    break
                except IssuesChanged:
                    continue
            else:
                raise IssuesKeepChanging(f"Matched issues changed during {MAX_ATTEMPTS} attempts")
        except Exception:
            self._set_step(Step.FAILED)
            raise
        labels: dict[str, int] = {}
        for s in kept:
            labels[s.label] = labels.get(s.label, 0) + 1
        self.job.metadata = {
            **self.job.metadata,
            "config_version": config.version,
            "candidates": len(candidates),
            "kept": len(kept),
            "label_counts": labels,
        }
        self.job.steps = {**self.job.steps, STEP: str(Step.DONE)}
        save_progress(self.job, metadata=self.job.metadata, steps=self.job.steps)

    def _persist(
        self,
        profile: DeveloperProfile,
        config: ScoringConfig,
        dev: DeveloperFeatures,
        ranked: list[Scored],
        now: datetime,
    ) -> list[Scored]:
        """Write the top N of ``ranked`` that the user has not dismissed (also while this run
        worked) and return them. Raises ``IssuesChanged``, writing nothing, when a matched
        issue no longer exists or was re-analyzed: every stored number and reason comes from
        the stored issues."""
        sizes = settings.REPO_SIZE_THRESHOLDS
        # A disconnect or deletion cancels the job; a cancelled run never replaces results.
        with job_write(self.job):
            # One lock order with feedback (services/locks.py): profile, then dismissals,
            # recommendations and issues. A dismiss committed before this point is seen.
            lock_developer(profile.user_id)
            dismissed = set(
                DismissedRepository.objects.filter(user_id=profile.user_id).values_list(
                    "repository_id", flat=True
                )
            )
            kept = [s for s in ranked if s.repo.id not in dismissed][
                : settings.RECOMMENDATIONS_TOP_N
            ]
            existing = {
                r.repository_id: r
                for r in Recommendation.objects.select_for_update().filter(developer=profile)
            }
            # Lock the matched issues so a concurrent issue refresh cannot change one before
            # commit; if one is already gone or re-analyzed, the scores and reasons came from
            # what is no longer stored: rank again.
            matched = {m.issue.id: m.issue.analyzed_at for s in kept for m in s.issues.issues}
            stored = dict(
                Issue.objects.select_for_update()
                .filter(pk__in=matched)
                .order_by("pk")
                .values_list("pk", "analyzed_at")
            )
            if stored != matched:
                raise IssuesChanged()
            to_create: list[Recommendation] = []
            to_update: list[Recommendation] = []
            for position, s in enumerate(kept, start=1):
                snapshot = s.repo.snapshot
                fields = {
                    "scoring_config": config,
                    "score": s.score,
                    "signal_scores": {name: signal.value for name, signal in s.signals.items()},
                    "rank": position,
                    "match_label": s.label,
                    "technologies": technologies_json(dict(s.techs), dev),
                    "activity_label": snapshot.activity_label if snapshot else "",
                    "size": repository_size(snapshot.contributors if snapshot else None, sizes),
                    **issue_snapshot(s.issues.issues),
                    "generated_at": now,
                }
                if (rec := existing.pop(s.repo.id, None)) is not None:
                    for name, value in fields.items():
                        setattr(rec, name, value)
                    to_update.append(rec)
                else:
                    to_create.append(
                        Recommendation(developer=profile, repository_id=s.repo.id, **fields)
                    )
            Recommendation.objects.filter(pk__in=[r.pk for r in existing.values()]).delete()
            if to_update:
                Recommendation.objects.bulk_update(
                    to_update,
                    [
                        "scoring_config",
                        "score",
                        "signal_scores",
                        "rank",
                        "match_label",
                        "technologies",
                        "activity_label",
                        "size",
                        "relevant_issue_count",
                        "issue_difficulties",
                        "issue_contribution_types",
                        "generated_at",
                    ],
                )
            created = Recommendation.objects.bulk_create(to_create)
            RecommendationReason.objects.filter(recommendation__developer=profile).delete()
            by_repo = {r.repository_id: r for r in [*to_update, *created]}
            RecommendationReason.objects.bulk_create(
                RecommendationReason(
                    recommendation=by_repo[s.repo.id],
                    type=reason.type,
                    text=reason.text,
                    weight=reason.weight,
                    detail=reason.detail,
                    position=index,
                )
                for s in kept
                for index, reason in enumerate(reasons(s.signals, config.weights, config.params))
            )
            RecommendedIssue.objects.filter(recommendation__developer=profile).delete()
            RecommendedIssue.objects.bulk_create(
                RecommendedIssue(
                    recommendation=by_repo[s.repo.id],
                    issue_id=matched_issue.issue.id,
                    rank=position,
                    score=matched_issue.score,
                    reasons=list(matched_issue.reasons),
                )
                for s in kept
                for position, matched_issue in enumerate(s.issues.issues, start=1)
            )
        return kept

    def _check_cancelled(self) -> None:
        heartbeat(self.job)  # raises JobCancelled when cancelled, deleted or reclaimed

    def _set_step(self, state: str) -> None:
        self.job.steps = {**self.job.steps, STEP: str(state)}
        save_progress(self.job, steps=self.job.steps)
