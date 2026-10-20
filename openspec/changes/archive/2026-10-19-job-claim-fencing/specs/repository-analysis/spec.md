## MODIFIED Requirements

### Requirement: Repository processing lifecycle
Each repository SHALL have a processing state: DISCOVERED, FETCHING, ANALYZED, INDEXED, RECOMMENDABLE, STALE, REFRESHING or FAILED, with the time of the last transition.
- A newly found repository is DISCOVERED.
- First analysis moves it DISCOVERED → FETCHING → ANALYZED (data collected) → INDEXED (activity signals computed).
- It then becomes RECOMMENDABLE if it is eligible, or stays INDEXED with its ineligibility reason.
- Stale data moves it to STALE, a refresh moves it to REFRESHING, and a completed refresh returns it to RECOMMENDABLE or INDEXED.
- Eligibility determined by the last completed analysis SHALL be kept while a repository is STALE or REFRESHING.

Only one analysis of a repository SHALL run at a time. Each analysis SHALL hold a claim on the repository and SHALL renew it between the data types it fetches. A claim not renewed for longer than the configured stale-job time SHALL be reclaimable, and reclaiming SHALL replace the earlier claim. Only the analysis holding the current claim SHALL be able to complete, fail or release the repository. An analysis whose claim was replaced SHALL leave the repository's state unchanged.

Moving to FETCHING or REFRESHING and back after a transient failure or cancellation SHALL NOT change the time of the last transition: the repository SHALL return to the state it had before the analysis started, with that state's transition time, in a single atomic step.

#### Scenario: First analysis
- **WHEN** a DISCOVERED, eligible repository is analyzed successfully
- **THEN** it is FETCHING while its data is fetched, passes ANALYZED and INDEXED within the transaction that stores the data, and ends RECOMMENDABLE

#### Scenario: Concurrent analysis
- **WHEN** a repository is FETCHING for one developer's discovery and another developer's discovery reaches it
- **THEN** the second discovery does not fetch it, and its candidate counts as awaiting analysis until the first finishes

#### Scenario: Refresh keeps eligibility
- **WHEN** a RECOMMENDABLE repository becomes STALE
- **THEN** it stays eligible until the refresh completes and re-checks eligibility

#### Scenario: Long analysis is not reclaimed
- **WHEN** an analysis keeps fetching a repository's data types for longer than the stale-job time in total, renewing its claim between them
- **THEN** no other worker reclaims the repository while it runs

#### Scenario: Reclaimed analysis cannot overwrite
- **WHEN** a slow analysis's claim is reclaimed by another worker and the slow analysis then finishes or fails
- **THEN** the repository's state is decided only by the analysis holding the current claim

#### Scenario: Transient failure keeps the retry clock
- **WHEN** a FAILED repository is retried, the retry hits a rate limit, and the repository returns to FAILED
- **THEN** its last-transition time is the time it first became FAILED, so the configured retry delay is not restarted

### Requirement: Analysis failures are recorded
A repository that GitHub reports as not found, unavailable for legal reasons, or blocked SHALL move to FAILED with a machine-readable error code, and its candidates SHALL be ineligible with the reason `repository_unavailable`. A FAILED repository SHALL be retried after a configured delay (default 24 hours), counted from when it became FAILED. A rate limit or transient failure SHALL NOT mark the repository FAILED: it SHALL return to the state it had before the analysis started, keeping that state's transition time, and the analysis SHALL be retried later. A missing README, community file or label SHALL NOT be a failure. A failure of one repository SHALL NOT fail the discovery job.

#### Scenario: Deleted repository
- **WHEN** GitHub answers 404 for a candidate repository during analysis
- **THEN** the repository is FAILED with error code `not_found`, its candidates are ineligible with the reason `repository_unavailable`, and the discovery job continues with the next repository

#### Scenario: Rate limited during analysis
- **WHEN** a rate limit is hit while a DISCOVERED repository is FETCHING
- **THEN** the repository returns to DISCOVERED with its earlier transition time and is not marked FAILED

#### Scenario: Grace period not restarted
- **WHEN** a DISCOVERED repository is past its grace period, its analysis is released after a transient failure, and the background refresh runs next
- **THEN** the repository is still due for analysis and is queued
