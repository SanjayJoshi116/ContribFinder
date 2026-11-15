## ADDED Requirements

### Requirement: Follow-up job visible with the completion
A job's follow-up (discovery after a completed sync or analysis, a generation after a completed
discovery, the generation rerun requested while a generation ran) SHALL become visible in the same
committed state as the job's completion: a status read that sees the job finished SHALL also see
its follow-up job, when one was started. A follow-up that fails to start SHALL NOT change the
job's outcome, and the follow-up's queued task SHALL be sent only after that state is committed.

#### Scenario: Discovery visible with the completed sync
- **WHEN** a sync ends as COMPLETED and starts a discovery run
- **THEN** no read of the user's jobs sees the sync COMPLETED without the new discovery job

#### Scenario: Follow-up fails to start
- **WHEN** starting the discovery after a completed sync raises an error
- **THEN** the sync stays COMPLETED and the error is logged
