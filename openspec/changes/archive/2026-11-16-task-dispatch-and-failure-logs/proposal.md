## Why

Celery tasks are sent three different ways (ideas.md §15, "One dispatch after commit helper").
`queue_revocation` and the data-deletion cache purge send after commit and log a broker refusal;
`_start_job` sends after commit but lets the refusal escape; job recovery calls `.delay()`
directly. The escaping case is user-visible: with Redis down, `POST /api/v1/profile/sync` and a restore of
a dismissed repository answer 500 although the job or the restore is already committed (job
recovery re-sends the PENDING job later). One recovery run stops at the first refused send.

Failure logging differs the same way (ideas.md §15, "One traceback rule", `Bug_Backlog.md`
SIM-10): the revocation and repository refresh tasks keep the traceback of an unexpected error,
but `run_tracked_job` logs every final failure as a one-line warning, so a bug in sync, analysis,
discovery or generation loses its stack.

## What Changes

- New `services/dispatch.py`: `send(task, *args, ...)` sends a task and logs a broker refusal
  (returns whether it was sent); `after_commit(task, *args, ...)` does the same once the caller's
  transaction commits. Errors other than a broker refusal still propagate.
- `_start_job`, job recovery (`_requeue`), `queue_revocation` and the data-deletion purge retry
  send through it. A refused start leaves the PENDING job for recovery; recovery logs a refused
  job and continues with the next.
- `freshness.start_due_generations` drops its own `BrokerError` catch (now unreachable);
  `_finish_and_follow_up` drops its broker branch, keeps the catch for inline (eager) errors.
- New `log_failure(logger, code, exc, message, *args, expected=())` in `services/errors.py`:
  `internal_error` (and not an `expected` type) logs at ERROR with traceback, anything else at
  WARNING without. Used by `run_tracked_job`, `revoke_later` and the repository refresh.
- No API, schema, ranking or migration change. Patch release.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `sync-jobs`: adds "A refused task send never fails committed work" and "Unexpected job
  failures keep their traceback".

## Impact

- New `apps/backend/services/dispatch.py`; edits in `services/jobs.py`,
  `services/github/accounts.py`, `services/data_deletion.py`, `services/ranking/freshness.py`,
  `services/errors.py`, `github/tasks.py`, `repositories/tasks.py`.
- Tests adjusted: `tests/test_job_follow_up.py` (broker refusal message),
  `tests/test_recommendation_generation.py` (sweep past a refused send); new tests for the helper,
  the sync/restore endpoints with a refusing broker, recovery continuing, and the log levels.
- `backlog.queue_released` / `send_refreshes` unchanged: they already log, and unmark refused
  refreshes (SIM-11 stays open).
- CLAUDE.md §7 rule: send tasks through `services/dispatch`.
