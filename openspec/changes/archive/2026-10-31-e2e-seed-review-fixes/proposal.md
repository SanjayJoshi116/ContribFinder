## Why

The review sweep's fifth module, `apps/backend/e2e/` (`Bug_Backlog.md` batch 30, SEED-1…SEED-10),
found that the browser-test seed wipes its database after checking only that the `e2e` app is
installed, that a CI retry of a test that changes data never starts from seeded data (two tests
share `e2e-dashboard`, and the delete-data test's user is empty on retry), and several smaller
seed and builder defects: sessions and audit entries pile up, `_reset` is never tested on seeded
data, jobs are written twice and outside the shared job builder, `make_issue` is untyped, and the
seeded data contradicts itself. The security review of the module found nothing.

## What Changes

- SEED-1: `e2e_seed` refuses to run unless the default database is `contribfinder_e2e`, in
  addition to the `e2e` app check.
- SEED-2: every browser test that changes data owns a seeded user per attempt: `save` and
  `dismiss` get their own users (`e2e-save`, `e2e-dismiss`), and each data-changing user is seeded
  once per attempt (`<user>`, `<user>-retry1`), so a CI retry signs in as a fresh copy. `signInAs`
  picks the attempt's copy from `testInfo.retry`.
- SEED-3: `add_candidate` advances an existing candidate's `last_seen_at` (never older than its
  newest discovery record), as discovery does.
- SEED-4: `CREATE DATABASE` quotes the name with `connection.ops.quote_name`.
- SEED-5: `_reset` also deletes sessions and audit entries.
- SEED-6: a backend test seeds, resets and seeds again, and checks the session ids written.
- SEED-7: `_run` finishes the job in one fenced write (`finish_job(..., steps=...)`) and fails
  if the job could not be finished.
- SEED-8: `services.jobs.new_job(user, job_type)` builds a PENDING job with its steps for both
  `_start_job` and the seed.
- SEED-9: `make_issue` returns `Issue` (module-level import).
- SEED-10: the seeded snapshot's `days_since_push` comes from the repository's `pushed_at`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-client`: "End-to-end coverage of the main flows" (the seed refuses any database but the
  end-to-end one; a retried test that changes data starts from seeded data).

## Impact

- `apps/backend/e2e/` (seed command, `builders.py`), `services/jobs.py`, `tests/test_e2e_seed.py`.
- `apps/frontend/e2e/fixtures.ts`, `dashboard.spec.ts` (users for save and dismiss).
- Browser tests must run (`npm run e2e`): the seed and fixtures change.
- No migration, no API contract change (OpenAPI `1.0.0`), no ranking change.
