## 1. Seed command

- [x] 1.1 SEED-1: `E2E_DATABASE`; `handle` refuses any other default database before creating, migrating or deleting (D1); test: the guard raises, and `config.settings.e2e` uses `E2E_DATABASE`
- [x] 1.2 SEED-4: `CREATE DATABASE` with `connection.ops.quote_name`
- [x] 1.3 SEED-5, SEED-6: `seed() -> dict[str, str]` (D3); `_reset` also deletes sessions and audit entries; test: `seed()` twice, returned keys match the users, the first run's users, sessions and audit entries are gone
- [x] 1.4 SEED-2: `MUTATING_USERS`, `READ_USERS`, `--attempts` from Playwright's `RETRIES`; mutating users seeded as `<user>`, `<user>-retry<n>` (D2); test: every key is seeded with a working session
- [x] 1.5 SEED-10: snapshot `days_since_push` from `repo.pushed_at`

## 2. Jobs and builders

- [x] 2.1 SEED-8: `services.jobs.new_job(user, job_type)`; `_start_job` and the seed use it
- [x] 2.2 SEED-7: `_run` finishes with `finish_job(..., steps=...)` once and raises `CommandError` on False; test: a job that cannot be finished fails the seed
- [x] 2.3 SEED-3: `add_candidate` advances `last_seen_at` (D5); test: a second, later discovery moves the candidate's `last_seen_at`, and `discovery_seen` later than `seen` leaves the candidate no older than its record
- [x] 2.4 SEED-9: `make_issue -> Issue`, module-level import

## 3. Browser tests

- [x] 3.1 SEED-2: `signInAs` picks the session for `test.info().retry` for mutating users on a retry and fails naming the user and attempt when missing; `SeededUser` lists the new users
- [x] 3.2 SEED-2: `dashboard.spec.ts` signs in per test (save `e2e-save`, dismiss `e2e-dismiss`, reads `e2e-dashboard`)

## 4. Checks

- [x] 4.1 Backend `uv run pytest`, `ruff check`, `ruff format --check`, `mypy`; frontend `test`, `lint`, `typecheck`, `format:check`, `build`; `npm run e2e` (the seed and fixtures change)

## 5. Release (workflow steps 6-8)

- [x] 5.1 `/simplify`, then `/code-review` on the fix diff; record and fix
- [x] 5.2 Archive (delta into `web-client`); `Bug_Backlog.md` batch 30 rows marked fixed; security-review box ticked (no findings)
- [x] 5.3 Release housekeeping (CLAUDE.md §8); commit only when the owner says so
