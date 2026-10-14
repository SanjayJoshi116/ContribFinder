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
from django.db import transaction
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
from services.github.sync import JobCancelled
from services.matching.features import DeveloperFeatures, load_candidates, load_developer
from services.matching.issues import MatchedIssue, load_issues
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
            candidates = load_candidates(profile)
            self._check_cancelled()
            kept = rank_pool(
                dev,
                candidates,
                config.weights,
                config.params,
                lambda ids: load_issues(ids, now, settings.ISSUE_MAX_AGE_DAYS),
                min_score=settings.RECOMMENDATION_MIN_SCORE,
                top_n=settings.RECOMMENDATIONS_TOP_N,
            )
            kept = self._persist(profile, config, dev, kept, now)
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
        self.job.save(update_fields=["metadata", "steps", "updated_at"])

    def _persist(
        self,
        profile: DeveloperProfile,
        config: ScoringConfig,
        dev: DeveloperFeatures,
        kept: list[Scored],
        now: datetime,
    ) -> list[Scored]:
        """Write the result and return what was kept after dropping repositories dismissed
        while this run worked."""
        sizes = settings.REPO_SIZE_THRESHOLDS
        with transaction.atomic():
            # A disconnect cancels the job; re-check under lock so a cancelled run never
            # replaces the previous results.
            status = (
                SyncJob.objects.select_for_update()
                .filter(pk=self.job.pk)
                .values_list("status", flat=True)
                .first()
            )
            if status != SyncJob.Status.RUNNING:
                raise JobCancelled()
            dismissed = set(
                DismissedRepository.objects.filter(user_id=profile.user_id).values_list(
                    "repository_id", flat=True
                )
            )
            kept = [s for s in kept if s.repo.id not in dismissed]
            # Lock the matched issues so a concurrent issue refresh cannot delete one before
            # commit; one it already deleted is dropped.
            alive = set(
                Issue.objects.select_for_update()
                .filter(pk__in=[m.issue.id for s in kept for m in s.issues.issues])
                .values_list("pk", flat=True)
            )
            issues: dict[int, list[MatchedIssue]] = {
                s.repo.id: [m for m in s.issues.issues if m.issue.id in alive] for s in kept
            }
            existing = {
                r.repository_id: r
                for r in Recommendation.objects.select_for_update().filter(developer=profile)
            }
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
                    **issue_snapshot(issues[s.repo.id]),
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
                    issue_id=matched.issue.id,
                    rank=position,
                    score=matched.score,
                    reasons=list(matched.reasons),
                )
                for s in kept
                for position, matched in enumerate(issues[s.repo.id], start=1)
            )
        return kept

    def _check_cancelled(self) -> None:
        if self.job.heartbeat() in (SyncJob.Status.CANCELLED, None):
            raise JobCancelled()

    def _set_step(self, state: str) -> None:
        self.job.steps = {**self.job.steps, STEP: str(state)}
        self.job.save(update_fields=["steps", "updated_at"])
