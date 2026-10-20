# sync-jobs Specification

## Purpose

Lets users start and follow background GitHub synchronization without waiting on a long HTTP request. It tracks each job's lifecycle and progress and exposes the synced data and last-sync time to the frontend.

## Requirements

### Requirement: Start a sync
A signed-in user with a connected GitHub account SHALL be able to start a sync. The request SHALL return immediately with the job's ID and status, while the work runs in the background.

#### Scenario: Sync started
- **WHEN** a signed-in user sends `POST /api/v1/profile/sync` with a valid CSRF token and no sync is active
- **THEN** the system responds with HTTP 202 and the new job (ID, status PENDING, steps), and the request does not wait for any GitHub call

#### Scenario: No GitHub account connected
- **WHEN** a signed-in user without a connected GitHub account requests a sync
- **THEN** the system responds with HTTP 409 and error code `github_not_connected`

### Requirement: One active sync per user
The system SHALL allow at most one active (PENDING, RUNNING or RETRYING) job per user and job type (profile sync, profile analysis, repository discovery and recommendation generation). A start request while one is active SHALL return the active job and SHALL NOT create a second job. A RUNNING job without a heartbeat for `SYNC_STALE_AFTER_SECONDS` SHALL NOT count as active: starting a job of that type SHALL end it as FAILED with error code `worker_lost` and create a new job. A start that races with another start SHALL return the job that the other start created, even if that job has already finished, and SHALL never fail with a server error.

#### Scenario: Sync already running
- **WHEN** the user requests a sync while their previous sync is RUNNING
- **THEN** the system responds with HTTP 202 and the existing job's ID, and no new job is created

#### Scenario: Stale analysis does not block re-analysis
- **WHEN** a profile analysis job is RUNNING without a heartbeat for longer than `SYNC_STALE_AFTER_SECONDS` and an operator starts re-analysis for that user
- **THEN** the stale job ends as FAILED with error code `worker_lost` and a new analysis job is queued

#### Scenario: Conflicting job finished meanwhile
- **WHEN** two sync requests arrive together, the first creates a job, and that job finishes before the second request reads it back
- **THEN** the second request responds with HTTP 202 and the first request's job in its current status, and does not respond with HTTP 500

### Requirement: Sync cooldown
A new sync SHALL NOT start within the configured cooldown after the user's last completed sync. The rejection SHALL tell the client when a sync becomes possible.

#### Scenario: Refresh too soon
- **WHEN** the user's last sync completed 1 minute ago, the cooldown is 5 minutes, and the user requests a sync
- **THEN** the system responds with HTTP 429, error code `sync_cooldown`, and a `Retry-After` header of about 240 seconds

### Requirement: Job lifecycle and progress
Each sync job SHALL move through PENDING → RUNNING → COMPLETED, or into FAILED, RETRYING or CANCELLED. It SHALL record start time, completion time, attempt count, a machine-readable error code on failure, and per-step status for the steps profile, readme, repositories, languages, topics, dependencies, contributions and analysis, in that order. Each step's status SHALL be pending, running, done, not_found, skipped or failed. Jobs created before the dependencies, contributions and analysis steps existed SHALL still be readable, and a missing step SHALL be reported as pending. A job of any type that ends as FAILED or CANCELLED, by its worker, by recovery, by expiry or by cancellation, SHALL have no step left `running`: every running step SHALL become `failed`, and other steps SHALL keep their status.

#### Scenario: Successful job
- **WHEN** a sync runs to completion
- **THEN** the job status is COMPLETED, every step is done, not_found or skipped, and the start and completion times are set

#### Scenario: Failed job keeps partial progress
- **WHEN** the languages step fails permanently after profile and repositories completed
- **THEN** the job status is FAILED with an error code, the profile and repositories steps stay done, the languages step is failed, and the data from completed steps is kept

#### Scenario: Analysis failure
- **WHEN** every GitHub step completes but the analysis step fails
- **THEN** the job status is FAILED with error code `analysis_failed`, the analysis step is failed, the synced GitHub data is kept, and the previous developer profile is unchanged

#### Scenario: Cancelled mid-step
- **WHEN** the user disconnects GitHub while the repositories step of their sync is running
- **THEN** the job is CANCELLED, the repositories step is failed, and no step is reported as running

### Requirement: Sync status endpoint
The system SHALL provide the user's most recent sync job and the time of their last successful sync. It SHALL expose only the requesting user's jobs.

#### Scenario: Status during a sync
- **WHEN** a signed-in user requests `GET /api/v1/sync/status` while their sync is RUNNING with profile done
- **THEN** the response contains the job status RUNNING, the per-step statuses, and the last successful sync time (or null if none)

#### Scenario: Never synced
- **WHEN** a user who has never synced requests the status
- **THEN** the response has no current job and a null last successful sync time

#### Scenario: Another user's jobs are not visible
- **WHEN** user A requests the status
- **THEN** no job belonging to user B is returned

### Requirement: Initial sync after first sign-in
When a user signs in and has never synced, the system SHALL start a sync automatically. Signing in SHALL NOT wait for that sync.

#### Scenario: First sign-in
- **WHEN** a user completes GitHub sign-in for the first time
- **THEN** a sync job for that user exists in PENDING or a later state, and the sign-in redirect is not delayed by GitHub data fetching

#### Scenario: Returning user
- **WHEN** a user who already has a completed sync signs in again
- **THEN** no new sync is started automatically

### Requirement: Cancellation on disconnect
Disconnecting GitHub SHALL cancel every active job of the user: profile sync, profile analysis, repository discovery and recommendation generation. A cancelled job SHALL make no further GitHub requests. A repository that a cancelled discovery was analyzing SHALL return to the state it had before that analysis started. A cancelled recommendation generation SHALL leave the user's previous recommendations unchanged.

#### Scenario: Disconnect during sync
- **WHEN** the user disconnects GitHub while their sync is RUNNING or RETRYING
- **THEN** the job ends as CANCELLED and no further GitHub requests are made for it

#### Scenario: Disconnect during discovery
- **WHEN** the user disconnects GitHub while their discovery job is analyzing a repository
- **THEN** the discovery job ends as CANCELLED, no further GitHub requests are made for it, and the repository is no longer FETCHING

#### Scenario: Disconnect during recommendation generation
- **WHEN** the user disconnects GitHub while their recommendation generation job is RUNNING
- **THEN** the job ends as CANCELLED and the recommendations stored before it started are unchanged

### Requirement: Synced data endpoints
The system SHALL expose the requesting user's synced GitHub profile, including whether a profile README exists, and a paginated list of the repositories they own with languages and topics. These SHALL be served from stored data without calling GitHub. Repositories linked to the user only as contributor SHALL NOT appear in the repository list.

#### Scenario: Profile data
- **WHEN** a signed-in user with a completed sync requests `GET /api/v1/profile/github`
- **THEN** the response contains their stored GitHub profile fields and `has_profile_readme`, and no GitHub request is made

#### Scenario: Repository list
- **WHEN** the user requests `GET /api/v1/profile/repositories`
- **THEN** the response is a paginated list of the repositories they own, each with metadata, languages (with byte counts) and topics, most recently pushed first

#### Scenario: Contributed repositories excluded
- **WHEN** the user owns 2 repositories and is linked to 3 others as contributor
- **THEN** the repository list contains only the 2 owned repositories

#### Scenario: Not yet synced
- **WHEN** a user with no completed sync requests `GET /api/v1/profile/github`
- **THEN** the system responds with HTTP 404 and error code `not_synced`

### Requirement: Onboarding progress view
After sign-in, a user without a completed sync SHALL see an onboarding view. It SHALL show per-step progress for every sync step (profile, README, repositories, languages, topics, dependencies, contributions and profile analysis) and update without a page reload until the sync ends, then show the profile page. If the sync fails, the view SHALL show a readable message and a way to retry.

#### Scenario: Onboarding completes
- **WHEN** a newly signed-in user's sync moves from RUNNING to COMPLETED
- **THEN** the onboarding view marks each step, including dependencies, contributions and analysis, as it completes and then shows the profile page

#### Scenario: Onboarding sync fails
- **WHEN** the sync ends as FAILED with `github_auth_invalid`
- **THEN** the view explains that GitHub access must be renewed and offers sign-in again

#### Scenario: Analysis fails during onboarding
- **WHEN** the sync ends as FAILED with `analysis_failed`
- **THEN** the view explains that the profile could not be built from the synced data and offers a retry

### Requirement: Discovery after profile changes
When a profile sync completes, or a standalone profile analysis completes, the system SHALL start a repository discovery job for that user in the background. If a discovery job is already active for the user, no second job SHALL be created. A failed sync or analysis SHALL NOT start discovery. Starting discovery SHALL NOT change the outcome of the sync or analysis job.

#### Scenario: Sync completes
- **WHEN** a user's profile sync ends as COMPLETED
- **THEN** a repository discovery job for that user exists in PENDING or a later state

#### Scenario: Sync fails
- **WHEN** a user's profile sync ends as FAILED
- **THEN** no repository discovery job is started for it

#### Scenario: Discovery already active
- **WHEN** a re-analysis completes while the user's discovery job is RUNNING
- **THEN** no second discovery job is created

### Requirement: Recovery of jobs whose worker died
A RUNNING job SHALL record a heartbeat between units of work (each repository, query or step). A RUNNING job with no heartbeat for `SYNC_STALE_AFTER_SECONDS` (default 10 minutes) SHALL be treated as abandoned by a dead worker. A periodic task (every `JOB_RECOVERY_INTERVAL_SECONDS`, default 5 minutes) SHALL move each abandoned job to RETRYING, revoke its claim, and requeue it so that it resumes from its unfinished steps, without waiting for the broker's redelivery. A PENDING or RETRYING job that has not been picked up for `SYNC_STALE_AFTER_SECONDS` plus `GITHUB_MAX_RETRY_DELAY` SHALL be treated as having lost its queued task and SHALL be requeued. A job SHALL be requeued at most once per such waiting period, so recovery does not send the same job again on every run. A job that has used all `SYNC_MAX_ATTEMPTS`, whether it is found abandoned by the recovery task or redelivered by the broker, SHALL end as FAILED with error code `worker_lost` instead of running again. A requeued job that is already running again SHALL NOT be run twice. Redis calls SHALL time out (`REDIS_SOCKET_TIMEOUT`, default 5 seconds) so a stalled connection fails the work instead of blocking a worker.

#### Scenario: Worker restarted mid-discovery
- **WHEN** a discovery job is RUNNING and its worker process is killed
- **THEN** within `SYNC_STALE_AFTER_SECONDS` plus one recovery interval the job is requeued and resumes, and steps already done are not repeated

#### Scenario: Job keeps losing its worker
- **WHEN** an abandoned job has already been attempted `SYNC_MAX_ATTEMPTS` times
- **THEN** the recovery task ends it as FAILED with error code `worker_lost` instead of requeueing it

#### Scenario: Redelivered past the attempt limit
- **WHEN** the broker redelivers a job whose worker crashed and the job has already been attempted `SYNC_MAX_ATTEMPTS` times
- **THEN** the job ends as FAILED with error code `worker_lost` and its work does not run again

#### Scenario: Lost queued task
- **WHEN** a job is PENDING, its task message was lost, and it has waited longer than `SYNC_STALE_AFTER_SECONDS` plus `GITHUB_MAX_RETRY_DELAY`
- **THEN** the recovery task requeues it, the job runs, and the user can start jobs of that type again after it finishes

#### Scenario: Requeued once per waiting period
- **WHEN** the recovery task requeued a job and runs again before the job has waited another full waiting period
- **THEN** it does not requeue that job again

#### Scenario: Live job is left alone
- **WHEN** a RUNNING job recorded a heartbeat within `SYNC_STALE_AFTER_SECONDS`
- **THEN** the recovery task does not requeue it

### Requirement: Job claim fencing
Each time a worker starts running a job (a first run, a retry, a redelivery or a recovery), the job SHALL get a new claim that replaces any earlier one. Only the worker holding the current claim SHALL be able to record a heartbeat, save progress, write the user's data, schedule a retry or finish the job. A worker whose claim was replaced SHALL stop at its next heartbeat or write, SHALL write nothing further, and SHALL NOT start a follow-up job.

#### Scenario: Slow worker loses its claim
- **WHEN** a RUNNING job stops sending heartbeats for longer than `SYNC_STALE_AFTER_SECONDS`, another worker reclaims it, and the first worker then resumes
- **THEN** the first worker's next heartbeat or write is refused, it stops without writing data, and only the second worker can complete the job

#### Scenario: Only one follow-up
- **WHEN** two workers held claims on the same sync job one after the other and both reach the end of their work
- **THEN** the job is completed once and at most one discovery job is started after it

### Requirement: No inline retries without a worker
When background work runs inline because no broker is configured, an error that would otherwise be retried after a countdown SHALL NOT be retried immediately. The job SHALL instead end as FAILED with the error code it would get after its last attempt (for example `github_rate_limited` or `github_unavailable`).

#### Scenario: Rate limited without Redis
- **WHEN** `REDIS_URL` is empty and a sync hits a GitHub rate limit
- **THEN** the job ends as FAILED with error code `github_rate_limited` after one GitHub request, and no request is repeated without waiting
