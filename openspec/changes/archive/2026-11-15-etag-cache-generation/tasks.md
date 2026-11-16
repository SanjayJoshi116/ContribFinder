## 1. Model

- [x] 1.1 `User.github_cache_generation` and migration `accounts/0006`.

## 2. Deletion

- [x] 2.1 `delete_github_data` bumps the generation in its transaction; `_purge_later` removed (D4).
- [x] 2.2 `github.purge_user_cache` kept for queued messages, docstring says so.

## 3. Client

- [x] 3.1 `for_user` reads token and generation in one query; user-scope clients carry it (D2).
- [x] 3.2 After an ETag `cache.set`, re-read the generation; changed or user gone → delete the key (D1, D3).

## 4. Tests

- [x] 4.1 Write after deletion committed: entry removed. Write by a current client: entry kept.
- [x] 4.2 Account deletion (user gone): entry removed. Public scope: no generation query.
- [x] 4.3 Deletion bumps the generation; no second purge queued (replaces the old test).
- [x] 4.4 Verify failure logged, not raised.

## 5. Checks and release

- [x] 5.1 `uv run pytest`, `ruff check`, `ruff format --check`, `mypy`; `npm run api:sync` shows no drift.
- [x] 5.2 `Bug_Backlog.md`: SVC-16 fixed, SVC-6 and SVC-15 updated, open-items line. `/simplify` (batch 73) and fix-diff `/code-review` (batch 74) of the uncommitted change, all findings fixed or recorded.
- [x] 5.3 Archive; release housekeeping (CLAUDE.md §8, 0.12.76). Commit only when the owner says so.
