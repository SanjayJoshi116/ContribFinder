## Why

The review sweep's next module, `apps/backend/jobs/` (`Bug_Backlog.md` batch 36, JOB-1…JOB-10),
found that the `SyncJob` admin can create rows that fail (500), delete jobs behind the app's
cancel and finish flows, and overwrite a job a worker is writing while making a dead job look
alive; and that `/sync/status` shows a job whose worker died as running for up to about 15
minutes, with Refresh disabled, while the backend already treats it as abandoned. It also found a few smaller things: an unused `is_active` property whose meaning
differs from `active_jobs()`, a constraint that repeats the active statuses, a literal step
state, an N+1 admin list, and a recovery scan with no matching index. The security review of the module found
nothing.

## What Changes

- JOB-1, JOB-2: `SyncJobAdmin` becomes view-only: no add, no delete (`NoAddDeleteAdmin`), no
  change (no save, so no full-row write and no `updated_at` bump).
- JOB-5: `list_select_related = ("user",)` on the admin list.
- JOB-4: remove the unused `SyncJob.is_active`; `services.jobs.active_jobs()` stays the one
  definition of an active job.
- JOB-6: the `one_active_job_per_user_and_type` condition is built from `ACTIVE_STATUSES`
  (same values, no migration).
- JOB-7: the serializer fills missing steps with `SyncJob.StepState.PENDING`.
- JOB-8 (part): a partial index on `updated_at` for active jobs, which the recovery task's
  scans use, and `expires` on the `recover-stale-jobs` beat entry so runs that piled up while
  the worker was down are dropped.
- JOB-3: every job the API returns carries `stalled` (RUNNING with no heartbeat for
  `SYNC_STALE_AFTER_SECONDS`, the rule `active_jobs()` and recovery already use). The SPA keeps
  polling a stalled job, says that background work stopped and resumes automatically, and lets
  the user start a sync over a stalled one (the backend already ends it as `worker_lost`).
  Reading a status changes nothing; recovery still resumes the job.
- Accepted, no code change: JOB-9 (cooldown after completed syncs only, by design), JOB-10 (`last_synced_at` is the last
  successful sync; data versions count a failed one on purpose), and pruning old jobs (JOB-8,
  a retention decision).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `sync-jobs`: new "Stalled jobs are reported" (`stalled` on every returned job; reading
  changes nothing; starting over a stalled sync).
- `web-client`: new "Stalled job" (keeps polling, stalled notice, sync can be started).

The admin, index, task options and refactors change no specified behavior.

## Impact

- Backend: `apps/backend/jobs/{admin.py,models.py,serializers.py}`, `services/job_guard.py`
  (`is_stalled`), `services/jobs.py` (`_stale_running` shares the rule), new migration
  `jobs.0007` (partial index), `config/settings/base.py` (`CELERY_BEAT_SCHEDULE`), tests.
- API: additive field `stalled` on `SyncJob` (OpenAPI stays `1.0.0`); `npm run api:sync`.
- Frontend: `src/app/jobTransitions.ts` (`isStalled`), `features/sync/pipeline.ts`,
  `routes/AppShell.tsx`, `routes/OnboardingPage.tsx`, tests.
- No ranking change.
