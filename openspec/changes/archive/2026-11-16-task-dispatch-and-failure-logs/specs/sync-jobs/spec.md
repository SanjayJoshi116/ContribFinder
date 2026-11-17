## ADDED Requirements

### Requirement: A refused task send never fails committed work

When the broker refuses a background task after the work that queued it has been committed, the
request or task that queued it SHALL still succeed, the refusal SHALL be logged, and a PENDING job
left without its task SHALL be re-sent by job recovery. Job recovery SHALL continue with the
remaining jobs when the broker refuses one of them. Errors other than a broker refusal SHALL NOT
be hidden by this rule.

#### Scenario: Sync started while the broker is down

- **WHEN** a signed-in user starts a sync and the broker refuses the task
- **THEN** the endpoint answers as for a started sync, the job is PENDING, the refusal is logged,
  and job recovery re-sends the job once the waiting period has passed

#### Scenario: Restore while the broker is down

- **WHEN** a user restores a dismissed repository and the broker refuses the generation task
- **THEN** the restore succeeds and the dismissal is gone, and the PENDING generation job is
  re-sent by job recovery

#### Scenario: Recovery past a refused send

- **WHEN** job recovery requeues three jobs and the broker refuses the second
- **THEN** the first and third are sent, the second is logged as not queued, and the recovery
  run completes

#### Scenario: Database error while starting a job

- **WHEN** starting a job fails with a database error
- **THEN** the error is raised, not logged as a refused send

### Requirement: Unexpected job failures keep their traceback

When a tracked job, a token revocation or a repository refresh fails for good with an unexpected
error (not a GitHub failure, a typed job error or an expected refusal), the log record SHALL be
at error level and include the traceback. Expected final failures SHALL be logged at warning
level without a traceback. Log records SHALL NOT include tokens or other secrets.

#### Scenario: Bug in a sync job

- **WHEN** a sync job raises an unexpected exception on its last attempt
- **THEN** the job ends FAILED with `internal_error` and the log record is at error level with
  the traceback

#### Scenario: GitHub unavailable

- **WHEN** a job fails for good with `github_unavailable`
- **THEN** the log record is at warning level and has no traceback

#### Scenario: GitHub refuses a revocation

- **WHEN** a token revocation fails for good because GitHub refuses it
- **THEN** the log record is at warning level, has no traceback and contains no token
