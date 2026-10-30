## Context

`lifecycle.release_name(full_name, github_id)` runs inside the caller's transaction from
`storage.upsert_repository` (profile sync, discovery search, repository analysis). It renames each
holder to `{full_name}~{github_id}`, makes an eligible holder ineligible `name_released`, and moves
RECOMMENDABLE to INDEXED. `staleness.stale_parts` then reports its metadata stale, so
`mark_stale` (hourly) moves it to STALE and `queue_batch` (every 15 minutes) queues
`repositories.sync_repository`. Analysis already fetches metadata first for a released name and
falls back to `get_repository_by_id`. Only the trigger is slow.

## Goals / Non-Goals

**Goals:** queue the holder's refresh at commit; never queue it twice; never block or enlarge
the caller's transaction; keep the periodic path as the fallback.

**Non-Goals:** refreshing holders in no pool (the backlog never does); changing analysis,
staleness or eligibility; a new setting.

## Decisions

### D1. `release_name` returns the holders it renamed

`release_name(...) -> list[int]` (pks, possibly empty). `upsert_repository` ignores it today and
passes it to `backlog.queue_released(pks)` in the same place. Alternative: a post-save signal;
rejected, the rename is a `QuerySet.update` (no signal) and implicit dispatch is harder to test.

### D2. `backlog.queue_released(pks, now)` selects and stamps in the caller's transaction

Filters `pooled()` rows among `pks` that are not `IN_PROGRESS`, not FAILED, and not queued within
`lost_before(now)`; sets `refresh_queued_at=now` on them in one `update`, then registers
`transaction.on_commit` to dispatch `sync_repository.delay(pk)` for each. Stamping inside the
transaction means a rollback undoes the stamp and the dispatch together; `on_commit` means the
task never runs before the rename is visible. Rows are already locked by the rename `update`,
so no extra lock order is introduced. `refresh_failed_at` is ignored on purpose: the release is
new information, not a retry of the failed refresh.

Kind is always `all` (`sync_repository`): the analysis picks the stale parts, metadata first.

### D3. No dispatch without credentials or a worker

`queue_released` returns early (no stamp) when `not has_app_credentials()` (same gate as
`process_repository_backlog`) or `settings.CELERY_TASK_ALWAYS_EAGER`. Eager mode would run a
shared repository's GitHub analysis inside a user's sync or discovery commit hook; the periodic
task (or the next discovery analysis) covers it, as today. Tests of the dispatch use
`override_settings(CELERY_TASK_ALWAYS_EAGER=False)` and patch `delay`.

### D4. Dispatch lives with the tasks, imported lazily

`services/repositories/backlog.py` imports `repositories.tasks.sync_repository` inside the
`on_commit` callback (`# avoid import cycle`), as `services/github/accounts.py` does for
`revoke_replaced_token`. The task module stays a thin dispatcher.

## Risks / Trade-offs

- A burst of renames (e.g. an org transfer seen in one search page) queues one task per pooled
  holder. Bounded by the search page size and by the not-queued-twice stamp; each analysis is
  the same one the backlog would run an hour later.
- A holder whose analysis was in progress is not queued; its analysis either fetched metadata
  (resolves it) or raises `ClaimLost` on the changed name and restores the row, which then waits
  for the periodic task as today. Accepted: rare, and no worse than now.

## Migration Plan

None (no schema or setting). Rollback is a code revert.
