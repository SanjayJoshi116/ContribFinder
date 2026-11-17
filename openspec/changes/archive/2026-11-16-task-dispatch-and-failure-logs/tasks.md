## 1. Dispatch helper

- [x] 1.1 Add `services/dispatch.py` with `send(task, *args, about="", **options) -> bool` and
  `after_commit(task, *args, about="", **options)`; catch only `kombu` `OperationalError`, log
  task name and `about` with traceback at WARNING, never the arguments
- [x] 1.2 Unit tests: sent, refused (logged, False, no args in the record), non-broker error
  propagates, `after_commit` sends only on commit and not on rollback

## 2. Use it

- [x] 2.1 `services/jobs._start_job` → `after_commit`; `_requeue` → `send`, continue on refusal
- [x] 2.2 `_finish_and_follow_up`: drop the `BrokerError` branch, keep the post-commit catch-all
- [x] 2.3 `services/github/accounts.queue_revocation` and `services/data_deletion._purge` → helper
- [x] 2.4 `services/ranking/freshness.start_due_generations`: drop the `BrokerError` catch
- [x] 2.5 Tests: `POST /api/v1/profile/sync` and restore with a refusing broker (success, PENDING job,
  logged); recovery past a refused send; database error on start still raised; update
  `test_job_follow_up.py` and `test_recommendation_generation.py` expectations

## 3. Failure logging

- [x] 3.1 Add `log_failure` to `services/errors.py`
- [x] 3.2 Use it in `run_tracked_job`, `github/tasks.revoke_later` (`expected=(OAuthError,)`) and
  `repositories/tasks._refresh`
- [x] 3.3 Tests: level and traceback for `internal_error` vs a GitHub code vs `OAuthError`; no
  token in the revocation record

## 4. Checks

- [x] 4.1 `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`
- [x] 4.2 Confirm no remaining direct `.delay(` / `apply_async(` outside `services/dispatch.py`,
  the backlog and the legacy `revoke_replaced_token` (grep)

## 5. Docs and release

- [x] 5.1 ideas.md §15: move both ideas to Shipped (SIM-11 stays open); `Bug_Backlog.md` SIM-10 closed
- [x] 5.2 CLAUDE.md §4 (`services/dispatch.py`), §7 rules (send through `services/dispatch`;
  final failures through `log_failure`); CLAUDE_HISTORY.md entry
- [x] 5.3 Release housekeeping (CLAUDE.md §8): patch bump, CHANGELOG, features.txt, README version
  line, `npm run check:version`
