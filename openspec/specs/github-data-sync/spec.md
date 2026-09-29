# github-data-sync Specification

## Purpose

Fetches a signed-in user's public GitHub data (profile, profile README, owned repositories, languages, topics) into ContribFinder. Later profiling and matching stages read it locally instead of calling GitHub on every request.

## Requirements

### Requirement: GitHub profile ingestion
A sync SHALL fetch the authenticated user's GitHub profile and store it: GitHub ID, username, display name, bio, company, location, blog/website, follower count, following count, public repository count and account creation date. Each sync SHALL overwrite values that changed on GitHub.

#### Scenario: Profile stored after sync
- **WHEN** a sync completes for a user whose GitHub profile has name "The Octocat", bio "Builds tools" and 12 public repositories
- **THEN** the stored GitHub profile for that user shows those values and the time of this sync

#### Scenario: Profile values change on GitHub
- **WHEN** the user's bio changed on GitHub since the previous sync and a new sync completes
- **THEN** the stored bio equals the new value and no duplicate profile record exists

### Requirement: Public repository ingestion
A sync SHALL fetch the user's public repositories that they own. For each it SHALL store: GitHub ID, owner, name, full name, description, URL, default branch, stars, forks, open issue count, primary language, license, fork flag, archived flag, creation date, last update date and last push date. Each repository SHALL be stored once and linked to the user as owner. Repositories that GitHub no longer returns for the user SHALL be unlinked from the user on the next successful sync.

#### Scenario: Owned repositories stored
- **WHEN** a sync completes for a user with 3 public owned repositories, one of which is a fork
- **THEN** 3 repositories are linked to the user, with the fork flagged as a fork

#### Scenario: Repository deleted or made private on GitHub
- **WHEN** a repository linked to the user is no longer returned by GitHub and a new sync completes
- **THEN** the repository is no longer linked to the user

#### Scenario: Per-sync repository cap
- **WHEN** the user owns more public repositories than the configured per-sync cap
- **THEN** only the most recently pushed repositories up to the cap are synced, and the job metadata records that the cap was applied

### Requirement: Repository languages
For each synced repository the system SHALL store its language breakdown (language name and byte count), replacing the previous breakdown on each sync.

#### Scenario: Languages stored
- **WHEN** GitHub reports a repository's languages as Python 7000 bytes and TypeScript 3000 bytes
- **THEN** the repository has exactly those two language entries with those byte counts

#### Scenario: Repository with no detected languages
- **WHEN** GitHub reports no languages for a repository
- **THEN** the repository has no language entries and the sync still completes

### Requirement: Repository topics
For each synced repository the system SHALL store the topics GitHub reports, replacing the previous topics on each sync.

#### Scenario: Topics stored
- **WHEN** GitHub reports topics `django` and `rest-api` for a repository
- **THEN** the repository has exactly those two topics

### Requirement: Profile README ingestion
A sync SHALL look for the profile README in the repository named after the user's username, owned by the user. If it exists, the system SHALL store its raw content unchanged and separately from any derived data. A missing profile README SHALL be recorded as absent and SHALL NOT fail the sync.

#### Scenario: Profile README present
- **WHEN** the repository `octocat/octocat` has a README containing "## Skills\nPython"
- **THEN** the stored profile README content equals that text exactly and the profile is marked as having a README

#### Scenario: No profile README
- **WHEN** the user has no `{username}/{username}` repository, or it has no README
- **THEN** the profile is marked as having no README, the sync completes successfully, and the README step reports "not found" rather than an error

### Requirement: Complete paginated results
The system SHALL retrieve every page of paginated GitHub list responses, up to a configured page limit per request sequence. It SHALL NOT silently truncate results below that limit.

#### Scenario: Multiple pages of repositories
- **WHEN** GitHub returns the user's repositories across 3 pages
- **THEN** repositories from all 3 pages are stored

#### Scenario: Page limit reached
- **WHEN** a list has more pages than the configured page limit
- **THEN** the system stops at the limit and records in the job metadata that results were truncated

### Requirement: Rate-limit handling
The system SHALL respect GitHub's primary and secondary rate limits. When GitHub signals that a limit was hit, the system SHALL stop requesting, wait until the time GitHub gives (`Retry-After`, or the rate-limit reset time), capped at a configured maximum, and then resume the sync without repeating completed steps. It SHALL NOT retry immediately in a loop.

#### Scenario: Secondary rate limit with Retry-After
- **WHEN** GitHub answers a sync request with 403 or 429 and `Retry-After: 60`
- **THEN** the job moves to RETRYING, makes no further GitHub requests for at least 60 seconds, then resumes and completes the remaining steps

#### Scenario: Primary rate limit exhausted
- **WHEN** GitHub answers with 403, `X-RateLimit-Remaining: 0` and a reset time 10 minutes ahead
- **THEN** the job moves to RETRYING and resumes no earlier than the reset time

#### Scenario: Wait exceeds maximum
- **WHEN** the required wait exceeds the configured maximum retry delay
- **THEN** the job moves to FAILED with error code `github_rate_limited`

### Requirement: Transient failure handling
The system SHALL retry timeouts, connection errors and GitHub 5xx responses with exponential backoff, up to a configured number of attempts. After the attempts are used up, the job SHALL fail with a safe error code. Completed steps SHALL NOT be re-fetched on retry.

#### Scenario: Temporary GitHub outage
- **WHEN** the repositories request returns 502 once and then succeeds
- **THEN** the job retries after a backoff delay and completes, with the attempt count reflecting the retry

#### Scenario: Persistent failure
- **WHEN** GitHub keeps returning 503 for every attempt
- **THEN** the job moves to FAILED with error code `github_unavailable` after the configured number of attempts

### Requirement: Conditional requests
The system SHALL send conditional requests (ETag) for resources it has fetched before. A `304 Not Modified` response SHALL reuse the previously stored data and SHALL NOT be treated as an error.

#### Scenario: Unchanged repository list
- **WHEN** a second sync requests the repository list and GitHub answers 304 Not Modified
- **THEN** the previously fetched repository list is reused and the sync completes successfully

### Requirement: Credential use during sync
Sync SHALL authenticate to GitHub with the user's stored token. The token SHALL NOT appear in job records, job arguments, error messages or logs. If GitHub rejects the token, or the user has no connected GitHub account, the sync SHALL stop without retrying and report that the user must sign in again.

#### Scenario: Token revoked on GitHub
- **WHEN** GitHub answers a sync request with 401
- **THEN** the job moves to FAILED with error code `github_auth_invalid` and is not retried

#### Scenario: No secrets in job data
- **WHEN** any sync job runs, succeeds or fails
- **THEN** its stored fields, queued task arguments and log output contain no access token

### Requirement: Dependency manifest ingestion
A sync SHALL read root-level dependency manifests for the user's most recently pushed owned non-fork repositories, up to a configured number of repositories (default 30). The supported manifests are requirements.txt, pyproject.toml, package.json, go.mod, Cargo.toml, pom.xml, build.gradle and build.gradle.kts. For each repository the system SHALL store the dependency names found per ecosystem and manifest, replacing the previous set on each sync. Raw manifest contents SHALL NOT be stored. Manifests larger than a configured size SHALL be skipped. An empty repository, a repository without supported manifests, or a manifest that cannot be fetched (not found or forbidden) SHALL be skipped without failing the sync. Rate limits and transient failures SHALL be handled as for other sync requests, and a retried sync SHALL NOT re-read repositories it already finished.

#### Scenario: Manifests stored
- **WHEN** an owned repository has package.json with dependencies `react` and `vite` at its root
- **THEN** the repository's stored dependencies are `react` and `vite` for the npm ecosystem from package.json

#### Scenario: Repository without manifests
- **WHEN** an owned repository has no supported manifest at its root
- **THEN** it has no stored dependencies and the sync completes

#### Scenario: Repository cap
- **WHEN** the user owns 50 non-fork repositories and the cap is 30
- **THEN** manifests are read only for the 30 most recently pushed, and the job metadata records that the cap was applied

#### Scenario: Forks skipped
- **WHEN** an owned repository is a fork
- **THEN** its manifests are not read

### Requirement: External contribution ingestion
A sync SHALL collect the user's public contributions to repositories they do not own:
- merged pull requests authored by the user, up to a configured number;
- public push activity in the recent public events GitHub provides.

For the contributed repositories with the most contributions, up to a configured number (default 20), the system SHALL store repository metadata, languages and topics as for owned repositories. It SHALL link them to the user as contributor with the number of merged pull requests and pushes observed, and the time of the latest one. Contributor links that are no longer observed SHALL be removed on the next successful sync. Private activity SHALL NOT be requested. If GitHub rejects the contribution search for the user as invalid, the step SHALL be recorded as skipped and the sync SHALL complete.

#### Scenario: Merged pull requests recorded
- **WHEN** the user has 3 merged pull requests to `pallets/flask` and 1 to `psf/requests`
- **THEN** both repositories are stored with languages and topics, and linked to the user as contributor with 3 and 1 merged pull requests

#### Scenario: Own repositories excluded
- **WHEN** the user has merged pull requests to a repository they own
- **THEN** that repository is not linked as a contributed repository

#### Scenario: Contribution search rejected
- **WHEN** GitHub answers the contribution search with 422
- **THEN** the contributions step is skipped and the sync completes

#### Scenario: Contribution repository cap
- **WHEN** the user contributed to 35 repositories and the cap is 20
- **THEN** only the 20 repositories with the most contributions are stored and linked, and the job metadata records that the cap was applied
