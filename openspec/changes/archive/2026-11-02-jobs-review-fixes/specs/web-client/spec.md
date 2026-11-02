## ADDED Requirements

### Requirement: Stalled job
The SPA SHALL keep treating a stalled job (`stalled: true`) as unfinished: it keeps polling its
status and does not react to it as a finished job. It SHALL tell the user that background work
stopped and resumes automatically, instead of the stage text of a running job. While the sync job
is stalled, the user SHALL be able to start a sync (the dashboard's Refresh, onboarding's Try
again).

#### Scenario: Sync stalled on the dashboard
- **WHEN** the sync status returns a RUNNING job with `stalled: true`
- **THEN** the dashboard shows that background work stopped and resumes automatically, and Refresh is enabled

#### Scenario: Stalled job resumes
- **WHEN** a stalled sync is later returned RUNNING with `stalled: false`, then COMPLETED
- **THEN** the stalled notice goes away, and the finished sync triggers the usual refresh once

#### Scenario: Sync stalled during onboarding
- **WHEN** the onboarding page shows a sync job with `stalled: true`
- **THEN** the page shows the stalled notice and a Try again button

#### Scenario: Discovery stalled
- **WHEN** the sync is finished and the discovery status returns a job with `stalled: true`
- **THEN** the dashboard shows the stalled notice instead of "Finding projects…"
