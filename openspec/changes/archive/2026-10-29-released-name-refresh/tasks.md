## 1. Queue released holders

- [x] 1.1 `lifecycle.release_name` returns the pks of the holders it renamed (empty list when none); update its docstring
- [x] 1.2 `backlog.queue_released(pks, now)`: return early without credentials (`has_app_credentials`) or with `CELERY_TASK_ALWAYS_EAGER`; select `pooled()` rows among `pks` not `IN_PROGRESS`, not FAILED, not queued since `lost_before(now)`; stamp `refresh_queued_at=now`; `transaction.on_commit` dispatches `sync_repository.delay(pk)` per row (lazy import)
- [x] 1.3 `storage.upsert_repository` passes `release_name`'s result to `backlog.queue_released` (check no import cycle: `services.repositories.backlog` ← `services.github.storage`)
- [x] 1.4 Update the module docstrings of `backlog.py` and `storage.py`

## 2. Tests

- [x] 2.1 Pooled RECOMMENDABLE holder released by a discovery search: stamped, one `sync_repository` dispatched after commit (`CELERY_TASK_ALWAYS_EAGER=False`, `delay` patched); `queue_batch` right after does not pick it
- [x] 2.2 Rolled-back transaction: no dispatch, no stamp
- [x] 2.3 Not queued: holder in no pool, in progress (claimed), FAILED, already queued within the window; eager mode; missing credentials
- [x] 2.4 Holder with a recent `refresh_failed_at` is still queued
- [x] 2.5 Existing released-name tests (`test_discovery_repository_data.py`, `test_job_fencing.py`) still pass unchanged

## 3. Checks and release

- [x] 3.1 `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`, `uv run mypy .`
- [x] 3.2 Archive the change (spec delta into `repository-analysis`); `ideas.md` moves §13 to Shipped
- [x] 3.3 Release housekeeping (CLAUDE.md §8): patch version bump, CHANGELOG, features.txt, README, CLAUDE.md roadmap entry
