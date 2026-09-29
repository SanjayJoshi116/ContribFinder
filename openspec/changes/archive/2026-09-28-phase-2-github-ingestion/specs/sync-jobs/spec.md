## Purpose

Lets users start and follow background GitHub synchronization without waiting on a long HTTP request. It tracks each job's lifecycle and progress and exposes the synced data and last-sync time to the frontend.

## ADDED Requirements

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
Each sync job SHALL move through PENDING → RUNNING → COMPLETED, or into FAILED, RETRYING or CANCELLED. It SHALL record start time, completion time, attempt count, a machine-readable error code on failure, and per-step status for the steps profile, readme, repositories, languages and topics. Each step's status SHALL be pending, running, done, not_found, skipped or failed.

#### Scenario: Successful job
- **WHEN** a sync runs to completion
- **THEN** the job status is COMPLETED, every step is done or not_found, and the start and completion times are set

#### Scenario: Failed job keeps partial progress
- **WHEN** the languages step fails permanently after profile and repositories completed
- **THEN** the job status is FAILED with an error code, the profile and repositories steps stay done, the languages step is failed, and the data from completed steps is kept

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
Disconnecting GitHub SHALL cancel the user's active sync. A cancelled job SHALL make no further GitHub requests.

#### Scenario: Disconnect during sync
- **WHEN** the user disconnects GitHub while their sync is RUNNING or RETRYING
- **THEN** the job ends as CANCELLED and no further GitHub requests are made for it

### Requirement: Synced data endpoints
The system SHALL expose the requesting user's synced GitHub profile, including whether a profile README exists, and a paginated list of their synced repositories with languages and topics. These SHALL be served from stored data without calling GitHub.

#### Scenario: Profile data
- **WHEN** a signed-in user with a completed sync requests `GET /api/v1/profile/github`
- **THEN** the response contains their stored GitHub profile fields and `has_profile_readme`, and no GitHub request is made

#### Scenario: Repository list
- **WHEN** the user requests `GET /api/v1/profile/repositories`
- **THEN** the response is a paginated list of their linked repositories, each with metadata, languages (with byte counts) and topics, most recently pushed first

#### Scenario: Not yet synced
- **WHEN** a user with no completed sync requests `GET /api/v1/profile/github`
- **THEN** the system responds with HTTP 404 and error code `not_synced`

### Requirement: Onboarding progress view
After sign-in, a user without a completed sync SHALL see an onboarding view. It SHALL show per-step progress and update without a page reload until the sync ends, then show the synced profile. If the sync fails, the view SHALL show a readable message and a way to retry.

#### Scenario: Onboarding completes
- **WHEN** a newly signed-in user's sync moves from RUNNING to COMPLETED
- **THEN** the onboarding view marks each step as it completes and then shows the signed-in profile view

#### Scenario: Onboarding sync fails
- **WHEN** the sync ends as FAILED with `github_auth_invalid`
- **THEN** the view explains that GitHub access must be renewed and offers sign-in again
