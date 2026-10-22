## 1. Keep-alive restarts (D1, P-1)

- [x] 1.1 `scripts/restarts.mjs`: pure `restartBudget({ max, windowMs })` with `allow(now)`.
  Tests in `scripts/restarts.test.mjs`: allows `max` within the window, refuses the next,
  allows again once old entries leave the window.
- [x] 1.2 `scripts/redis.mjs`:
  - `startKeepAlive()` spawns and records the session, and removes the old record when it
    exits;
  - a `stopping` flag set by `stop()`;
  - the `exit` handler restarts within the budget and logs the code in decimal and hex;
  - past the budget it logs the give-up message and exits 1.
- [x] 1.3 Manual: with `npm start` running, kill the keep-alive `wsl.exe` (its pid is in
  `.run/redis-*.json`). The runner logs and starts a new one, the stack stays up, and `.run/`
  holds the new pid. Then `npm run stop` stops everything and no keep-alive is restarted.

## 2. Line endings (D2, P-2)

- [x] 2.1 `.gitattributes`: `* text=auto eol=lf`. `git ls-files --eol` shows no `i/crlf`.
- [x] 2.2 On this checkout: rewrite the working files on a clean tree (as built: `git ls-files -z
  | xargs -0 rm -f && git checkout -- .`; `checkout-index` skipped clean-looking files), then
  `npm run format:check` in `apps/frontend` passes without `--end-of-line auto`.
- [x] 2.3 README (setup section): the one-time refresh for existing Windows checkouts.

## 3. Flaky frontend tests (D3, P-3)

- [x] 3.1 Run `src/app/app.test.tsx` and `src/features/feedback/feedback.test.tsx` 5 times with
  `--reporter=verbose` while the backend suite runs. Record the failing test names and errors.
- [x] 3.2 Fix each at its cause (wait for the element or the request count; no global timeout
  increase). Re-run 5 times under the same load: no failure. If nothing reproduced in 3.1,
  record the runs in P-3 and leave it open.

## 4. uv for api:sync (D4, P-4)

- [x] 4.1 `apps/frontend/package.json` `api:export` through `node ../../scripts/manage.mjs
  spectacular ...`.
- [x] 4.2 Run `npm run api:sync` with `uv` not on PATH. It succeeds, with no diff in
  `src/api`.

## 5. Lint and format scripts/ (D5, P-5)

- [x] 5.1 Move `apps/frontend/.prettierrc.json` to the repository root. `npm run format:check`
  in `apps/frontend` still passes.
- [x] 5.2 Root `eslint.config.mjs` (scripts only, Node globals). Root devDependencies
  `eslint`, `@eslint/js`, `globals`, `prettier` at the frontend's versions. Root scripts
  `lint:scripts`, `format:scripts`. `npm install` refreshes the lockfile.
- [x] 5.3 `prettier --write scripts`. Fix any lint errors. Both new scripts pass, and so does
  `npm run test:scripts`.
- [x] 5.4 `.github/workflows/ci.yml` (`api-contract`): root `npm ci`, `lint:scripts`,
  `format:scripts`; `cache-dependency-path` lists both lockfiles.
- [x] 5.5 `scripts/setup.mjs` already runs `npm ci` at the root. Confirm that it installs the
  new devDependencies.

## 6. Snapshot order and index (D6, Q-10, Q-11)

- [x] 6.1 `repositories/queries.py`: `SNAPSHOT_NEWEST_FIRST`, used by `latest_snapshot`,
  `repositories/api.py` and `services/repositories/analysis.py`. No other copy is left
  (`grep '"-captured_at", "-pk"'`).
- [x] 6.2 `RepositorySnapshot.Meta.indexes` → `(repository, -captured_at, -id)`, plus the
  migration (`makemigrations --settings config.settings.test`).
  `tests/test_seed_migrations.py` and the full suite pass.
- [x] 6.3 `EXPLAIN` the `latest_snapshot` prefetch query on the test database: the plan reads
  the new index and has no Sort under the window. Note the plan in the PR or commit message.
  As built: single-repository reads are index scan + limit; the prefetch keeps a bounded sort
  (bitmap scan for `= ANY`), see design D6.

## 7. Leftovers (D7, Q-12)

- [x] 7.1 Replace `_update_metadata` with `merge_metadata(self.job, {...})` in
  `services/github/sync.py` and `services/discovery/service.py`, and delete both methods.
- [x] 7.2 Test modules import the builders from `e2e.builders`. Drop the re-export and
  `__all__` from `tests/repo_fixtures.py`. The test count is unchanged.

## 8. Verification and housekeeping

- [x] 8.1 Backend `ruff check`, `ruff format --check`, `mypy`, `pytest`. Frontend lint,
  format:check, typecheck, test, build, `npm run e2e`. Root `test:scripts`, `lint:scripts`,
  `format:scripts`, `check:version`.
- [x] 8.2 `Bug_Backlog.md`:
  - mark P-1 (restart part), P-2, P-4, P-5, Q-10, Q-11, Q-12 `fixed (tooling-data-hygiene)`;
  - P-3 fixed, or still open with the runs recorded;
  - update the shipped line (batch 16, Q follow-ups) and name what is next.
- [x] 8.3 `ideas.md` §16: mark `.gitattributes`, the builder imports and the metadata write
  path shipped, and keep "stored activity" open. §15: mark lint `scripts/` shipped.
- [x] 8.4 CLAUDE.md:
  - §4: `restarts.mjs` and the root lint/format configs;
  - §6: `lint:scripts`, `format:scripts`, the keep-alive restart, and that the CRLF note in
    §7 is resolved;
  - §7: shipped entry.
- [x] 8.5 Release housekeeping (CLAUDE.md §8), patch release 0.12.11:
  - `VERSION`, the package files and lockfiles;
  - `CHANGELOG.md`, `features.txt`, README status line.
