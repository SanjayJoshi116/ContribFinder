## Context

See proposal.md (Why) and `Bug_Backlog.md` batch 30. `e2e_seed` runs once per Playwright run,
from `scripts/e2e-backend.mjs` before Django starts, and writes `{user: session id}` to
`e2e/.sessions.json`; `signInAs(user)` (`e2e/fixtures.ts`) sets that cookie. CI runs Playwright
with `retries: 1`, one worker. Only `config.settings.e2e` installs the app; it pins the database
name to `contribfinder_e2e`. Since the spec covers the seed, SEED-1 and SEED-2 are spec deltas
(`web-client`); the rest are code fixes.

## Goals / Non-Goals

**Goals:** close SEED-1…SEED-10, each with a test (backend) or a browser run (SEED-2).

**Non-Goals:** reseeding between tests or attempts (a Playwright `globalSetup` per test would
restart Django); excluding `e2e/` from the production image (the security review found it inert:
only `DJANGO_SETTINGS_MODULE`, a trusted value, could load it); a public replacement for
`connection._nodb_cursor()` (Django has none).

## Decisions

**D1 — Database guard.** `E2E_DATABASE = "contribfinder_e2e"` in the command; `handle` raises
`CommandError` unless `settings.DATABASES["default"]["NAME"]` equals it, before creating,
migrating or deleting anything. A test checks `config/settings/e2e.py` uses the same name (the
settings module cannot import the app). Alternative: a dedicated `E2E_SEED_ALLOWED` setting —
rejected, a second switch that can drift from the database it protects.

**D2 — One user per data-changing test and attempt.** `MUTATING_USERS = ("e2e-save",
"e2e-dismiss", "e2e-delete")`, `READ_USERS = ("e2e-dashboard",)`, plus the unsynced user. The
seed takes `--attempts` (default 1); `playwright.config.ts` defines `RETRIES` once and passes
`RETRIES + 1` through `scripts/e2e-backend.mjs`. Each mutating user is seeded once per attempt
(`<user>`, then `<user>-retry<n>`). The sessions file is the only contract: `{user: [session per
attempt]}` for mutating users, `{user: session}` (one id, every attempt) for the rest; not
`~` in names, the released-repository-name mark. `signInAs(user)` takes the entry for
`test.info().retry` (a single entry serves every attempt) and fails naming the user and attempt
when it is missing, so `fixtures.ts` holds no user list and no naming rule. `dashboard.spec.ts`
signs in per test: save → `e2e-save`, dismiss → `e2e-dismiss`, the two read tests →
`e2e-dashboard`. Alternatives: reseed before each retry — rejected, it needs a backend hook and a
restart; a fixed attempt count in the seed — rejected after `/simplify`, it duplicated
Playwright's `retries` and seeded unused copies locally.

**D3 — Seeding in one function.** `seed() -> dict[str, str]` (reset, pool, users, sessions)
holds what `handle` did after `migrate`; `handle` checks D1, creates and migrates the database,
calls `seed()` and writes the JSON. The backend test calls `seed()` twice on the test database
and checks the returned keys and that the first run's users and sessions are gone (SEED-6).
`_reset` deletes sessions and audit entries too (SEED-5). Synced users share one repository pool,
so seeding 4 synced users (dashboard, save, dismiss, delete), plus 3 retry copies in CI, costs
one analysis and one generation each.

**D4 — Jobs.** `services.jobs.new_job(user, job_type) -> SyncJob` creates the PENDING job with
`STEPS_BY_JOB_TYPE` steps; `_start_job` calls it inside its transaction, the seed calls it
directly (SEED-8). `_run` passes `steps=dict.fromkeys(job.steps, DONE)` to `finish_job` and
raises `CommandError` when it returns False (SEED-7).

**D5 — Builders.** `add_candidate` on an existing candidate sets `last_seen_at` to the latest of
its value, `seen` and `discovery_seen`, and a new candidate starts at the later of the two, as
`DiscoveryService` stamps both with the run time (SEED-3). `make_issue -> Issue` with a
module-level import (SEED-9). The seeded snapshot's `days_since_push` is
`(now - repo.pushed_at).days` (SEED-10). `CREATE DATABASE` uses `connection.ops.quote_name`
(SEED-4).

## Risks / Trade-offs

- [Seed takes longer (7 synced users instead of 2)] → each is one analysis and one generation
  over a shared 25-repository pool, a few seconds in total; the e2e server timeout is unchanged.
- [A test that changes data but signs in as a read user] → not detectable without reseeding
  (a non-goal); the user's name says which kind a test is, and review catches it.
- [Callers of `add_candidate` relying on a stale `last_seen_at`] → the backend suite runs
  unchanged; any test that needs an older candidate passes `seen` explicitly.
