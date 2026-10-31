## 1. Data deletion

- [x] 1.1 SVC-1: `delete_github_data` captures `user_id` before anything else; every purge uses it (D1); test: account deletion purges the deleted user's `github:etag:<id>:*` keys
- [x] 1.2 SVC-6: task `github.purge_user_cache(user_id)` queued on commit with `countdown=SYNC_STALE_AFTER_SECONDS`, robust (D1); test: queued with the id and countdown, a broker error never fails the deletion
- [x] 1.3 SVC-3, SVC-10: `_delete_orphans` locks candidates in GitHub ID order, then deletes the orphans and counts from `delete()` (D4); test: count matches the deleted rows, a repository still referenced is kept

## 2. Jobs

- [x] 2.1 SVC-4: `_end_jobs` locks in pk order (D5)
- [x] 2.2 SVC-8: `claim_job` returns None when the job is gone after the claim (D5); test
- [x] 2.3 SVC-5: `run_tracked_job(..., on_failed=)` after a final failure only; generation passes `rerun_recommendations_if_requested` to both hooks (D2); test: a rerun requested on a running generation that fails starts one more generation; a retry or cancel starts none

## 3. Feedback and versions

- [x] 3.1 SVC-7: `record` and `save` snapshot from the row read under the lock (D3); test: a rank changed after loading is the stored rank
- [x] 3.2 SVC-2: `opened_issue` locks its issue after the recommendation; a gone issue stores no event (D3); test
- [x] 3.3 SVC-9: `versions()` `recommendations` includes the latest save/unsave/dismiss/restore event (D6); test: a dismissal after the last generation moves it, and the spec scenario

## 4. Checks

- [x] 4.1 Backend `uv run pytest`, `ruff check`, `ruff format --check`, `mypy`; `npm run api:sync` shows no drift (no API shape change); no frontend or e2e change

## 5. Release (workflow steps 6-8)

- [x] 5.1 `/simplify`, then `/code-review` on the fix diff; record and fix
- [x] 5.2 Archive (deltas into `recommendation-engine`, `sync-jobs`); `Bug_Backlog.md` batch 31 rows marked fixed
- [x] 5.3 Release housekeeping (CLAUDE.md §8); commit only when the owner says so
