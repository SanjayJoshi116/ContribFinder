## 1. Data model and migrations (D1, D7, D8)

- [x] 1.1 Add `SyncJob.claim_token` (UUID, null, not editable) and a `jobs` migration; confirm no serializer exposes it and the OpenAPI schema is unchanged
- [x] 1.2 Add `Repository.claim_token` (UUID, null) and `Repository.claimed_at` (null), with field docstrings separating `claimed_at` from `lifecycle_changed_at`; `repositories` migration with a `RunPython` backfill `claimed_at = lifecycle_changed_at` for FETCHING/REFRESHING (reverse no-op)
- [x] 1.3 Remove `SyncJob.heartbeat()` from `jobs/models.py`

## 2. Job claims and fenced writes (D1, B-2, B-10)

- [x] 2.1 `claim_job(job_id) -> SyncJob | None`: one UPDATE adding `attempts < SYNC_MAX_ATTEMPTS` and a fresh `claim_token`; when nothing matched, end jobs that matched except for attempts as FAILED `worker_lost` (via 3.1)
- [x] 2.2 `services/job_guard.py`: `job_write(job)` and `save_progress(job, **fields)` match status RUNNING and `claim_token`; new `heartbeat(job)` raising `JobCancelled` when nothing was updated
- [x] 2.3 `finish_job(job, status, **fields)` matches the token and clears it; the RUNNING → RETRYING update in `run_tracked_job` does the same; `on_completed` runs only when `finish_job` matched
- [x] 2.4 Update callers: `services/github/sync.py`, `services/discovery/service.py`, `services/ranking/service.py` (`job_write(self.job)`, `_check_cancelled` → `job_guard.heartbeat`)
- [x] 2.5 Tests: a reclaimed job's first worker gets `JobCancelled` on heartbeat, `save_progress`, `job_write` and `finish_job`, writes nothing, and starts no follow-up; only the second worker completes the job; redelivery at the attempt limit ends FAILED `worker_lost` without running the job body

## 3. Ending jobs, recovery and eager mode (D2, D3, D4, B-1, B-9, B-11, B-12)

- [x] 3.1 `_end_jobs(queryset, status, **fields)`: lock rows, set status, `completed_at`, `updated_at`, clear `claim_token`, rewrite `running` steps to `failed`; use it in `_expire_stale`, `cancel_active_syncs`, `claim_job`'s limit path and `finish_job`'s FAILED path
- [x] 3.2 `recover_stale_jobs`: stale RUNNING below the limit → RETRYING, token cleared, `updated_at = now`, one `.delay`; at the limit → `_end_jobs` FAILED `worker_lost`; PENDING/RETRYING older than `SYNC_STALE_AFTER_SECONDS + GITHUB_MAX_RETRY_DELAY` → `updated_at = now`, one `.delay`
- [x] 3.3 `run_tracked_job`: with `CELERY_TASK_ALWAYS_EAGER`, call `decide_retry` with `attempts = SYNC_MAX_ATTEMPTS`; `_safe_detail` keeps `str(exc)[:500]` for `PermanentJobError`
- [x] 3.4 Tests: a cancelled, expired, worker-failed or recovery-failed job has no `running` step; a stale RUNNING job is requeued once and is RETRYING with no token; a lost PENDING job is requeued after the wait and not again on the next run; a live job and a recently scheduled RETRYING job are left alone; in eager mode a 429 fails the sync with `github_rate_limited` after one request
- [x] 3.5 Update existing retry tests (`test_github_sync.py` and others that expect RETRYING) to run with `override_settings(CELERY_TASK_ALWAYS_EAGER=False)`; update `test_job_recovery.py` and `test_deletion_finality.py` for the new signatures and RETRYING transition

## 4. Starting jobs (D5, B-7, B-8, B-19)

- [x] 4.1 `_start_job(user, job_type, steps)`: active check (stale-excluding), `_expire_stale`, create with on-commit `.delay`, IntegrityError → active job or else the newest job of that type (`created=False`), never `.get()`
- [x] 4.2 `start_profile_sync`, `start_profile_analysis`, `start_discovery`, `start_recommendations` keep their preconditions and return types and delegate to `_start_job`
- [x] 4.3 Tests: a stale RUNNING analysis job is expired with `worker_lost` and a new one queued; an IntegrityError whose conflicting job already finished returns that job without raising (`POST /profile/sync` → 202)

## 5. Profile analysis (D5, D6, B-3, B-5, B-18)

- [x] 5.1 `ProfileAnalysisService(user, config=None, *, job=None)`; `job_write(job)` when a job is given
- [x] 5.2 `_upsert_catalog_skills` / `_upsert_catalog_interests` insert `sorted(set(slugs))`
- [x] 5.3 `_persist`: when the locked existing profile has `analyzed_at > now`, keep it and return it unchanged
- [x] 5.4 `extract_developer_skills` → `run_tracked_job(self, job_id, _analyze, on_completed=start_discovery_after)`; `_analyze` saves step `running`, runs the service, saves step `done`; `services/github/sync.py` `_step_analysis` passes `job=self.job`
- [x] 5.5 Tests: an analysis whose `now` is older than the stored `analyzed_at` leaves the profile unchanged and the job COMPLETED; catalog upserts are issued in sorted order; standalone analysis failure still ends FAILED `analysis_failed` with step `failed` and the previous profile kept; discovery still starts after a completed analysis

## 6. Repository claims (D7, C-3, C-4, C-10, C-19)

- [x] 6.1 `lifecycle.claim`: staleness from `claimed_at`; set `claim_token`, `claimed_at`; leave `lifecycle_changed_at` alone
- [x] 6.2 `lifecycle.renew(repo)` and `ClaimLost`; `release(repo)` as one token-matched UPDATE with `Coalesce(NullIf(previous_lifecycle, ""), DISCOVERED)` that keeps `lifecycle_changed_at`; `fail(repo, code)` token-matched
- [x] 6.3 `lifecycle.complete(repo, now)`: lock the row by `pk` and token first (raise `ClaimLost`), then one save to RECOMMENDABLE/INDEXED with `lifecycle_changed_at = now`, clearing the claim
- [x] 6.4 `RepositoryAnalysisService`: renew before each part in `_fetch`; call `complete`'s claim check at the start of the store transaction; `ClaimLost` → `Outcome.SKIPPED` without release
- [x] 6.5 `process_repository_backlog`: abandoned clause uses `claimed_at` (or null)
- [x] 6.6 Tests: an analysis renewing its claim across a long fetch is not reclaimed; a reclaimed analysis's release, fail and complete change nothing and store no data; a transient failure on a FAILED repository keeps its original `lifecycle_changed_at`, and on a DISCOVERED one past the grace period it stays due in the backlog; release restores DISCOVERED when `previous_lifecycle` is empty; existing lifecycle and discovery tests pass

## 7. Verification and housekeeping

- [x] 7.1 Backend: `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`, `uv run mypy .`
- [x] 7.2 `npm run api:sync` shows no schema drift
- [x] 7.3 Manual (local worker + Redis): kill the worker mid-discovery → the job becomes RETRYING within one recovery interval after the stale time and completes; with `REDIS_URL` empty a sync that hits a GitHub error fails instead of looping; disconnect during sync leaves no step running in the UI (2026-10-19: done on the local stack with a real worker and WSL Redis. The test account's GitHub token was revoked, so the worker kill used a `profile_analysis` held by a row lock instead of a discovery, and the UI check was done through `SyncJobSerializer` output, not the browser)
- [x] 7.4 Mark B-1, B-2, B-3, B-5, B-7, B-8, B-9, B-10, B-11, B-12, B-18, B-19, C-3, C-4, C-10, C-19 (and C-22, resolved by D7) `fixed (job-claim-fencing)` in `Bug_Backlog.md`; CHANGELOG `[Unreleased]` entry
