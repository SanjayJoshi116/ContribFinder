## Context

See proposal.md (Why) and `Bug_Backlog.md` batch 31. `data_deletion.delete_github_data` serves
delete-data, disconnect and account deletion (the last two inside `services/accounts._leave`,
one transaction that ends in `user.delete()` for account deletion); it purges the user's ETag
cache `on_commit`. A cancelled worker notices the cancel at its next `job_write`,
`save_progress` or heartbeat, so it can finish an in-flight GitHub request (and write its cache
entry) after the purge. The lock order is `services/locks.py`: job → developer profile →
dismissals/saves → recommendations → issues by pk → children. Search results are upserted with
`update_or_create` (row lock) in the same transaction that records the candidate.

## Goals / Non-Goals

**Goals:** close SVC-1…SVC-10, each with a test.

**Non-Goals:** a per-user cache generation key (scoping every ETag key by a value delete-data
bumps): it would close SVC-6 completely but touches every cache read and write in the GitHub
client; changing `_safe_detail`, audit retention after delete-data (spec: identifying audit
values go only with the account), or the lock order.

## Decisions

**D1 — Purge by id, twice.** `delete_github_data` reads `user_id = user.pk` first and every
purge uses it (SVC-1). After commit it purges at once and queues
`github.purge_user_cache(user_id)` with `countdown=SYNC_STALE_AFTER_SECONDS`: by then a cancelled
worker has either hit `JobCancelled` at a guarded write or is counted dead (SVC-6). The task
calls the same `purge_user_github_cache`; a broker error is logged (robust `on_commit`, as
revocation). Alternative: the cache-generation key (Non-Goals).

**D2 — Rerun after any end.** `run_tracked_job` gains `on_failed`, called once after a job ends
FAILED for good (not on a scheduled retry, not when cancelled), with the same error isolation as
`on_completed`. The generation task passes `rerun_recommendations_if_requested` to both. The flag
is cleared on claim, so a rerun that also fails starts nothing more unless requested again
(SVC-5). Alternative: one `on_finished(job, status)` hook — rejected, the existing
`on_completed` callers would all need a status check.

**D3 — Feedback under the lock.** `record` and `save` read the recommendation under its lock
(`select_for_update().select_related("scoring_config").filter(pk=...).first()`) and snapshot from
that row (SVC-7). An `opened_issue` event then locks its issue by pk; a missing issue stores no
event and returns False, as a missing recommendation does (SVC-2). Order: recommendation, then
issue, per `services/locks.py`.

**D4 — Orphan cleanup.** `_delete_orphans` first locks the candidate repositories
(`select_for_update`, `order_by("github_id")`, the order of every bulk repository lock, so it
never deadlocks with discovery's search), then runs the NOT EXISTS delete in a later statement, so
it sees links committed by writers that held those row locks; the count comes from `delete()`'s
per-model result (SVC-3, SVC-10). Writers that link a repository without its row lock still end
in a deferred FK error at commit: loud, rare, no data lost.

**D5 — Jobs.** `_end_jobs` locks `order_by("pk")` (SVC-4); `claim_job` reloads with `.first()`
and returns None when the job is gone, logged like a not-claimable job (SVC-8).

**D6 — Data versions.** `recommendations` also takes the newest `RecommendationFeedback.created_at`
among the user's `saved`, `unsaved`, `dismissed`, `undismissed` events (one aggregate; restore
records `undismissed`). Events are deleted with the GitHub data, so after delete-data the area is
null as before (SVC-9). `feedback.LIST_ACTIONS` names the four; a partial index
`feedback_list_change_idx (user, -created_at) WHERE action IN LIST_ACTIONS` (`feedback.0006`)
keeps the aggregate off the user's `viewed` events, since the SPA reads the versions on every
route change and focus.

## Risks / Trade-offs

- [The delayed purge needs a worker] → without Redis (eager mode) there is no shared ETag cache to
  purge; with Redis, a broker outage logs the failure and the entries expire within
  `GITHUB_ETAG_TTL`, as today.
- [A worker slower than `SYNC_STALE_AFTER_SECONDS` between guarded writes] → it is reclaimed as
  dead by then; a write after both purges is the remaining window, bounded by the TTL.
- [A failed generation's rerun fails again for the same cause] → at most one extra run per
  request; the flag never re-arms itself.
- [One more query per `/sync/versions`] → served by the partial index, never a scan of the
  user's view history.
