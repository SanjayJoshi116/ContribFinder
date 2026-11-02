## Why

The review sweep's next module, `apps/backend/repositories/` (`Bug_Backlog.md` batch 38,
REPO-1…REPO-8), found two serious problems:
- The repository admin is fully editable. Staff can set `lifecycle` and `is_eligible`, edit
  languages, topics and dependencies without the row lock, and delete shared repositories along
  with other users' candidates, recommendations and saves.
- The app's own read-only admin still allows delete.

It also found that the refresh task:
- hides unexpected errors (no stack trace);
- retries inline with no backoff when tasks run eagerly;
- leaves repositories marked as queued when the broker refuses their task;
- can be queued twice when its rate-limit retries outlast the queued window.

The security review of the module found nothing.

## What Changes

- REPO-5, REPO-6, REPO-7: every repository admin is view-only. `ReadOnlyAdmin` builds on
  `core.admin.NoAddDeleteAdmin` with no change permission; `RepositoryAdmin` and
  `UserRepositoryAdmin` use it; the inlines cannot delete; lists select their related rows.
- REPO-1: a refresh that fails with `internal_error` (not a GitHub error) logs its traceback.
  The shared retry policy is unchanged: the refresh failure delay already retries it later.
- REPO-2: the refresh decides its attempt through `attempt_number(..., eager=...)`, like every
  other task, so an inline run never retries inline.
- REPO-3: a refresh task the broker refuses is logged and its repository is no longer marked
  queued; the other tasks of the batch are still sent.
- REPO-4: a refresh that schedules a retry renews its repository's queued time.
- REPO-8 (accepted): `/discovery/candidates` shows a released name (`owner/name~<id>`) and its
  old link until re-analysis. The SPA does not call it, the refresh is queued at once since
  0.12.36, and a fix needs a nullable `html_url` (contract change).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repository-analysis`: "Background refresh" (a scheduled retry renews the queued time; a task
  the broker refused does not count as queued).

The admin, logging and eager-mode changes change no specified behavior.

## Impact

- `apps/backend/repositories/{admin.py,tasks.py}`, `services/repositories/backlog.py` (helpers
  to renew or clear the queued time), tests.
- No migration, no API change (OpenAPI `1.0.0`), no frontend change, no ranking change.
