## Why

A repository that gives up its name to another GitHub ID (`lifecycle.release_name`) becomes
ineligible `name_released` and drops out of recommendations. Today it only comes back once the
hourly `mark_stale_repositories` sweep moves it to STALE and the 15-minute backlog queues it, so
the gap can last more than an hour. Queuing its refresh when the name is released closes the gap
to minutes (`ideas.md` §13). No ranking change: the same analysis runs, only sooner.

## What Changes

- When storing a repository makes pooled holders give up the name, the system queues a refresh
  of each such holder once the storing transaction commits, and stamps it as queued so the
  periodic backlog does not queue it twice.
- Holders that are in progress, FAILED, already queued, or in no developer's pool are left to the
  existing paths (their running analysis, the FAILED retry, the queued task, nothing).
- Without app client credentials, or when tasks run inline (no worker), nothing is queued: the
  periodic background refresh stays the fallback, and a user's sync or discovery never runs a
  shared repository's analysis inline.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repository-analysis`: "Background refresh" gains the immediate refresh of a repository that
  gave up its name.

## Impact

- `services/repositories/lifecycle.py` (`release_name` returns the holders it changed),
  `services/repositories/backlog.py` (new `queue_released`), `repositories/tasks.py` (dispatch).
- Callers of `upsert_repository` (sync, discovery search, analysis) are unchanged.
- No migration, setting, API or frontend change; no ranking change, baselines cannot move.
