## Context

Task sends today (`apps/backend`):

| Site | How | Broker refusal |
|---|---|---|
| `services/jobs._start_job` | `on_commit(lambda: task.delay(pk))` | raised after commit: 500 from `POST /sync`, restore; caught by `freshness` and `accounts.views._start_initial_sync` |
| `services/jobs._requeue` (recovery) | `.delay()` inline | raised: the run stops, later jobs wait a period |
| `services/github/accounts.queue_revocation` | `on_commit(..., robust=True)` | logged by Django |
| `services/data_deletion._purge` | `apply_async` inside a robust callback | logged by Django |
| `services/repositories/backlog` | `send_refreshes` in a robust callback | logged, refused rows unmarked |
| `jobs._finish_and_follow_up` | hook → `_start_job` | caught after commit, logged |

Final-failure logging: `run_tracked_job` warns without traceback for every code;
`revoke_later` logs a traceback for `internal_error` unless `OAuthError`, nothing otherwise;
`repositories.tasks._refresh` logs ERROR with traceback for `internal_error`, WARNING otherwise.

## Goals / Non-Goals

**Goals:**
- One place that sends a task and decides what a broker refusal means.
- One rule for final-failure log level and traceback.

**Non-Goals:**
- The backlog's sends (SIM-11): `send_refreshes` must unmark refused rows, which a generic helper
  cannot know. It already logs.
- Swallowing non-broker errors after commit. Robust `on_commit` would also hide an inline
  (eager) task's bug in tests and dev; only `_finish_and_follow_up` keeps its catch-all, as
  CLAUDE.md requires for hooks.
- Retry-path logging (still a warning with the exception type).

## Decisions

- **Catch `kombu.exceptions.OperationalError` only.** That is the broker refusal the existing
  sweeps already catch (CLAUDE.md "Sweeps that queue jobs per user catch only broker errors").
  A database error still fails the request or beat task. Alternative (catch `Exception`, as
  `robust=True`) would mask bugs; rejected.
- **`send` returns a bool, `after_commit` returns nothing.** Recovery counts what it sent;
  callers after commit cannot act on the outcome anyway.
- **Log the task name and a caller-given `about` string, never the arguments.** `revoke_later`
  takes ciphertext; logging it is pointless and widens exposure. The record keeps the traceback
  (`exc_info=True`) at WARNING: the work is safe, recovery covers it.
- **Recovery on refusal keeps the bumped `updated_at`.** The job is retried after one more
  waiting period, the same bound as a lost message; resetting it would make every run retry it
  against a down broker.
- **Callers that caught `BrokerError` from `start_*`:** `freshness.start_due_generations` drops
  its catch; `accounts.views._start_initial_sync` keeps its catch-all (sign-in must never fail
  for any reason). `created` from `start_*` still means "job created", whether sent or not.
- **`log_failure` in `services/errors.py`, not `services/github/retry.py`.** `retry.py` holds
  pure policy functions (CLAUDE.md §5); logging is a side effect. Signature
  `log_failure(logger, code, exc, message, *args, expected=())`; unexpected =
  `code == "internal_error" and not isinstance(exc, expected)`. `revoke_later` passes
  `expected=(OAuthError,)` and now also logs expected failures at WARNING (message only, no
  exception text).
- **Messages stay per caller** ("Job %s failed: %s", "Repository %s refresh failed: %s"),
  so existing log searches still match.

## Risks / Trade-offs

- [A refused `start_*` now looks successful to the caller] → the job is PENDING and recovery
  re-sends it within `SYNC_STALE_AFTER_SECONDS + GITHUB_MAX_RETRY_DELAY`; the status endpoint
  already shows PENDING. Same outcome as before, minus the 500.
- [Eager mode: an inline task's non-broker error after commit now propagates from
  `queue_revocation` / purge instead of being logged by Django] → both tasks catch their own
  errors; tests would surface a real bug, which is wanted.
- [Tracebacks from `run_tracked_job` could carry exception text] → only for `internal_error`,
  which is our own code's exception; log redaction (`core` logging filter) still applies.
