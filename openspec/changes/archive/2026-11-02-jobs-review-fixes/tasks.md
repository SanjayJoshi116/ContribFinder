## 1. Admin

- [x] 1.1 JOB-1, JOB-2, JOB-5: `SyncJobAdmin(NoAddDeleteAdmin[SyncJob])`, `has_change_permission` False, `list_select_related = ("user",)` (D1); tests: add, change and delete refused for a superuser, the change page renders view-only, the changelist query count does not grow with rows

## 2. Model and serializer

- [x] 2.1 JOB-4, JOB-6: remove `SyncJob.is_active`; constraint condition from `ACTIVE_STATUSES`; `makemigrations --check` reports nothing for it (D2)
- [x] 2.2 JOB-8: partial index `syncjob_active_updated_idx` (D3), migration `jobs.0007`; test: the index exists with its condition
- [x] 2.3 JOB-7: `StepState.PENDING` in `SyncJobSerializer.to_representation` (D5); existing missing-step test still passes

## 3. Beat

- [x] 3.1 JOB-8: `expires` on `recover-stale-jobs` (D4); test: the beat entry carries `expires == JOB_RECOVERY_INTERVAL_SECONDS`

## 4. Stalled jobs, backend (JOB-3)

- [x] 4.1 `job_guard.is_stalled(job, now)` (D6); test: agrees with `_stale_running` just before and after the cutoff, false for every other status
- [x] 4.2 `SyncJobSerializer.stalled` (D6); tests: sync status returns `stalled: true` for a dead RUNNING job and leaves the row unchanged, `false` for a live one; discovery and generation status carry the field; starting over a stalled sync returns a new job and fails the old one `worker_lost`
- [x] 4.3 `npm run api:sync`; commit `openapi` schema and `src/api/schema.d.ts`

## 5. Stalled jobs, frontend (JOB-3)

- [x] 5.1 `isStalled` in `src/app/jobTransitions.ts`; `usePipelineStage` returns `'stalled'` with `STAGE_TEXT.stalled` (D7); tests: stalled sync and stalled discovery show the notice, a stalled job keeps polling and triggers no refresh, resuming then completing refreshes once
- [x] 5.2 AppShell Refresh enabled for a stalled sync; Onboarding shows the notice and Try again (D7); tests for both

## 6. Backlog

- [x] 6.1 `Bug_Backlog.md` batch 36 "Sweep: `jobs/`": JOB-1…JOB-10 with verdicts (JOB-9, JOB-10 accepted; JOB-8 partial)

## 7. Checks

- [x] 7.1 Backend `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`, `uv run mypy .`, `makemigrations --check --settings config.settings.test`
- [x] 7.2 Frontend `npm test`, `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm run build`; API contract has no drift (e2e not needed: no seeded flow has a stalled job)

## 8. Release

- [x] 8.1 `/simplify`, then `/code-review` on the fix diff; record and fix (skipped by the owner, 2026-11-02)
- [x] 8.2 Archive (deltas into `sync-jobs`, `web-client`); release housekeeping (CLAUDE.md §8, 0.12.48); commit only when the owner says so
