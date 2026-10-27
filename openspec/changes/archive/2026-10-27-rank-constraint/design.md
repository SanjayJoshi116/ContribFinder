## Context

See proposal.md for why; requirements are in `specs/recommendation-engine` and
`specs/recommendation-feedback`.
- Writers: `RecommendationService._persist` (`services/ranking/service.py`) ranks recommendations
  and matched issues with `enumerate(..., start=1)`; `services.feedback.record` snapshots
  `recommendation.rank` or None.
- Columns: `Recommendation.rank` `PositiveIntegerField`, `RecommendedIssue.rank`
  `PositiveSmallIntegerField`, `RecommendationFeedback.rank` `PositiveIntegerField(null=True)`.
  Django's positive fields only add `>= 0` checks.
- Uniqueness: `Recommendation` is unique per (developer, repository) and `RecommendedIssue` has
  its own unique constraint; neither rank is unique, so shifting a group's ranks cannot collide.
- The feedback report counts `rank is None or rank < 1` as unattributed.

## Goals / Non-Goals

**Goals:**
- The database refuses rank 0 in all three tables.
- The upgrade never fails and never deletes data, whatever is stored.

**Non-Goals:**
- Making ranks contiguous or unique per developer (generation already writes 1..N; a constraint
  would make every regeneration order its writes).
- Changing the feedback report's `< 1` guard: harmless, and the evaluation spec still says "a
  rank below 1 counts as none".

## Decisions

**D1. `CheckConstraint` in `Meta.constraints`, one migration per app.**
- `recommendation_rank_positive` (`rank__gte=1`), `recommended_issue_rank_positive`
  (`rank__gte=1`), `feedback_rank_positive` (`Q(rank__isnull=True) | Q(rank__gte=1)`). Each
  migration: `RunPython(repair, noop)` then `AddConstraint`, so the constraint is added to clean
  data in the same migration.
- *Alternative:* a validator on the field. Rejected: `bulk_create`/`bulk_update` (how
  generation writes) skip model validation; only the database sees every writer.

**D2. Repair, never delete.**
- Events: `rank=0` → `rank=None`, the meaning the report already gives it.
- Recommendations: for each developer with a rank-0 row, `update(rank=F("rank") + 1)` on all of
  that developer's rows; matched issues likewise per recommendation. Order is kept and no row is
  lost; the next generation renumbers anyway.
- Repair functions use the historical models; the reverse is a no-op (the repaired values are
  valid either way).
- *Alternative:* delete rank-0 recommendations and let the sweep regenerate. Rejected: deletes
  user-visible state with no guarantee the sweep picks the developer up.

## Risks / Trade-offs

- [A table lock while the constraint validates] → Small tables (top N per developer); the check
  is one sequential scan.
- [A future writer that computes ranks from 0] → It fails loudly with an `IntegrityError` in
  tests instead of storing data the readers misread; that is the point.

## Migration Plan

- Deploy runs the three migrations (repair, then constraint). Rollback: migrate back; the reverse
  drops the constraints and leaves the repaired values.
