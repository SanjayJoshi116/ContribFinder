## Context

Findings and verdicts are in `Bug_Backlog.md` (RNK-1…RNK-10), each checked by reading the code
against the specs. Relevant facts:

- `freshness.due_profiles` is one ORM query of correlated subqueries; `failed_recently` matches
  any FAILED generation that completed within `RECOMMENDATION_FAILED_RETRY_MINUTES`.
- A completed generation writes `metadata["config_version"]` (`service.py`); the outdated-config
  test reads only `Recommendation.scoring_config`.
- `services.jobs._start_job` queues with `transaction.on_commit(lambda: task.delay(...))`. The
  beat sweep runs outside an outer transaction, so the callback runs as the inner `atomic` block
  exits and a broker error raises out of `start_recommendations`.
- `technologies.repository_technologies` keeps a slug found only by a source weighted 0 as
  `Tech(weight=0)`. `skill_match` filters `t.weight > 0`; `framework_match` does not.
- `v1-deterministic` and `v2-deterministic` weight topics 0.6, give every openness flag points
  above 0, and v2 weights both issue signals above 0. Benchmarks are scored through the same
  `rank_pool`.

## Goals / Non-Goals

**Goals:** the behavior in the spec deltas, with stored configurations scoring exactly as before
(`baselines.json` unchanged), and one computation of contributions per candidate.

**Non-Goals:** making `_start_job` robust for every job type (a web request that cannot queue
keeps failing loudly); storing an activation time on `ScoringConfig`; changing any configuration.

## Decisions

### D1. Latest-failure backoff (RNK-1)

`failed_recently` becomes "the latest finished generation (COMPLETED or FAILED, by
`completed_at`) is FAILED and completed within the delay": a subquery for the latest finished
job's status and time, compared in the `exclude`. Alternative: also require no COMPLETED job after
the failure (`~Exists(completed after)`); same result, one more subquery.

### D2. Config change read from the last generation (RNK-2)

Add `last_config = Subquery(last completed generation's metadata__config_version)` and mark due
when it is set and differs from the active version (`Q(last_config__isnull=False) &
~Q(last_config=active_version)`). Keep the `outdated_config` recommendation check (it covers
recommendations left from before a job recorded its version). A job without the key never makes
a developer due by this rule. Alternative: an `activated_at` field on `ScoringConfig` compared
with the last generation's start; rejected: needs a migration and a backfill, and the job
already records what it used.

### D3. Per-developer queuing failure (RNK-6)

`start_due_generations` wraps each `start_recommendations` in `try/except Exception`, logs with
`logger.exception` (user id only) and continues. The created job stays PENDING; job recovery
(`_requeue`) re-sends it. Alternative: `on_commit(..., robust=True)` in `_start_job`; rejected
for this change (Non-Goals): it changes every job start, including request paths.

### D4. Activation re-checks the candidate under the lock (RNK-5)

Inside the transaction, after locking every row, `ScoringConfig.objects.filter(version=version)
.exists()` false → `ActivationError("... no longer exists")`, before any update. The row lock
makes the later `update` count 1; an assertion is not needed.

### D5. Contributions computed once (RNK-7, RNK-8, RNK-10)

`Scored` gains `parts: Mapping[str, float]` (the `contributions` result `score_candidate` already
sums). `explain.reasons(signals, parts)` takes them; a reason needs `round(parts[name], 4) > 0`
and evidence. `weighted_score` is deleted; tests use `score_candidate` or `contributions` with
explicit params. `service.py` passes `s.parts`.

### D6. Signals (RNK-3, RNK-4, RNK-9)

- `framework_match` adds `t.weight > 0` to its filter.
- `contribution_openness` evidence lists flags with `points[key] > 0`; the value is unchanged
  (0-point flags add 0).
- `rank_pool` loads issues only when `params.get("issues")` and `weights.get("issue_fit", 0) > 0
  or weights.get("difficulty_fit", 0) > 0`; otherwise every candidate gets `NO_MATCH`.

## Risks / Trade-offs

- [D2 adds a JSON key lookup per profile to the sweep query] → one more correlated subquery on
  the indexed `(user, job_type)` jobs; the sweep runs every 30 minutes.
- [After activating a new config, every developer is due at once] → already true for developers
  with recommendations; the sweep coalesces, and `start_recommendations` skips active jobs.
- [Baselines move unexpectedly] → task runs `evaluate_ranking` and the baseline test; any
  movement stops the change.

## Migration Plan

No migration. Deploy and roll back as code only.
