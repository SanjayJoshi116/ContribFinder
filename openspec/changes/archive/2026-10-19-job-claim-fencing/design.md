## Context

See proposal.md for motivation. Rows B-1, B-2, B-3, B-5, B-7, B-8, B-9, B-10, B-11, B-12,
B-18, B-19, C-3, C-4, C-10 and C-19 in `Bug_Backlog.md` (verified; the verification notes
narrow B-7, B-8, B-10, B-11, C-3, C-4 and C-19).

Current state that shapes the approach:
- `claim_job(job_id) -> bool` is one conditional UPDATE: PENDING/RETRYING, or RUNNING with
  `updated_at` older than `SYNC_STALE_AFTER_SECONDS`, becomes RUNNING with `attempts + 1`.
  Nothing identifies which worker holds the job.
- `updated_at` is the heartbeat. `SyncJob.heartbeat()` (model method) bumps it while RUNNING;
  `save_progress` and `job_write` (`services/job_guard.py`, batch 2) check only `status ==
  RUNNING`. `finish_job` and the RUNNING → RETRYING update check the same.
- `recover_stale_jobs` fails stale RUNNING jobs at the attempt limit, then calls `.delay` for
  every stale RUNNING job without changing it.
- `cancel_active_syncs` and `_expire_stale` are bulk UPDATEs that never touch `steps`.
- `run_tracked_job` raises `task.retry(countdown=...)`. In eager mode Celery runs the retry
  inline at once.
- Four `start_*` functions repeat the active check, expiry, create and IntegrityError fallback,
  with differences: analysis has no stale exclusion or expiry; sync uses `.get()`.
- `developers.extract_developer_skills` claims and finishes by hand. `ProfileAnalysisError` is
  already a `PermanentJobError` (`analysis_failed`), so `decide_retry` fails it without a retry.
- `lifecycle.claim` sets FETCHING/REFRESHING and `lifecycle_changed_at = now` under a row lock.
  The claim's staleness is read from `lifecycle_changed_at`. `release` reads, then updates, and
  stamps `lifecycle_changed_at = now`. `fail` and `complete` match only on `pk`. `complete`
  saves ANALYZED and INDEXED separately before the final state.
- `lifecycle_changed_at` is read by the backlog (DISCOVERED grace, FAILED retry, abandoned
  claims) and by `services/ranking/freshness.py` (`Max(...)` of the pool as a change signal).

## Goals / Non-Goals

**Goals:**
- One fencing idea for jobs and repositories: a random token written at claim time, and every
  later write matches on it.
- No new settings, no API change, no change to step names or job types.

**Non-Goals:**
- Exactly-once execution. A fenced-out worker may still have made GitHub requests before its
  next check; only its writes are refused.
- Interrupting a worker mid-request. Checks stay between units of work, as today.
- Re-checking eligibility on stored data (C-5, C-14, R-12: batch 7) and GitHub error mapping
  (batch 5).

## Decisions

### D1. Job claim token
`SyncJob.claim_token = UUIDField(null=True, editable=False)`. It is not in any serializer.

`claim_job(job_id) -> SyncJob | None`:
- One UPDATE with the current condition plus `attempts < SYNC_MAX_ATTEMPTS`. It sets
  `claim_token = uuid4()`, `status = RUNNING`, `attempts + 1`, `started_at` (coalesce) and
  `updated_at`. On success it returns the job, loaded with `select_related("user")`. Callers
  use the returned instance, which carries the token.
- If nothing matched, a second UPDATE ends any job that would have matched except for its
  attempts as FAILED `worker_lost`, through D3. This covers a redelivery at the limit (B-10).
  It returns None.

Every write a worker makes matches `pk`, `status = RUNNING` and `claim_token = job.claim_token`:
- `job_guard.job_write(job)` (it takes the job instead of the id) locks the row and raises
  `JobCancelled` unless status and token match.
- `job_guard.save_progress(job, **fields)` checks the same.
- New `job_guard.heartbeat(job)` replaces `SyncJob.heartbeat()`. It raises `JobCancelled` when
  zero rows are updated. The `_check_cancelled` methods in the sync, discovery and ranking
  services call it instead of comparing statuses.
- `finish_job(job, status, **fields)` and the RUNNING → RETRYING update in `run_tracked_job`
  clear the token as they leave RUNNING.

A fenced-out worker gets `JobCancelled`, which `run_tracked_job` already handles by returning
quietly. `on_completed` runs only if `finish_job` matched, so a fenced-out worker never starts
a follow-up job.

**Alternative:** fence with `attempts` as a version counter. It is not unique across a
reclaim racing with a redelivery, and it would tie fencing to the retry budget. A UUID is
clearer.

**Alternative:** keep `job_write(job_id)` and look the token up. The token has to come from
the worker's own claim, not from the database, or a fenced-out worker would read the new
owner's token. So the signatures take the job.

### D2. Recovery moves abandoned jobs to RETRYING; PENDING and RETRYING get a timeout
`recover_stale_jobs`, in one pass:
1. **Stale RUNNING** (no heartbeat for `SYNC_STALE_AFTER_SECONDS`): jobs at the attempt limit
   end as FAILED `worker_lost` (D3). The others get `status = RETRYING`,
   `claim_token = NULL` and `updated_at = now`, then one `.delay`. The status change means the
   next beat no longer sees them as stale RUNNING (B-12). The revoked token fences the old
   worker even if it is only slow (B-2).
2. **Lost messages:** PENDING or RETRYING jobs with `updated_at` older than
   `SYNC_STALE_AFTER_SECONDS + GITHUB_MAX_RETRY_DELAY` get `updated_at = now`, then one
   `.delay` (B-1). The wait covers the longest retry countdown, so a retry that is merely
   scheduled is not duplicated. Bumping `updated_at` makes the next requeue wait a full period.
   No `requeued_at` column is needed: `updated_at` is not a heartbeat outside RUNNING.

A duplicate message is harmless: `claim_job` lets exactly one delivery claim the job.

The task stays a thin wrapper and reports `{"requeued", "failed"}`, now counting both kinds.

### D3. One way to end jobs that did not complete
`_end_jobs(queryset, status, **fields) -> int` is used by recovery, `_expire_stale`,
`cancel_active_syncs`, the FAILED path of `claim_job` and the FAILED path of `run_tracked_job`
(through `finish_job`). It locks the matching rows (`select_for_update`). For each row it sets
the status, `completed_at`, `updated_at`, `claim_token = NULL` and the given fields, and
rewrites `steps` so that every `running` step becomes `failed` (B-11). There are at most a few
rows per call, so a per-row save is fine. A JSONB update in SQL would be harder to read and test.

`failed` is used for CANCELLED too. The step did not finish, and the UI already renders
`failed`. A separate `cancelled` step state would change the OpenAPI enum and the frontend for
no user benefit.

### D4. No inline retry without a worker
In `run_tracked_job`, when `settings.CELERY_TASK_ALWAYS_EAGER` is true, `decide_retry` is
called with `attempts = SYNC_MAX_ATTEMPTS`. It therefore returns the `Fail` the job would get
after its last attempt (`github_rate_limited`, `github_unavailable`), and the policy stays one
pure function (B-9). It reads the Django setting instead of `task.request.is_eager`, because
tests run tasks eagerly and drive the retry path with `override_settings(...=False)`. A mocked
task object would also make `request.is_eager` truthy.

**Alternative:** sleep for the countdown. That blocks the HTTP request that started the job
for up to `GITHUB_MAX_RETRY_DELAY`, which breaks "HTTP requests never wait on GitHub".

### D5. `_start_job` and thin analysis task
`_start_job(user, job_type, steps) -> tuple[SyncJob, bool]`:
1. Return `active_jobs(user, job_type).first()` if there is one. Stale RUNNING jobs are excluded.
2. Run `_expire_stale(user, job_type)`.
3. Create the job in `transaction.atomic()` and queue `_task_for(job_type).delay` on commit.
4. On `IntegrityError`, return `active_jobs(...).first()`. If that is None, the conflicting job
   finished between the insert and this read (B-8): return the user's newest job of that type
   with `created=False`. Never use `.get()`.

The four `start_*` functions keep their preconditions (account connected, profile exists,
cooldown) and their return types, then delegate. `start_profile_analysis` gains the stale
exclusion and expiry (B-7, B-19).

`extract_developer_skills` becomes `run_tracked_job(self, job_id, _analyze,
on_completed=start_discovery_after)` (B-18). The `_analyze` function:
- saves step `running` via `save_progress`;
- runs `ProfileAnalysisService(job.user, job=job)`;
- saves step `done`.

`ProfileAnalysisError` already fails as `analysis_failed` with no retry, and D3 turns the
running step into `failed`. To keep the stored detail, `_safe_detail` keeps `str(exc)[:500]`
for `PermanentJobError` as well as `GitHubError`. Those messages are built by our code, never
from payloads.

### D6. Profile analysis: fixed upsert order and newest snapshot wins
- `_upsert_catalog_skills` and `_upsert_catalog_interests` insert `sorted(set(slugs))`. Each
  transaction then locks catalog rows in one global order (skills, then interests,
  alphabetical), so two analyses cannot deadlock (B-3).
- `ProfileAnalysisService(user, config=None, *, job: SyncJob | None = None)` replaces `job_id`.
  `run()` takes `now` before `build_input`.
- In `_persist`, after locking the profile row, if an existing profile has `analyzed_at > now`
  the result is dropped and the stored profile is returned (B-5). The comparison is strict, so
  re-running at the same instant stays idempotent. The job completes normally: a newer
  analysis already reflects at least this data.

**Alternative:** lock the profile row before `build_input`. That serializes analyses, but a
first analysis has no row to lock, and the lock would be held across the whole computation.
The timestamp check needs no new lock.

### D7. Repository claim token and claim time
New fields: `Repository.claim_token` (UUID, null) and `Repository.claimed_at` (null).

- `lifecycle.claim(repo_id) -> Repository | None`:
  - The staleness test for IN_PROGRESS uses `claimed_at`.
  - It sets `lifecycle`, `previous_lifecycle` (unless reclaiming), `claim_token = uuid4()` and
    `claimed_at = now`.
  - It does **not** touch `lifecycle_changed_at` (C-10). The returned instance carries the
    token.
- `lifecycle.renew(repo) -> None`: an UPDATE of `claimed_at` matching `pk` and the token. It
  raises `ClaimLost` (in `services/repositories/lifecycle.py`) when nothing matched.
  `RepositoryAnalysisService._fetch` calls it with the cancellation check before each part
  (C-4).
- `lifecycle.release(repo)`: one UPDATE matching `pk`, token and IN_PROGRESS (C-3, C-19).
  - It sets `lifecycle = Coalesce(NullIf(F("previous_lifecycle"), ""), DISCOVERED)`.
  - It clears `previous_lifecycle`, `claim_token` and `claimed_at`.
  - It leaves `lifecycle_changed_at` alone, so the restored state keeps its own transition
    time.
- `lifecycle.fail(repo, code)`: matches `pk` and the token, sets `lifecycle_changed_at = now`,
  and clears the claim.
- `lifecycle.complete(repo, now)`: first locks the row with `select_for_update` filtered on
  `pk` and the token, and raises `ClaimLost` if it is gone.
  - `run()` calls it at the start of the store transaction, so a fenced-out analysis rolls back
    without storing anything.
  - It then does one save to RECOMMENDABLE/INDEXED with `lifecycle_changed_at = now` and
    clears the claim.
  - The two unobservable intermediate saves are dropped, which also resolves C-22 (batch 11).
- `RepositoryAnalysisService.run` catches `ClaimLost` and returns `Outcome.SKIPPED`, the same
  as when another worker holds the claim. It does not release.

Because a claim no longer bumps `lifecycle_changed_at`, `freshness.py` stops seeing an analysis
start as a pool change. Only completed analyses and failures count, which is what it means.
`process_repository_backlog`'s abandoned clause becomes `lifecycle__in=IN_PROGRESS,
claimed_at__lt=abandoned` (or null).

### D8. Migrations
- `jobs`: add `claim_token`. Rows that are RUNNING at deploy time have a null token. Their
  old-code workers stop on restart; recovery reclaims them with a token.
- `repositories`: add `claim_token` and `claimed_at`, plus a `RunPython` backfill
  `claimed_at = lifecycle_changed_at` for FETCHING/REFRESHING rows, so in-flight claims keep
  their age. Reverse is a no-op.

## Risks / Trade-offs

- [Every `job_write`, `save_progress` and `finish_job` caller changes signature] → mypy strict
  catches missed callers. The batch-2 tests in `test_deletion_finality.py` keep covering
  cancellation, and new tests cover fencing.
- [Recovery requeues a PENDING job that is only stuck in a long queue] → the message is a
  duplicate. `claim_job` lets one delivery win, and the wait (`SYNC_STALE_AFTER_SECONDS +
  GITHUB_MAX_RETRY_DELAY`) is far above normal queue time.
- [The newest-snapshot check drops a result computed with new weights] → it only drops a
  result when a later analysis already stored a profile. That analysis used the same settings
  in the same process generation. `reanalyze_profiles` runs later, so its `now` is newer.
- [Tests that drive retries under eager settings now see FAILED] → those tests set
  `CELERY_TASK_ALWAYS_EAGER=False` via `override_settings`. A new test covers the eager
  behaviour itself.
- [`claimed_at` and `lifecycle_changed_at` now mean different things] → the model field
  docstrings say so, and the lifecycle module docstring documents both.

## Migration Plan

Deploy the migrations together with the code (`migrate` before workers start, as today).
Rollback: revert the code and migrate back. The new columns are dropped, and the old code
ignores them anyway. No data is rewritten except the `claimed_at` backfill.
