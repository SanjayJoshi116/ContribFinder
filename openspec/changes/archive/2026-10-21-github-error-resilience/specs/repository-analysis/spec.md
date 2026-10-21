## MODIFIED Requirements

### Requirement: Analysis failures are recorded
A repository that GitHub reports as not found, unavailable for legal reasons, or blocked SHALL move to FAILED with a machine-readable error code, and its candidates SHALL be ineligible with the reason `repository_unavailable`. A repository whose analysis hits any other non-retryable GitHub client error SHALL move to FAILED with the error code `client_error`, and one whose GitHub response cannot be interpreted SHALL move to FAILED with the error code `invalid_response`, with the same ineligibility. A FAILED repository SHALL be retried after a configured delay (default 24 hours), counted from when it became FAILED. A rate limit (including a secondary rate limit without `Retry-After`), a transient failure, rejected credentials, cancellation or a database failure SHALL NOT mark the repository FAILED: it SHALL return to the state it had before the analysis started, keeping that state's transition time, and the analysis SHALL be retried later. A renamed or transferred repository SHALL be followed to its current name and SHALL NOT be a failure. A missing README, community file or label SHALL NOT be a failure, and a manifest that cannot be parsed SHALL contribute no dependencies without being a failure. A failure of one repository SHALL NOT fail the discovery job.

#### Scenario: Deleted repository
- **WHEN** GitHub answers 404 for a candidate repository during analysis
- **THEN** the repository is FAILED with error code `not_found`, its candidates are ineligible with the reason `repository_unavailable`, and the discovery job continues with the next repository

#### Scenario: Rate limited during analysis
- **WHEN** a rate limit is hit while a DISCOVERED repository is FETCHING
- **THEN** the repository returns to DISCOVERED with its earlier transition time and is not marked FAILED

#### Scenario: Secondary rate limit is not a block
- **WHEN** GitHub answers a contributors request during analysis with 403, requests remaining, no `Retry-After`, and a message saying a secondary rate limit was exceeded
- **THEN** the repository is not marked FAILED or ineligible, returns to its previous state, and the contributor count is not recorded as unknown

#### Scenario: Grace period not restarted
- **WHEN** a DISCOVERED repository is past its grace period, its analysis is released after a transient failure, and the background refresh runs next
- **THEN** the repository is still due for analysis and is queued

#### Scenario: Renamed repository
- **WHEN** a candidate `old-org/tool` was renamed to `new-org/tool` and GitHub answers with a 301 redirect to the repository's current API location
- **THEN** the analysis completes, and the repository is stored under `new-org/tool` with the same GitHub ID

#### Scenario: Unexpected client error
- **WHEN** GitHub answers a request for one candidate repository with 400, and the discovery job has more repositories to analyze
- **THEN** that repository is FAILED with error code `client_error`, and the discovery job analyzes the remaining repositories and completes

#### Scenario: Response that cannot be interpreted
- **WHEN** GitHub's answer for one candidate repository lacks a field the analysis needs
- **THEN** that repository is FAILED with error code `invalid_response`, and the discovery job continues with the next repository

#### Scenario: Deeply nested manifest in a candidate
- **WHEN** a candidate repository's package.json nests arrays too deeply to parse
- **THEN** the analysis completes with no dependencies from that manifest, and the repository is not FAILED

### Requirement: Background refresh
A periodic background task SHALL refresh, in batches of a configured size (default 50), the repositories that are in at least one developer's pool and are STALE, DISCOVERED and not analyzed within the configured grace period (default 10 minutes), or FAILED and due for retry. A refresh SHALL fetch only the stale data types and SHALL use conditional requests. Repositories in no pool SHALL NOT be refreshed. Refreshing SHALL NOT block any HTTP request.

A refresh that ends without being retried and without marking the repository FAILED (for example a rate-limit wait beyond the maximum, or transient failures that used up the attempts) SHALL record its error code and time on the repository, SHALL keep the repository's state and its stored data, and SHALL NOT be queued again by the background task until a configured delay (default 60 minutes) has passed. A later completed analysis SHALL clear the recorded error.

#### Scenario: Only stale parts fetched
- **WHEN** a STALE repository has only stale metadata and activity signals
- **THEN** the refresh fetches metadata and activity data, does not fetch the README, community files or manifests, and the repository ends RECOMMENDABLE or INDEXED

#### Scenario: Orphan repository not refreshed
- **WHEN** a STALE repository is in no developer's pool
- **THEN** the background task does not refresh it

#### Scenario: Refresh fails without a retry
- **WHEN** a STALE repository's refresh keeps getting 503 until its attempts are used up
- **THEN** the repository is still STALE and eligible as before, its recorded error is `github_unavailable`, and the background task does not queue it again within the configured delay

#### Scenario: Refresh retried after the delay
- **WHEN** the configured delay has passed since a recorded refresh failure, and the next refresh completes
- **THEN** the background task queues the repository, and after the analysis it has no recorded error
