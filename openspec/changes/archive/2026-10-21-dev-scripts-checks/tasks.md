## 1. Runner records and stop scope (D1, G-1, G-2)

- [x] 1.1 `scripts/child.mjs`: `recordProcess(name, pid = process.pid, exe = 'node')` writes
  `.run/<name>-<pid>.json` (`{ pid, name, exe, startedAt }`) under the repository root and
  removes it on exit; `readRecords()` and `removeRecord(file)` for `stop.mjs`.
- [x] 1.2 Every runner (`start`, `backend`, `worker`, `beat`, `frontend`, `redis`) records
  itself; `redis.mjs` also records the keep-alive `wsl.exe` (`exe: 'wsl'`).
- [x] 1.3 `stop.mjs`: kill recorded pids whose live process still has the recorded executable
  and a matching command line (runner pattern, or `sleep infinity` for the keep-alive); delete
  stale records. Keep the repository-path match for Python/Celery and Vite; drop the node runner
  match by command line alone. Move the matching into a pure function (`matchStack(processes,
  records, repo)`) exported for tests.
- [x] 1.4 `start.mjs` prunes stale records at launch.
- [x] 1.5 `.gitignore`: `.run/`.
- [x] 1.6 Tests (`node --test "scripts/*.test.mjs"`): another checkout's runner is not matched; a reused pid
  with a different executable or command line is not matched and its record is reported stale;
  the keep-alive record is matched; Python and Vite of this repository still match.

## 2. Console close, spawn errors, port wait (D2, D3, G-2, G-3, G-4)

- [x] 2.1 `redis.mjs`: stop on `SIGHUP` too.
- [x] 2.2 `child.mjs` `runChild`: guard `process.kill(-pid, signal)` (already gone is fine); on
  child `error` print `Could not start <cmd>: <message>` and exit 1.
- [x] 2.3 `wait-port.mjs`: per-attempt `socket.setTimeout(remaining)`, `timeout` destroys the
  socket with an error so the deadline path reports it. Test against a listening port, a closed
  port and a non-routable address with a short deadline.
- [x] 2.4 Manual: close the `npm start` console window; no `node`, `python`, `celery` or the
  keep-alive `wsl.exe` of this repository remains (CLAUDE.md §6 testing note: launch through
  WMI).

## 3. Beat schedule, CI, setup, version check (D4, D5, D6, G-7, G-8, G-9, G-10)

- [x] 3.1 `beat.mjs`: schedule file `contribfinder-celerybeat-<sha1(root)[:8]>` via an exported
  `scheduleFile(root)`; test that two roots give two names.
- [x] 3.2 `.github/workflows/ci.yml`: `cancel-in-progress: ${{ github.event_name ==
  'pull_request' }}`; add an `npm run test:scripts` step to an existing Node job.
- [x] 3.3 `setup.mjs`: `npm ci` at the root, then in `apps/frontend`.
- [x] 3.4 `check-version.mjs`: compare `packages[""].version` of both lockfiles too, naming the
  entry on failure; export the comparison for a test with a half-updated lockfile.
- [x] 3.5 Root `package.json`: `test:scripts` runs `node --test "scripts/*.test.mjs"`.

## 4. Configuration checks (D7, H-7)

- [x] 4.1 `core/checks.py` new group `sync_github_config_check`:
  - positive integers (`core.E020`): `SYNC_MAX_ATTEMPTS`, `SYNC_STALE_AFTER_SECONDS`,
    `JOB_RECOVERY_INTERVAL_SECONDS`, `GITHUB_SYNC_MAX_REPOS`, `GITHUB_MAX_PAGES`,
    `GITHUB_MAX_RETRY_DELAY`, `GITHUB_ETAG_TTL`, `GITHUB_MANIFEST_MAX_REPOS`,
    `GITHUB_MANIFEST_MAX_BYTES`, `GITHUB_CONTRIB_MAX_PRS`, `GITHUB_CONTRIB_MAX_REPOS`,
    `OAUTH_STATE_MAX_PENDING`, `OAUTH_STATE_TTL_SECONDS`,
    `REPO_FAILED_RETRY_HOURS`, `REPEATED_CONTRIBUTION_MIN_PRS`, `DISCOVERY_ANALYSIS_CONCURRENCY`,
    `SESSION_COOKIE_AGE`;
  - non-negative integer (`core.E050`): `SYNC_COOLDOWN_SECONDS`, `REPO_DISCOVERED_GRACE_MINUTES`
    (0 means no cooldown, no grace);
  - positive number (`core.E051`): `GITHUB_HTTP_TIMEOUT`, `REDIS_SOCKET_TIMEOUT`.
- [x] 4.2 `core.E014` `EXPERIENCE_THRESHOLDS`: known signals only, each a pair of non-negative
  numbers, intermediate ≤ experienced.
- [x] 4.3 Tests: each new id fires for a bad value (0, negative, string, wrong shape, reversed
  pair) and the default settings pass; production startup refuses
  `JOB_RECOVERY_INTERVAL_SECONDS=0`.

## 5. Scoring config seeds (D8, H-10, H-11)

- [x] 5.1 `0002_seed_v1_deterministic.seed`: activate v1 only when no config other than v1 is
  active; never change an existing v1's flag otherwise.
- [x] 5.2 `0003_seed_v2_deterministic.seed`: activate v2 (deactivating v1) only when no config
  outside {v1, v2} is active; otherwise store v2 inactive.
- [x] 5.3 Tests with `MigrationExecutor` (new `tests/test_seed_migrations.py`): fresh migrate → v2
  active; back to `0001` and forward again, with and without v1 recommendations → exactly one
  active after each step that leaves a configuration (seed functions called directly, plus one
  real `MigrationExecutor` round trip), v2 active at the end; an operator config active before `0003` stays
  active and v2 is stored inactive.

## 6. Deletion coverage and privacy page (D9, H-19)

- [x] 6.1 Backend test (`tests/test_privacy_coverage.py`): every model linked to `User` (directly,
  one-to-one, or by cascade through a deleted model) is either removed by `delete_github_data`
  or on the kept list (`User`, `GitHubAccount`, `AuditEvent`, Django admin log).
- [x] 6.2 Same test: every category those models map to is named on the privacy page
  (`PrivacyPage.tsx`, read as source), so no separate frontend test is needed.

## 7. Celery results (D10, H-20)

- [x] 7.1 `base.py`: `CELERY_TASK_IGNORE_RESULT = True`; `test_celery` still passes.

## 8. Verification and housekeeping

- [x] 8.1 Backend `ruff`, `mypy`, `pytest`; frontend lint, typecheck, test; `npm run
  test:scripts`; `npm run check:version`.
- [x] 8.2 Manual: two checkouts (or a worktree) running `npm start`; `npm run stop` in one leaves
  the other running; both beats use different schedule files.
- [x] 8.3 `Bug_Backlog.md`: mark G-1…G-4, G-7…G-10, H-7, H-10, H-11, H-19, H-20 `fixed
  (dev-scripts-checks)`, update the shipped line (batch 10) and name the next batch.
- [x] 8.4 README and CLAUDE.md §6: stop scope (recorded processes, `.run/`), console close,
  `npm run test:scripts`.
- [x] 8.5 Release housekeeping (CLAUDE.md §8), patch release 0.12.9: `VERSION`, package files
  and lockfiles, `CHANGELOG.md`, `features.txt`, README status, CLAUDE.md §4 layout and §7 entry.
