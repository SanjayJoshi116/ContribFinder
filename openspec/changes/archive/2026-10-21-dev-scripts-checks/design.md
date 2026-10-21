## Context

**Runners.** `npm start` (`scripts/start.mjs`) runs `node scripts/{redis,backend,worker,beat,frontend}.mjs`
under `concurrently`, with relative script paths, and sets `CF_STACK_PID` so each runner
(`child.mjs` `watchStack`) stops its tree when the stack process disappears. `npm run stop`
(`scripts/stop.mjs`) lists every process (CIM on Windows, `ps` elsewhere) and keeps:
- `node` whose command line matches `scripts/(start|backend|worker|beat|redis).mjs`, with no
  repository check (G-1);
- `node` Vite and Python/Celery whose command line contains the repository path.

`redis.mjs` spawns a `detached` `wsl.exe … sleep infinity` keep-alive (detached on purpose,
CLAUDE.md §6 "Known issues"). It handles SIGINT and SIGTERM only, and `stop.mjs` never matches
`wsl` (G-2). `child.mjs` calls `process.kill(-pid)` unguarded and has no spawn `error` handler
(G-3). `wait-port.mjs` uses `net.connect` without a socket timeout (G-4). `beat.mjs` keeps its
schedule at `os.tmpdir()/contribfinder-celerybeat-schedule` (G-7).

**Checks.** `core/checks.py` registers grouped checks (`core.E0xy`: 01x profiling, 02x
discovery/repository, 03x recommendation, 04x issues; `core.W00n`). `core.E020` is the shared
"must be a positive integer" id. `core/startup.py` turns errors into a startup failure in
production. The settings listed in the proposal (H-7) have no check.

**Seeds.** `0002` seeds v1 with `is_active = not exists(active)`. That check also counts v1, so
re-applying after a rollback deactivates v1 (H-11). `0003` deactivates every active config,
then activates v2 (H-10). A partial unique constraint allows at most one active config;
nothing enforces at least one.

## Goals / Non-Goals

**Goals:**
- Stop scope proven by process identity (recorded pid plus a matching executable and command
  line), not by script names alone.
- Pure, unit-testable helpers for the parts of the scripts that decide something (process
  matching, schedule file name, lockfile versions). Node's built-in test runner, no new
  dependency.
- Seeds that are idempotent in both directions and never override a non-seed choice.

**Non-Goals:**
- Process supervision beyond what exists (no restart on crash, no daemon).
- Re-running data migrations on existing databases: a database already past `0003` keeps its
  current active config.
- Checks for settings that have only a choice of strings (log level) or that Django validates
  itself.

## Decisions

**D1. Runners record themselves in `.run/` (G-1, G-2).** A new `child.mjs` helper
`recordProcess(name, pid = process.pid)` writes `.run/<name>-<pid>.json` (`{ pid, name, exe,
startedAt }`) at the repository root and removes it on exit. Every runner calls it for itself,
and `redis.mjs` also calls it for the keep-alive `wsl.exe`. `stop.mjs` then:
- for each record, kills the pid only when the live process still has the recorded executable
  and, for runners, a command line matching the runner pattern (the keep-alive must match
  `sleep infinity`); otherwise it deletes the stale record;
- keeps today's repository-path match for Python/Celery and Vite (their command lines carry
  the path);
- no longer matches node runners by command line alone.

*Alternatives.* Launching runners by absolute path and requiring the repository path in the
command line misses runners started by `npm run backend` and friends (npm passes the relative
script). Matching `wsl.exe sleep infinity` by text would also kill another project's keep-alive.

**D2. Console close (G-2, G-3).** `redis.mjs` adds `SIGHUP` to its stop signals, like
`runChild`. `runChild` wraps the group kill in try/catch (ESRCH means already gone) and adds a
child `error` handler that prints `Could not start <cmd>: <message>` and exits 1. Windows
delivers console close to Node as SIGHUP, so the same handler covers it.

**D3. Port wait (G-4).** Each attempt sets `socket.setTimeout(remaining)` and on `timeout`
destroys the socket with an error, which goes through the existing retry/deadline path.

**D4. Beat schedule (G-7).** `contribfinder-celerybeat-<sha1(root)[:8]>` in the OS temp dir.
The name stays out of the repository, so a stale schedule never shows in `git status`.

**D5. CI and setup (G-8, G-10).** `cancel-in-progress: ${{ github.event_name == 'pull_request' }}`.
Setup runs `npm ci` at the root and in `apps/frontend` (root first: `start.mjs` needs
`concurrently`). `setup.mjs` itself imports only Node built-ins and `uv.mjs`, so it runs before
any install.

**D6. Version check (G-9).** `check-version.mjs` reads both `version` and `packages[""].version`
of each lockfile and reports the failing entry by path (`package-lock.json packages[""]`).

**D7. New checks (H-7).** Reuse the positive-integer loop (`core.E020`) for the integer
settings, add non-negative where 0 is meaningful (`SYNC_COOLDOWN_SECONDS`, `REPO_DISCOVERED_GRACE_MINUTES`), and positive
numbers for the float timeouts (`GITHUB_HTTP_TIMEOUT`, `REDIS_SOCKET_TIMEOUT`): `core.E050`
(non-negative integer) and `core.E051` (positive number) for the new sync/job/GitHub group,
and `core.E014` for `EXPERIENCE_THRESHOLDS`:
- keys must be the known signals (the defaults' keys);
- each value must be a pair of non-negative numbers with the intermediate threshold not above
  the experienced one.

**D8. Seeds (H-10, H-11).**
- `0002 seed`: `is_active` only when no config *other than v1* is active. An existing v1 keeps
  its flag unless that rule activates it.
- `0003 seed`: activate v2 (and deactivate v1) only when nothing outside {v1, v2} is active;
  otherwise create or update v2 inactive.
- Unseeds stay as they are, since they already keep one active.

Migrations are edited in place: RunPython code is not recorded in the database, so existing
databases are unaffected and fresh ones get the corrected logic. A test runs `MigrationExecutor`
backwards to `0001` and forwards again, with and without v1 recommendations and with an operator
config active, and asserts one active config after each step.

**D9. Privacy and deletion (H-19).** Comparing the page text with the deletion code across two
languages is brittle. Instead:
- *Backend.* A test walks every model with a foreign key (direct or through the developer
  profile) to `User` and asserts each is either removed by `delete_github_data` or on an
  explicit kept list: account, GitHub connection, audit events. A new user-linked model then
  fails the test until it is classified.
- *Privacy page.* The same test maps each of those models to a category and asserts
  `PrivacyPage.tsx` names it (read as source; CI checks out both apps).

**D10. Task results (H-20).** `CELERY_TASK_IGNORE_RESULT = True` in `base.py`. The result
backend setting stays (harmless, and eager `.get()` in `test_celery` does not use it).

## Risks / Trade-offs

- [A runner killed with SIGKILL leaves its record] → `stop.mjs` treats a record whose pid is dead
  or mismatched as stale and deletes it; `start.mjs` prunes stale records at launch.
- [pid reuse with the same executable (another `node` that happens to run a runner script)] →
  The command-line match on the runner pattern plus the pid makes a false match require both
  reuse and an identical script name, which is far narrower than today.
- [New checks reject an existing local `.env`] → Checks only fail on values that would break at
  run time; defaults pass. `runserver` and `pytest` run the same checks, so a bad local value
  shows at once with the setting named, rather than as a loop or a failed analysis later.
- [Edited migrations differ from what older databases ran] → They only change behavior on
  re-application or on databases with an operator config, which is exactly the bug being fixed.

## Migration Plan

No data migration. Deploy as usual. Developers run `npm run stop` once with the old script if a
stack is running, since runners started before the change have no records.
