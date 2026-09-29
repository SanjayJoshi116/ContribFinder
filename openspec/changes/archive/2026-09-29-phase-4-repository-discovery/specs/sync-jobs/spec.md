## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Cancellation on disconnect
Disconnecting GitHub SHALL cancel every active job of the user: profile sync, profile analysis and repository discovery. A cancelled job SHALL make no further GitHub requests. A repository that a cancelled discovery was analyzing SHALL return to the state it had before that analysis started.

#### Scenario: Disconnect during sync
- **WHEN** the user disconnects GitHub while their sync is RUNNING or RETRYING
- **THEN** the job ends as CANCELLED and no further GitHub requests are made for it

#### Scenario: Disconnect during discovery
- **WHEN** the user disconnects GitHub while their discovery job is analyzing a repository
- **THEN** the discovery job ends as CANCELLED, no further GitHub requests are made for it, and the repository is no longer FETCHING
