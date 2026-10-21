## Context

Recommendations are written by one place, `RecommendationService._persist`, and changed by
feedback actions in `services/feedback.py`: save, unsave, dismiss, restore and views. Both
work on the same rows: `Recommendation`, its `RecommendationReason` and `RecommendedIssue`
children, `SavedRepository` and `DismissedRepository`. Issue refreshes in
`services/repositories/analysis.py` delete `Issue` rows, and Django cascades those deletes to
`RecommendedIssue`.

Today each path takes locks in its own order:
- **Persist:** job row → reads dismissals (no lock) → locks matched `Issue` rows → locks the
  developer's `Recommendation` rows → deletes and recreates the children.
- **Dismiss:** inserts a dismissal → deletes the save → `recommendation.delete()`. Django's
  collector deletes the children first, then the parent.
- **Issue refresh:** `Issue...delete()`. The collector deletes `RecommendedIssue` first, then
  the issue.

Hence the deadlocks (D-3, D-4), the missed dismissal (D-2) and the hidden save (E-5).
Separately, `load_candidates` scores only RECOMMENDABLE repositories, so a staleness mark,
which changes no data, deletes recommendations (D-1).

Batch 4 made every generation write go through `job_write(job)`, and data deletion waits for
it. That gives a fixed first lock (the job row) to build one order on.

## Goals / Non-Goals

**Goals:**
- One lock order for everything that writes a developer's recommendations or feedback state.
  No deadlocks, no missed dismissals.
- Stale data stays recommendable. A staleness mark changes neither the result nor the ids.
- What is stored (score, signals, label, reasons, issues) always comes from one consistent set
  of inputs.
- A request for a generation that arrives during a run is never lost.
- No change to scores, ranking or the benchmark baselines.

**Non-Goals:**
- Eligibility re-checks on stored data (batch 7, R-12).
- Frontend query invalidation and retries (batch 9).
- Partial re-scoring: when issues change, the run ranks again from scratch.
- A history of past recommendations.

## Decisions

### D1. Scorable means eligible and analyzed, not "currently RECOMMENDABLE" (D-1, E-4)

`load_candidates` filters on `is_eligible=True` and `lifecycle__in=SCORABLE`, where
`lifecycle.SCORABLE = (RECOMMENDABLE, STALE, REFRESHING)`.

Why the eligibility filter is enough:
- Analysis sets `is_eligible` when it completes (`complete`) or fails (`fail`), and marking a
  repository stale or claiming it for a refresh keeps the flag.
- So a STALE or REFRESHING row is eligible exactly when it was RECOMMENDABLE before. A FAILED
  retry is claimed as REFRESHING but stays ineligible.
- FETCHING is left out: it is a first analysis, with no eligibility yet.

Alternative rejected: keep a copy of the last recommendable state per repository. That adds
state for what `is_eligible` already says.

Freshness (D7) stops treating "marked stale" as a pool change, so the sweep doesn't regenerate
for nothing.

### D2. One lock order, anchored on the developer profile row (D-2, D-3, D-4, E-5, E-7)

A new helper `services/locks.py: lock_developer(user_id) -> DeveloperProfile | None` runs
`select_for_update()` on the user's profile. It must be called inside a transaction. The order
is:

```
job row (job_write, generation only)
  → developer profile row
    → read dismissals / saves (now stable: their writers hold the profile lock)
      → Recommendation rows
        → Issue rows, ORDER BY pk
          → children (reasons, recommended issues): delete / create
```

Who takes the profile lock first:
- **Generation:** `_persist`, right after entering `job_write`.
- **Feedback:** `save`, `unsave`, `dismiss`, `restore`, and `record` for `viewed`.
- **Data deletion:** `delete_github_data`, before deleting the profile. The collector would
  otherwise delete recommendations before the profile row. Deletion already cancels jobs first,
  so this matters only against concurrent feedback requests.

Why this fixes D-2: dismiss and persist are serialized per developer. Persist reads
dismissals after taking the lock, so it sees every dismissal committed before it.

Why D-3 can't deadlock any more: neither path touches recommendation rows before it holds the
profile lock.

**Issues (D-4).** Persist locks the matched issues with `select_for_update().order_by("pk")`.
`_store_issues` first locks the issues it is about to delete, the same way, and only then
deletes them. Both therefore take an issue's lock before its `RecommendedIssue` rows. Two
persists of different users that share issues lock them in the same order.

**Alternatives rejected:**
- A PostgreSQL advisory lock keyed on the user id. It works, but it is another concept, and
  it bypasses the ORM and the test database helpers.
- Locking the `User` row. That row is also written by sign-in (`last_login`). The profile row
  exists whenever recommendations do.

**Cost.** Feedback requests for one developer wait while that developer's persist runs. That
is milliseconds to a few hundred milliseconds, and only on that one row.

### D3. Feedback under the lock (E-5, E-6, E-7)

- **`save`:** lock, then check `Recommendation.objects.filter(pk=rec.pk).exists()`.
  - Dismiss deletes the recommendation, and persist filters dismissals under the same lock. So
    "it still exists" also means "not dismissed".
  - When it is gone, raise `Recommendation.DoesNotExist`. The view maps that to the usual 404.
- **`dismiss`:** lock, create the dismissal, then delete the save. When a save was deleted,
  record `unsaved` (E-6). Then delete the recommendation by pk, a no-op if a regeneration
  already dropped it.
- **`record(viewed)`:** lock, then run the de-duplication query and insert (E-7). Other actions
  don't de-duplicate and don't lock.
- **`unsave`, `restore`:** lock. These change the state persist reads.

### D4. Dismissals before the cut (D-10)

- `score.rank` and `pipeline.rank_pool` accept `top_n: int | None` (`None` means no cut).
- Generation passes `None`. `_persist` drops dismissed repositories, cuts to
  `RECOMMENDATIONS_TOP_N`, then numbers the ranks.
- Evaluation keeps passing its `top_n`, so its metrics and baselines are unchanged.
- Cost: issue matching already ran for every candidate past the relevance gate. Only the
  in-memory list is longer.

### D5. Issues changed → rank again (D-6)

Under the lock, `_persist` checks that every matched issue of the kept repositories still
exists. If one doesn't, it raises the internal `IssuesChanged`. That leaves `job_write` and
rolls back.

`run()` then repeats the whole pipeline (load candidates and issues, rank, persist) at most
`MAX_ATTEMPTS = 3` times, with a heartbeat between attempts. After the third failure it raises
`PermanentJobError` with code `issues_changed`. The previous recommendations stay.

Alternatives rejected:
- Dropping the vanished issues and re-scoring only the affected repositories. That is a second
  scoring path, and the ranks of other repositories would be stale relative to them.
- Holding the issue locks during ranking. That would mean I/O and CPU under a lock, against
  the `job_write` rule.

Issue deletions are rare (issue refreshes run every 6 h), so a second attempt nearly always
succeeds.

### D6. A request during a run is remembered (D-5)

A new `SyncJob.rerun_requested` boolean (default false) is only meaningful for generation jobs.
It is a column, not a metadata key, because the generation rewrites `metadata` wholesale in
`save_progress`, which would erase a concurrently set key.

`start_recommendations(user)`:
- Calls `_start_job` as today.
- If it returned an existing job whose status is RUNNING, it runs
  `SyncJob.objects.filter(pk=job.pk, status=RUNNING).update(rerun_requested=True)`.
- If that updated no row (the job finished in between), it calls `_start_job` again, which
  creates a new job.
- A PENDING or RETRYING job needs nothing: it loads its inputs when it runs.

`generate_recommendations` passes an `on_completed` hook to `run_tracked_job`. The hook
re-reads `rerun_requested` and calls `start_recommendations(job.user)` when it is set.

Why this is race-free:
- The flag update and `finish_job` both write the job row, so PostgreSQL serializes them.
- If the update waits for the finish, it re-evaluates `status=RUNNING`, matches nothing, and
  the caller starts a new job.
- If the update commits first, the hook (which runs after COMPLETED is committed) sees the
  flag.

This covers restore and discovery completion (new pool members). Both go through
`start_recommendations`, so the freshness sweep needs no dismissal or new-candidate tracking.

### D7. Freshness: ignore staleness marks, include emptied pools (D-14)

- `pool_changed` becomes
  `Max("candidates__repository__lifecycle_changed_at", filter=~Q(candidates__repository__lifecycle__in=(STALE, REFRESHING)))`.
  - A repository that is currently STALE or REFRESHING carries its staleness-mark time, which
    says nothing new about its data.
  - A completed refresh moves it to RECOMMENDABLE or INDEXED with a new time. A failure moves it
    to FAILED. Both count.
- The profile filter becomes `Exists(candidates) | Exists(recommendations)`.
- A new due rule: the profile has recommendations and no candidates. After that generation
  stores nothing, the profile has neither, and it drops out of the sweep.

### D8. Export takes the scorable pool plus dismissals (E-4)

`load_candidates(profile, *, include_dismissed=False)`; `export_developer` passes `True`. With
D1 the export holds stale repositories too, so it no longer depends on sweep timing.

### D9. Save button disabled while pending (F-4)

`SaveButton` sets `disabled={save.isPending || unsave.isPending}`, as `DismissButton` already
does. One request at a time means the optimistic snapshot is always taken from settled state.

## Risks / Trade-offs

- **Old data on screen without app credentials.**
  - Without app credentials, STALE repositories are never refreshed, so they stay recommended
    on old stored data.
  - Before this change they silently disappeared instead, which is worse: stale is not gone.
  - Activity labels describe the stored snapshot ("Recently active" as of its capture), never
    health. Showing the capture time is batch 9's concern.
- **A missed generation after a quick staleness mark.**
  - A repository analyzed and then marked stale before any freshness run has its completion
    time hidden from freshness (D7).
  - Discovery completion starts a generation directly, so this needs a stale threshold shorter
    than the sweep interval. That doesn't happen with the defaults (hours versus 30 minutes).
- **A lost rerun flag.**
  - If a flagged run fails rather than completes, the flag is lost.
  - Mitigation: the next freshness sweep or user action. A failed generation is usually
    systemic, and a rerun would fail too.
- **More serialization.**
  - Feedback for one developer now waits for that developer's persist.
  - Profile analysis also writes the profile row, so it waits for a persist in progress. There
    is no cycle: analysis takes its own job row, then the profile, and touches no
    recommendation rows.
- **Three attempts then fail.**
  - Under constant issue churn, a generation could fail with `issues_changed`.
  - The previous result stays, and the next sweep retries.

## Migration Plan

- **Schema:** one migration adds `SyncJob.rerun_requested` (boolean, default false), with no
  backfill.
- **Deploy:** a generation already running at deploy has no flag and behaves as before.
- **Effect on stored recommendations:** after deploy, the first sweep regenerates nothing new
  from staleness marks. Recommendations of currently STALE repositories reappear at the next
  regeneration with new ids, once only.
- **Rollback:** revert the code. The column can stay, since it is ignored.

## Open Questions

None.
