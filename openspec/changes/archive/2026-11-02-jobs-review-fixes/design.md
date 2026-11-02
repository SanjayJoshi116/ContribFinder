## Context

See proposal.md (Why). `SyncJob` rows are written only by `services/jobs.py` and
`services/job_guard.py`, which fence every write on status and `claim_token`; `updated_at`
(`auto_now`) is the job's heartbeat, read by `_stale_running` and `recover_stale_jobs`.
`core/admin.NoAddDeleteAdmin` already serves the audit and GitHub admins.

## Goals / Non-Goals

**Goals:** the admin can never write a job; the active-status list has one source; the
recovery scan has an index.

**Non-Goals:** pruning old jobs (retention needs its own decision and a spec); changing a job's
state when it is read; a cooldown for failed syncs (JOB-9 accepted).

## Decisions

### D1. View-only admin (JOB-1, JOB-2, JOB-5)

`SyncJobAdmin(NoAddDeleteAdmin[SyncJob])` with `has_change_permission` returning False. Django
then renders the change page as view-only (staff need the view permission; superusers have it)
and never calls `save_model`. `readonly_fields` stays (the view page shows every field).
`list_select_related = ("user",)`.

Alternative: keep change permission and override `save_model` to do nothing. Rejected: a Save
button that silently does nothing is worse than no Save button.

### D2. One active-status list (JOB-4, JOB-6)

The constraint uses `Q(status__in=[s.value for s in ACTIVE_STATUSES])`; Django's autodetector
compares deconstructed values, so `makemigrations --check` must report nothing. `is_active` is
deleted (no caller; `ScoringConfig.is_active` is a different field).

### D3. Recovery index (JOB-8, part)

Partial index `syncjob_active_updated_idx` on `(updated_at)` with
`condition=Q(status__in=ACTIVE_STATUSES)`: the recovery filters (`status=RUNNING,
updated_at < …` and `status in (PENDING, RETRYING), updated_at < …`) and `_expire_stale` all
fall inside it, and it stays small because finished jobs are not in it. Migration `jobs.0007`.
The planner may still choose a sequential scan on a tiny table; the check is that the index
exists and the condition matches, not a plan.

Alternative: `(status, updated_at)` full index. Rejected: it grows with every finished job.

### D4. Beat expiry

`"options": {"expires": JOB_RECOVERY_INTERVAL_SECONDS}` on `recover-stale-jobs`: a run that
waited longer than one interval is superseded by the next one. The task is idempotent, so this
only drops duplicate work.

### D5. Serializer default (JOB-7)

`dict.fromkeys(order, SyncJob.StepState.PENDING.value)`; output unchanged.

### D6. `stalled` on every returned job (JOB-3)

`job_guard.is_stalled(job, now) -> bool`: `job.status == RUNNING and job.updated_at <
stale_before(now)`. `services.jobs._stale_running` stays the queryset form of the same rule
(both read `stale_before`); a test checks they agree on both sides of the cutoff.
`SyncJobSerializer.stalled` is a read-only `BooleanField` sourced from a method
(`SerializerMethodField` with `extend_schema_field(OpenApiTypes.BOOL)`), so the sync, discovery
and generation statuses and the start response all get it. Additive: OpenAPI stays `1.0.0`.

Alternatives: expire the job inside `GET /sync/status` (rejected: a GET that writes, and it
fails a job recovery would resume, against "Recovery of jobs whose worker died"); report it as
RETRYING (rejected: the SPA treats RETRYING as active, nothing changes for the user); shorter
recovery windows (rejected: tuning only, and a slow live worker gets fenced out sooner).

### D7. SPA: stalled is unfinished but not blocking (JOB-3)

`isActive` is unchanged, so polling continues and `fetchStatusAndRefresh` never treats a
stalled job as finished; when recovery resumes the job the next poll shows it. A new
`isStalled(job)` (`src/app/jobTransitions.ts`) drives the user-facing parts:

- `usePipelineStage` returns `'stalled'` when the first active job of the chain is stalled;
  `STAGE_TEXT.stalled`: "Background work stopped. It resumes automatically within a few
  minutes, or press Refresh."
- AppShell: Refresh is disabled while `isActive(job) && !isStalled(job)`. The POST then ends the
  stalled sync as `worker_lost` and starts a new one (existing `_start_job`); the cooldown still
  applies after a recent completed sync.
- Onboarding: a stalled job shows the same notice and the Try again button.

Alternative: make `isActive` false for stalled jobs. Rejected: polling would stop (the user
would never see recovery resume the job) and the transition check would refresh derived data
for a job that has not finished.

## Risks / Trade-offs

- [Staff lose the ability to fix a stuck job by hand in the admin] → the app's own flows
  already do it (recovery, `_expire_stale` on the next start, cancellation on disconnect); a
  manual edit bypassed the claim fencing anyway.
- [The index migration locks `jobs_syncjob` briefly] → the table is small locally; a plain
  `AddIndex` is fine at this scale.

- [Clock skew between the database and the web process makes `stalled` flip early or late] →
  both times come from Django's `timezone.now()` on the servers; a few seconds against a
  10-minute cutoff does not matter.
- [The user restarts a sync recovery was about to resume] → the restart fails the old job and
  runs a full new sync: duplicate GitHub calls, no wrong data.

## Migration Plan

Apply `jobs.0007`; reverse removes the index. No data change.
