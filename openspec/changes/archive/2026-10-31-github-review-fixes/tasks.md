## 1. Delete-data service

- [x] 1.1 GH-3: `services/accounts.delete_github_data(user, request)`, `@transaction.atomic` around `data_deletion.delete_github_data` and the `github_data_deleted` audit entry (D1); `GitHubDataView.delete` calls it
- [x] 1.2 Test: a failing audit write leaves the user's GitHub data in place and records no entry; the success path still returns 204 with the entry

## 2. Revocation task

- [x] 2.1 GH-5: `revoke_later` decides with `REVOCATION_ATTEMPTS` as the attempt count under `CELERY_TASK_ALWAYS_EAGER` (D3)
- [x] 2.2 GH-1: `logger.exception` for errors that are not a `GitHubError`, before `record_revocation_failure` (D4)
- [x] 2.3 Tests: eager transient failure records `github_unavailable` once with no retry; non-eager still retries; an unexpected error logs its traceback, records `internal_error`, and the plaintext token appears in no log record

## 3. Admins and repository list

- [x] 3.1 GH-2: `GitHubAccountAdmin`, `GitHubProfileAdmin` without add and delete permissions; GH-8: `list_select_related = ("user",)` on both
- [x] 3.2 GH-7: drop `.distinct()` from `RepositoryListView.get_queryset`
- [x] 3.3 GH-4: `RepositoryPagination.max_page_size` from `max(100, GITHUB_SYNC_MAX_REPOS)` (D2)
- [x] 3.4 GH-4: `useRepositories` follows `next` and returns every result with the first page's `count`; update the doc comment
- [x] 3.5 Tests: admin add/delete refused and changelist query count independent of rows; repository list unchanged without `distinct` (one row per owned repository, contributors excluded); page size 200 honoured with the cap at 200; frontend test that two pages are merged

## 4. Checks

- [x] 4.1 Backend `uv run pytest`, `ruff check`, `ruff format --check`, `mypy`; frontend `test`, `lint`, `typecheck`, `format:check`, `build` (no e2e: no browser-flow change)

## 5. Release (workflow steps 6-8)

- [x] 5.1 `/simplify`, then `/code-review` on the fix diff; record and fix
- [x] 5.2 Archive (deltas into `data-controls`, `sync-jobs`); `Bug_Backlog.md` batch 29 rows marked fixed (GH-6 accepted); ACC-17 noted as superseded by GH-5
- [x] 5.3 Release housekeeping (CLAUDE.md §8)
