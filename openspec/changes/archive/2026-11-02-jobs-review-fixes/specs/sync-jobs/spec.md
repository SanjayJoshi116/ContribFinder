## ADDED Requirements

### Requirement: Stalled jobs are reported
Every job the API returns (sync, discovery and generation status, and the response that starts a
sync) SHALL carry `stalled`: true when the job is RUNNING and has recorded no heartbeat for
`SYNC_STALE_AFTER_SECONDS`, by the same rule recovery and job starts use to treat a job as
abandoned by a dead worker; false otherwise. Reading a status SHALL NOT change the job: recovery
still resumes it, and a new start still ends it as FAILED `worker_lost` and starts another.

#### Scenario: Worker died mid-sync
- **WHEN** a sync job is RUNNING with no heartbeat for longer than `SYNC_STALE_AFTER_SECONDS` and the user requests `GET /api/v1/sync/status`
- **THEN** the job is returned with status RUNNING and `stalled: true`, and the job row is unchanged

#### Scenario: Live job
- **WHEN** a RUNNING job recorded a heartbeat within `SYNC_STALE_AFTER_SECONDS`
- **THEN** it is returned with `stalled: false`

#### Scenario: Not running
- **WHEN** the job is PENDING, RETRYING, COMPLETED, FAILED or CANCELLED, however old
- **THEN** it is returned with `stalled: false`

#### Scenario: Starting over a stalled sync
- **WHEN** the latest sync is stalled and the user starts a sync outside the cooldown
- **THEN** the stalled job ends as FAILED `worker_lost` and a new job is returned with HTTP 202
