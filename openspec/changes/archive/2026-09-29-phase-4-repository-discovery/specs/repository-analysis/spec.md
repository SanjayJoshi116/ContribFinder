## Purpose

Collects and keeps fresh the public data about candidate repositories that matching needs, shared across developers, with an explicit processing lifecycle so that failures and stale data are visible as state rather than silently treated as missing.

## ADDED Requirements

### Requirement: Repository data collection
For each candidate repository the system SHALL collect and store:
- metadata: owner, name, description, URL, default branch, stars, forks, open issues, primary language, license, creation, update and push dates, archived and fork flags;
- languages (bytes) and topics;
- the README;
- whether it has CONTRIBUTING documentation, a code of conduct, issue templates and a pull request template;
- whether it has a `good first issue` and a `help wanted` label;
- root dependency manifests, parsed into dependency names the same way as for the developer's own repositories;
- activity signals (see `repository-activity`).

Repository data SHALL be stored once and shared by every developer whose pool contains the repository. A repository whose data is still fresh SHALL NOT be fetched again for another developer's discovery.

#### Scenario: Candidate analyzed
- **WHEN** a newly discovered candidate is analyzed
- **THEN** its metadata, languages, topics, README, community files, labels, dependencies and activity snapshot are stored

#### Scenario: Shared analysis
- **WHEN** two developers' discovery runs both find `encode/httpx` and its data is fresh after the first run
- **THEN** the second run makes no request for `encode/httpx` beyond its search result

#### Scenario: Missing optional files
- **WHEN** a repository has no README, no CONTRIBUTING file and no labels
- **THEN** it is analyzed successfully and records that each of these is absent

### Requirement: README storage
The raw README of a candidate repository SHALL be stored separately from the repository metadata and from anything derived from it, truncated to a configured maximum size (default 200 KB). Rendered HTML SHALL NOT be stored. A repository without a README SHALL be recorded as having none.

#### Scenario: Large README truncated
- **WHEN** a repository's README is 500 KB and the limit is 200 KB
- **THEN** the first 200 KB are stored and the stored record is marked truncated

### Requirement: Repository processing lifecycle
Each repository SHALL have a processing state: DISCOVERED, FETCHING, ANALYZED, INDEXED, RECOMMENDABLE, STALE, REFRESHING or FAILED, with the time of the last transition.
- A newly found repository is DISCOVERED.
- First analysis moves it DISCOVERED → FETCHING → ANALYZED (data collected) → INDEXED (activity signals computed).
- It then becomes RECOMMENDABLE if it is eligible, or stays INDEXED with its ineligibility reason.
- Stale data moves it to STALE, a refresh moves it to REFRESHING, and a completed refresh returns it to RECOMMENDABLE or INDEXED.
- Eligibility determined by the last completed analysis SHALL be kept while a repository is STALE or REFRESHING.

Only one analysis of a repository SHALL run at a time. An analysis that stopped updating for longer than the configured stale-job time SHALL be reclaimable.

#### Scenario: First analysis
- **WHEN** a DISCOVERED, eligible repository is analyzed successfully
- **THEN** it passes through FETCHING, ANALYZED and INDEXED and ends RECOMMENDABLE

#### Scenario: Concurrent analysis
- **WHEN** a repository is FETCHING for one developer's discovery and another developer's discovery reaches it
- **THEN** the second discovery does not fetch it, and its candidate counts as awaiting analysis until the first finishes

#### Scenario: Refresh keeps eligibility
- **WHEN** a RECOMMENDABLE repository becomes STALE
- **THEN** it stays eligible until the refresh completes and re-checks eligibility

### Requirement: Analysis failures are recorded
A repository that GitHub reports as not found, unavailable for legal reasons, or blocked SHALL move to FAILED with a machine-readable error code, and its candidates SHALL be ineligible with the reason `repository_unavailable`. A FAILED repository SHALL be retried after a configured delay (default 24 hours). A rate limit or transient failure SHALL NOT mark the repository FAILED: it SHALL return to the state it had before the analysis started, and the analysis SHALL be retried later. A missing README, community file or label SHALL NOT be a failure. A failure of one repository SHALL NOT fail the discovery job.

#### Scenario: Deleted repository
- **WHEN** GitHub answers 404 for a candidate repository during analysis
- **THEN** the repository is FAILED with error code `not_found`, its candidates are ineligible with the reason `repository_unavailable`, and the discovery job continues with the next repository

#### Scenario: Rate limited during analysis
- **WHEN** a rate limit is hit while a DISCOVERED repository is FETCHING
- **THEN** the repository returns to DISCOVERED and is not marked FAILED

### Requirement: Per-data-type freshness
The system SHALL record, per repository, when its metadata, README, community files and labels, dependencies and activity signals were last fetched. Each data type SHALL become stale after its own configured age (defaults: metadata 12 hours, activity 24 hours, community files and labels 7 days, dependencies 7 days, README 7 days). A periodic background task SHALL move RECOMMENDABLE and INDEXED repositories with any stale data type to STALE and record which data types are stale.

#### Scenario: Metadata stale
- **WHEN** a RECOMMENDABLE repository's metadata was fetched 13 hours ago, the metadata age limit is 12 hours, and the README was fetched yesterday
- **THEN** the periodic task marks it STALE with metadata stale and README not stale

### Requirement: Background refresh
A periodic background task SHALL refresh, in batches of a configured size (default 50), the repositories that are in at least one developer's pool and are STALE, DISCOVERED and not analyzed within the configured grace period (default 10 minutes), or FAILED and due for retry. A refresh SHALL fetch only the stale data types and SHALL use conditional requests. Repositories in no pool SHALL NOT be refreshed. Refreshing SHALL NOT block any HTTP request.

#### Scenario: Only stale parts fetched
- **WHEN** a STALE repository has only stale metadata and activity signals
- **THEN** the refresh fetches metadata and activity data, does not fetch the README, community files or manifests, and the repository ends RECOMMENDABLE or INDEXED

#### Scenario: Orphan repository not refreshed
- **WHEN** a STALE repository is in no developer's pool
- **THEN** the background task does not refresh it

### Requirement: Credentials for shared repository data
Analysis during a developer's discovery run SHALL use that developer's token. Background refresh SHALL NOT use any user's token: it SHALL authenticate with the application's OAuth client credentials and request public data only. If client credentials are not configured, background refresh SHALL do nothing and log a warning. Neither tokens nor the client secret SHALL appear in repository records, task arguments, error messages or logs.

#### Scenario: Refresh without a user
- **WHEN** the background task refreshes a stale repository
- **THEN** its GitHub requests are authenticated with the application's client credentials and no user token is decrypted

#### Scenario: No secrets stored or logged
- **WHEN** any repository analysis or refresh runs, succeeds or fails
- **THEN** stored repository fields, queued task arguments and log output contain no access token and no client secret
