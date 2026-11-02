## 1. Admin

- [x] 1.1 REPO-5, REPO-6, REPO-7: `ReadOnlyAdmin` on `NoAddDeleteAdmin`; `RepositoryAdmin`, `UserRepositoryAdmin` on it; inlines `can_delete = False`; `list_select_related` (D1); tests: add, change and delete refused on every repository admin, changelist query counts flat

## 2. Refresh task

- [x] 2.1 REPO-1, REPO-2: `attempt_number(..., eager=)` and a traceback for `internal_error` (D2); tests: an eager rate limit records a failure without retrying; an unexpected error is logged with its traceback and recorded as `internal_error`
- [x] 2.2 REPO-4: `backlog.mark_queued`; a scheduled retry renews `refresh_queued_at` (D3); test: the stamp moves forward on retry
- [x] 2.3 REPO-3: `backlog.unmark_queued`; the backlog task sends each refresh, clears the stamp of refused ones and returns the number sent (D3); test: the broker refuses the second of three, only it is unmarked

## 3. Backlog

- [x] 3.1 `Bug_Backlog.md` batch 38 "Sweep: `repositories/`": REPO-1…REPO-8 with verdicts (REPO-8 accepted); sweep table row ticked

## 4. Checks

- [x] 4.1 Backend `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`, `uv run mypy .`, `makemigrations --check --settings config.settings.test`

## 5. Release

- [x] 5.1 `/simplify`, then `/code-review` on the fix diff; record and fix (skipped by the owner, 2026-11-02)
- [x] 5.2 Archive (delta into `repository-analysis`); release housekeeping (CLAUDE.md §8, 0.12.50); commit only when the owner says so
