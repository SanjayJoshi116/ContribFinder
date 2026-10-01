## MODIFIED Requirements

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
