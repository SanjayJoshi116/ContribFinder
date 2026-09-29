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
The system SHALL allow at most one active (PENDING, RUNNING or RETRYING) sync per user. A start request while one is active SHALL return the active job and SHALL NOT create a second job.

#### Scenario: Sync already running
- **WHEN** the user requests a sync while their previous sync is RUNNING
- **THEN** the system responds with HTTP 202 and the existing job's ID, and no new job is created

### Requirement: Sync cooldown
A new sync SHALL NOT start within the configured cooldown after the user's last completed sync. The rejection SHALL tell the client when a sync becomes possible.

#### Scenario: Refresh too soon
- **WHEN** the user's last sync completed 1 minute ago, the cooldown is 5 minutes, and the user requests a sync
- **THEN** the system responds with HTTP 429, error code `sync_cooldown`, and a `Retry-After` header of about 240 seconds

### Requirement: Job lifecycle and progress
Each sync job SHALL move through PENDING → RUNNING → COMPLETED, or into FAILED, RETRYING or CANCELLED. It SHALL record start time, completion time, attempt count, a machine-readable error code on failure, and per-step status for the steps profile, readme, repositories, languages, topics, dependencies, contributions and analysis, in that order. Each step's status SHALL be pending, running, done, not_found, skipped or failed. Jobs created before the dependencies, contributions and analysis steps existed SHALL still be readable, and a missing step SHALL be reported as pending.

#### Scenario: Successful job
- **WHEN** a sync runs to completion
- **THEN** the job status is COMPLETED, every step is done, not_found or skipped, and the start and completion times are set

#### Scenario: Failed job keeps partial progress
- **WHEN** the languages step fails permanently after profile and repositories completed
- **THEN** the job status is FAILED with an error code, the profile and repositories steps stay done, the languages step is failed, and the data from completed steps is kept

#### Scenario: Analysis failure
- **WHEN** every GitHub step completes but the analysis step fails
- **THEN** the job status is FAILED with error code `analysis_failed`, the analysis step is failed, the synced GitHub data is kept, and the previous developer profile is unchanged

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
Disconnecting GitHub SHALL cancel every active job of the user: profile sync, profile analysis and repository discovery. A cancelled job SHALL make no further GitHub requests. A repository that a cancelled discovery was analyzing SHALL return to the state it had before that analysis started.

#### Scenario: Disconnect during sync
- **WHEN** the user disconnects GitHub while their sync is RUNNING or RETRYING
- **THEN** the job ends as CANCELLED and no further GitHub requests are made for it

#### Scenario: Disconnect during discovery
- **WHEN** the user disconnects GitHub while their discovery job is analyzing a repository
- **THEN** the discovery job ends as CANCELLED, no further GitHub requests are made for it, and the repository is no longer FETCHING

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
A RUNNING job SHALL record a heartbeat between units of work (each repository, query or step). A RUNNING job with no heartbeat for `SYNC_STALE_AFTER_SECONDS` (default 10 minutes) SHALL be treated as abandoned by a dead worker. A periodic task (every `JOB_RECOVERY_INTERVAL_SECONDS`, default 5 minutes) SHALL requeue each abandoned job so that it resumes from its unfinished steps, without waiting for the broker's redelivery. An abandoned job that has used all `SYNC_MAX_ATTEMPTS` SHALL end as FAILED with error code `worker_lost`. A requeued job that is already running again SHALL NOT be run twice. Redis calls SHALL time out (`REDIS_SOCKET_TIMEOUT`, default 5 seconds) so a stalled connection fails the work instead of blocking a worker.

#### Scenario: Worker restarted mid-discovery
- **WHEN** a discovery job is RUNNING and its worker process is killed
- **THEN** within `SYNC_STALE_AFTER_SECONDS` plus one recovery interval the job is requeued and resumes, and steps already done are not repeated

#### Scenario: Job keeps losing its worker
- **WHEN** an abandoned job has already been attempted `SYNC_MAX_ATTEMPTS` times
- **THEN** the recovery task ends it as FAILED with error code `worker_lost` instead of requeueing it

#### Scenario: Live job is left alone
- **WHEN** a RUNNING job recorded a heartbeat within `SYNC_STALE_AFTER_SECONDS`
- **THEN** the recovery task does not requeue it
