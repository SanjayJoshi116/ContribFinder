## Context

See proposal.md (Why). Repository rows are shared across users. Their lifecycle and eligibility
change only in `services/repositories/lifecycle.py`, and the language and dependency rows only
under the repository row lock. `backlog.queue_batch` and `queue_released` stamp
`refresh_queued_at`. `_not_queued(now)` treats a stamp newer than `lost_before(now)` as still
queued. `services.github.retry.attempt_number` is the one "eager = last attempt" rule.

## Goals / Non-Goals

**Goals:** staff cannot change repository data from the admin; refresh failures are visible
and never hot-loop; the queued stamp reflects whether a task can still run.

**Non-Goals:** retrying database errors (a change to the shared retry policy for every task);
REPO-8 (accepted); claiming a repository at queue time.

## Decisions

### D1. Admin (REPO-5, REPO-6, REPO-7)

`ReadOnlyAdmin[M](NoAddDeleteAdmin[M])` with `has_change_permission` False, the same shape as
`developers.admin.ReadOnlyAdmin`. A shared base in `core/admin.py` is tempting, but two
three-line classes keep each app's docstring next to its reason. `/simplify` may merge them later.
`RepositoryAdmin` and `UserRepositoryAdmin` move to it. The inlines get `can_delete = False`.
They need no `readonly_fields`: no change permission makes them read-only. `list_select_related`:
`("user", "repository")` for `UserRepository`, `("repository",)` for snapshots, and
`("developer", "repository")` for candidates. `DeveloperProfile.__str__` uses only `user_id`.

### D2. Refresh decision (REPO-1, REPO-2)

`attempt = attempt_number(task.request.retries + 1, settings.SYNC_MAX_ATTEMPTS,
eager=bool(task.request.is_eager))`, then `decide_retry(exc, attempt, ...)`. On `Fail`:
`logger.exception(...)` for `internal_error`, else `logger.warning(...)` as now (GitHub failures
are expected). This matches `revoke_later`.

### D3. Queued time follows the task (REPO-3, REPO-4)

`backlog.mark_queued(ids, now)` (re-stamp) and `backlog.unmark_queued(ids)` (clear) update
`refresh_queued_at` with a plain filtered `UPDATE`. They take no row lock: the stamp is
advisory, and the claim token still fences the analysis.
- `process_repository_backlog`: try each `.delay()`; collect the ids whose send raised; log once
  with the count; `unmark_queued(failed)`. The return value counts the tasks sent.
- `_refresh` on `Retry`: `mark_queued([repo_id], timezone.now())` before `task.retry(...)`.

Alternative: send on commit with a robust handler, as `queue_released` does. Rejected:
`queue_batch` has already committed when the task loops, and a robust handler would still leave
the stamp in place.

## Risks / Trade-offs

- [The stamp clear races a refresh that was actually delivered despite an error] → the claim
  token makes a duplicate a no-op (`SKIPPED`); at worst one extra fetch.
- [`logger.exception` for every internal error is noisy if a bug repeats hourly] → that noise
  is the point: it was silent before.
