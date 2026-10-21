## Why

Batch 10 of `Bug_Backlog.md` (rows G-1…G-4, G-7…G-10, H-7, H-10, H-11, H-19, H-20, re-verified
against the code on 2026-10-21). The local runners, setup and CI, the configuration checks and
the scoring-config seed migrations each have a gap that bites in normal use:
- `npm run stop` can kill another project's runners;
- closing the console leaves WSL and Redis awake;
- a port wait can overshoot its deadline by the OS connect timeout;
- two checkouts share one Celery beat schedule;
- a quick second push to `main` cancels the first commit's CI run;
- a half-updated lockfile passes the version check;
- setup can leave a lockfile diff that CI does not reproduce;
- a bad sync or GitHub cap (an interval of 0, a scalar threshold) passes the startup checks and
  fails later, in a hot loop or in every analysis;
- the v2 seed migration replaces whatever configuration is active, and re-applying the v1 seed
  can leave none active.

None of this changes ranking, so it does not wait for K-1. It is the next batch after 9.

## What Changes

- **The local stack stops only itself (G-1, G-2, G-3).**
  - Runners record their own process ids in a gitignored folder of the repository. `npm run
    stop` kills only recorded processes (after checking they still look like our runners) plus
    Python and Vite processes whose command line names this repository.
  - The WSL keep-alive that holds Redis awake is recorded too, and is stopped when the console
    closes (SIGHUP) or by `npm run stop`.
  - A child that already exited, or a runner whose program cannot be started, ends with a
    message instead of an uncaught exception.
- **Waits keep their deadline (G-4).** Each connection attempt of the port wait times out within
  the remaining time, so an unreachable host fails at the documented deadline.
- **One beat schedule per checkout (G-7).** The schedule file name includes a hash of the
  repository path.
- **CI checks every commit on `main` (G-8).** A newer run cancels an older one only on pull
  requests.
- **Version check covers the whole lockfile (G-9).** `packages[""].version` of both
  `package-lock.json` files must match `VERSION` too.
- **Setup installs what CI installs (G-10).** `npm run setup` runs `npm ci` at the root and in
  `apps/frontend`, so it never rewrites a lockfile.
- **Startup checks cover the remaining settings (H-7).** Sync and job settings
  (`SYNC_MAX_ATTEMPTS`, `SYNC_COOLDOWN_SECONDS`, `SYNC_STALE_AFTER_SECONDS`,
  `JOB_RECOVERY_INTERVAL_SECONDS`), GitHub caps and timeouts, OAuth state limits, repository
  grace and retry windows, `DISCOVERY_ANALYSIS_CONCURRENCY`, `REPEATED_CONTRIBUTION_MIN_PRS`,
  `SESSION_COOKIE_AGE`, `REDIS_SOCKET_TIMEOUT`, and the shape and order of
  `EXPERIENCE_THRESHOLDS`.
- **Seeding never overrides an operator's choice (H-10, H-11).**
  - The v2 seed becomes active only when no configuration other than v1 is active; otherwise
    it is stored inactive.
  - Re-applying the v1 seed after a rollback never deactivates v1 itself, so exactly one
    configuration stays active through any forward or backward migration.
- **Tests for what was untested (H-19).** Migrating the seeds backwards and forwards, and the
  privacy page listing exactly what data deletion removes.
- **No unused task results (H-20).** Celery stops storing task results nobody reads.

## Capabilities

### New Capabilities

- `developer-tooling`: the local runner stack (start, stop, console close, port waits, beat
  schedule), setup, the version-consistency check and CI run cancellation.

### Modified Capabilities

- `api-platform`: "Configuration validated at startup" names every numeric, interval and
  structured setting as checked, so a value that would loop or fail later blocks startup.
- `recommendation-engine`: "Versioned scoring configuration" says seeding activates a seeded
  configuration only in place of an earlier seed, and that migrations in either direction keep
  exactly one configuration active.

## Impact

- `scripts/`: `start.mjs`, `stop.mjs`, `child.mjs`, `redis.mjs`, `wait-port.mjs`, `beat.mjs`,
  `setup.mjs`, `check-version.mjs`, plus runner pid files under a gitignored `.run/`.
- `.github/workflows/ci.yml` (concurrency), `.gitignore`.
- `apps/backend/core/checks.py` (new checks), `config/settings/base.py`
  (`CELERY_TASK_IGNORE_RESULT`).
- `apps/backend/recommendations/migrations/0002_…` and `0003_…` (seed and unseed logic; data
  migrations already applied in a database are not re-run, so existing databases keep their
  current state).
- Tests: migration round trips, new checks, privacy page content, runner helpers where they are
  pure functions.
- No API, ranking or frontend behavior change. README and CLAUDE.md §6 describe the stop scope.
