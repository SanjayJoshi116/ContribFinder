## Why

Jobs and repository analyses can be claimed twice, can get stuck forever, and can report
progress that isn't true. Batch 4 of `Bug_Backlog.md` (verified) found these gaps:
- **No ownership fencing.** A slow worker whose job or repository claim was reclaimed keeps
  writing next to the new owner. The first one to finish fires the follow-up job (B-2, C-3,
  C-19). A repository claim is never renewed, so an analysis that takes more than 10 minutes is
  reclaimed while it is still running (C-4).
- **Zombie jobs.** PENDING and RETRYING jobs never expire. One lost broker message leaves a job
  that the one-active-job constraint keeps forever, so the user can never sync, discover or
  regenerate again (B-1).
- **Crash loops and duplicate messages.** Redelivery ignores `SYNC_MAX_ATTEMPTS` (B-10).
  Recovery re-sends the task on every beat without changing the job (B-12). In eager mode
  (`REDIS_URL` empty), a retry runs again inline right away and ignores the countdown, so it
  hits GitHub in a hot loop (B-9).
- **Misleading state.** FAILED and CANCELLED jobs keep a step `running`, so the UI shows a
  spinner on a dead job (B-11). A transient failure restarts a repository's FAILED retry clock
  and its DISCOVERED grace period (C-10).
- **Races in profile analysis.** Concurrent analyses deadlock on the shared skill catalog (B-3).
  A sync's analysis and a standalone analysis that overlap can let the older snapshot win (B-5).
- **Drifted copies.** The four `start_*` functions have drifted apart, which causes B-7 (stale
  analysis jobs block re-analysis) and B-8 (a 500 when the active job finished meanwhile). The
  analysis task re-implements `run_tracked_job` by hand (B-18, B-19).

Theme 1 of the backlog says one claim-token mechanism fixes jobs and repositories together.
Batches 5 to 7 build on job and lifecycle helpers, so this batch goes first.

## What Changes

- **Claim tokens.**
  - Every job claim and every repository analysis claim gets a fresh token.
  - Heartbeats, progress saves, guarded writes, retries and the final state are accepted only
    from the token's holder.
  - A worker that lost its claim stops at its next write and writes nothing.
- **Repository claims are renewed** between the parts of an analysis.
  - Releasing a claim restores the earlier state and its transition time in one atomic update.
  - A claim no longer counts as a lifecycle transition, so it does not restart the FAILED retry
    clock, the DISCOVERED grace period, or the recommendation freshness check.
- **Recovery covers every active state.**
  - A RUNNING job without a heartbeat is moved to RETRYING with its claim revoked, then
    requeued once.
  - A PENDING or RETRYING job whose message was lost is requeued after a longer wait.
  - Requeueing records the time, so the next beat doesn't send it again.
  - Redelivery and recovery both stop at `SYNC_MAX_ATTEMPTS` and end the job as FAILED with
    `worker_lost`.
- **Eager mode never retries inline.** Without a worker (`REDIS_URL` empty), an error that
  would be retried fails the job with the code it would get after its last attempt.
- **Terminal jobs have no running step.** Failing, cancelling, expiring or abandoning a job
  marks its `running` steps `failed`.
- **One start helper.** All four job types start through `_start_job`.
  - It ignores stale RUNNING jobs and expires them.
  - It never fails when the job it conflicted with finished meanwhile.
- **Profile analysis.**
  - The analysis task becomes a thin wrapper over `run_tracked_job`.
  - Catalog rows are upserted in a fixed order, so concurrent analyses never deadlock.
  - An analysis whose snapshot is older than the stored profile does not overwrite it.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `sync-jobs`:
  - Claim fencing.
  - Recovery of PENDING and RETRYING jobs.
  - The attempt limit on redelivery.
  - No inline retries in eager mode.
  - No `running` step on a finished job.
  - Starting a job never fails when the job it conflicted with finished meanwhile.
- `repository-analysis`:
  - Analysis claims are fenced and renewed.
  - A released claim keeps the earlier transition time.
- `developer-profile`: an older analysis never overwrites a newer profile.

## Impact

- **Backend:**
  - `services/jobs.py`: claim, finish, retry, recovery, expiry, cancel and `_start_job`.
  - `services/job_guard.py`: token-aware `job_write`, `save_progress` and a new `heartbeat`.
  - `jobs/models.py`: `SyncJob.heartbeat` moves to `job_guard`.
  - Callers in `services/github/sync.py`, `services/discovery/service.py` and
    `services/ranking/service.py`.
  - `developers/tasks.py`.
  - `services/profiling/analysis.py`.
  - `services/repositories/lifecycle.py` and `services/repositories/analysis.py`.
  - The `process_repository_backlog` abandoned-claim query in `repositories/tasks.py`.
- **Data:**
  - Migrations add `SyncJob.claim_token`, plus `Repository.claim_token` and
    `Repository.claimed_at`.
  - `claimed_at` is backfilled from `lifecycle_changed_at` for repositories that are
    FETCHING or REFRESHING.
- **API:** unchanged. The OpenAPI schema is unchanged; the token is never serialized.
- **Settings:** none new. The PENDING/RETRYING recovery wait is derived from
  `SYNC_STALE_AFTER_SECONDS` and `GITHUB_MAX_RETRY_DELAY`.
- **Out of scope:**
  - GitHub status mapping and one bad repository failing a job (batch 5).
  - Eligibility re-checks, C-5 and C-14 (batch 7).
  - The experience cutoffs, B-6 (batch 8).
