## Context

See proposal.md for why.
- Steps: queries → search → interactions → pool → analysis (`DISCOVERY_STEPS`). The pool step
  (`_step_pool`, `services/discovery/service.py`) runs inside `job_write`: prunes discovery
  records, removes expired candidates, removes `not_code` candidates (`_remove_not_code(pool,
  repo_ids)`, which reads `stored_not_code` with `has_dependencies_annotation()` and prefetched
  topics), re-checks eligibility, applies the cap, then records `pool_not_code`, `pool_size` and
  `pool_bands` (`_band_counts`).
- The analysis step plans once (`analysis_plan`), analyzes through `RepositoryAnalysisService`
  (concurrent threads possible), and records `analyzed` and `analysis_outcomes` per repository
  with `merge_metadata`. A completed analysis decides a suspected list's eligibility
  (`lifecycle.complete` → ineligible `not_code` when it has no manifest dependency).
- Discovery status and the candidate list compute pool counts from the database at request time.

## Goals / Non-Goals

**Goals:**
- A list found by this run's analysis leaves the pool before the run ends.
- One definition of the recorded pool summary, used after the pool step and after the cleanup.

**Non-Goals:**
- Refilling the freed slots in the same run (the next run's search does; a second search would
  spend budget).
- A new job step: step names are shown by the status endpoint and the profile page.
- Changing the `not_code` rule (K-4, `ideas.md` §11 "by content").

## Decisions

**D1. Cleanup at the end of `_step_analysis`, fenced by `job_write`.**
- After the loop, inside `job_write(self.job)`: `_remove_not_code(pool, ids)` with `ids` = the
  run's `analyzed` repositories whose outcome was `analyzed` (a FAILED or SKIPPED analysis decided
  nothing new; a reclaimed repository belongs to another analysis).
- Outcomes are recorded per repository today only as counts, so the step keeps the analyzed ids
  per outcome locally while it loops and stores the ids of `analyzed` ones in the metadata
  (`analysis_succeeded`), so a resumed step still knows them.
- `_remove_not_code` already re-reads the stored rows (topics, dependencies), so it sees what the
  analysis just stored.
- *Alternative:* a sixth step `cleanup`. Rejected: changes the step list the status endpoint,
  profile page and tests know, for a few deletes.
- *Alternative:* remove each list as its analysis completes (in the worker thread). Rejected: the
  workers do not hold the job's fence, and pool writes belong to the job thread.

**D2. One pool summary helper.**
- `_record_pool(extra)` computes `pool_size` and `pool_bands` from the current pool and merges
  them with `extra` (`pool_*` counters after the pool step; `analysis_not_code` after the
  cleanup). Both places call it, so the summary cannot drift.

**D3. Metadata.**
- `analysis_not_code`: removals after analysis (0 when none); `pool_not_code` keeps meaning
  removals by the pool step. `pool_size` / `pool_bands` are overwritten with the final pool.

## Risks / Trade-offs

- [A freed slot stays empty until the next run] → Acceptable: the removed repository was
  already ineligible, so recommendations do not change; only counts and the candidate list do.
- [A resumed analysis step after a crash between the loop and the cleanup] → The cleanup reads
  `analysis_succeeded` from the metadata and is idempotent (removing an absent candidate is a
  no-op).

## Migration Plan

- No migration or setting. Runs after the upgrade clean up; earlier lists leave at their next
  pool step as before.
- Rollback: revert the release.
