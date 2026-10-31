## MODIFIED Requirements

### Requirement: Recommendation generation job
The system SHALL generate recommendations in a background job per user, tracked like other jobs, that reads only stored data. A job SHALL start when the user's repository discovery completes. At most one generation job SHALL be active per user. When a generation is requested while the user's generation job is already running, that job SHALL be followed by another generation once it ends, whether it completed or failed, so the request is reflected even if the running job loaded its inputs before it. A run that starts after the request (a pending or retrying job) SHALL NOT run again for it. When matched issues are deleted or re-analyzed between ranking and storing, the job SHALL rank again from stored data, at most 3 times in total, and then fail without changing the stored recommendations. A failed generation SHALL keep the user's previous recommendations unchanged. A developer with no eligible candidates SHALL end with no recommendations and a completed job.

#### Scenario: After discovery
- **WHEN** a user's discovery job completes
- **THEN** a recommendation generation job for that user starts in the background

#### Scenario: Failure keeps old results
- **WHEN** a generation job fails while writing
- **THEN** the user's recommendations are exactly those of the previous successful generation

#### Scenario: Restore during a running generation
- **WHEN** a user restores a dismissed repository while their generation job is running
- **THEN** after that job completes another generation runs, and the restored repository can be among its recommendations

#### Scenario: Request while pending
- **WHEN** a generation is requested while the user's generation job is still pending
- **THEN** no further job is added, and the pending job's result reflects the request

#### Scenario: Issues keep changing
- **WHEN** matched issues disappear before every one of 3 attempts to store the result
- **THEN** the job fails and the user's recommendations are exactly those of the previous successful generation

#### Scenario: Restore during a generation that fails
- **WHEN** a user restores a dismissed repository while their generation job is running, and that job then fails
- **THEN** another generation runs after it, and the restored repository can be among its recommendations
