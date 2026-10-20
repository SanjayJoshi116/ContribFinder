## MODIFIED Requirements

### Requirement: Analysis runs from stored data
Profile analysis SHALL read only data stored in ContribFinder and SHALL make no GitHub requests. It SHALL run as the final step of every sync and SHALL also be available as a standalone background job for all users or one user, which operators start when weights or the catalog change. Analysis SHALL be idempotent: the same stored data and configuration SHALL produce the same profile. If analysis fails, the previous profile SHALL remain unchanged and the failure SHALL be recorded on the job. When analyses of the same user overlap, an analysis that read its data before the stored profile was analyzed SHALL NOT overwrite that profile. It SHALL complete without changes. Analyses of different users that run at the same time SHALL NOT fail each other.

#### Scenario: No GitHub calls
- **WHEN** a standalone analysis job runs for a user
- **THEN** no GitHub request is made and the profile's analysis time is updated

#### Scenario: Failure keeps previous profile
- **WHEN** analysis fails part-way through
- **THEN** the previous skills, interests and summary are unchanged and the job records the failure with error code `analysis_failed`

#### Scenario: Refresh re-analyzes
- **WHEN** the user presses Refresh and the sync completes
- **THEN** the profile's analysis time is later than before and reflects the newly synced data

#### Scenario: Older snapshot does not win
- **WHEN** a standalone analysis reads the user's data, then a sync's analysis reads newer data and stores its profile, and then the standalone analysis tries to store its result
- **THEN** the stored profile is the sync's, and the standalone job completes without changing it

#### Scenario: Concurrent analyses of different users
- **WHEN** two users' analyses that detect overlapping skills and interests store their profiles at the same time
- **THEN** both complete and neither fails with `analysis_failed`
