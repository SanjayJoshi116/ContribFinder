# repository-analysis Specification

## Purpose

Collects and keeps fresh the public data about candidate repositories that matching needs, shared across developers, with an explicit processing lifecycle so that failures and stale data are visible as state rather than silently treated as missing.
## Requirements
### Requirement: Repository data collection
For each candidate repository the system SHALL collect and store:
- metadata: owner, name, description, URL, default branch, stars, forks, open issues, primary language, license, creation, update and push dates, archived and fork flags;
- languages (bytes) and topics;
- the README;
- whether it has CONTRIBUTING documentation, a code of conduct, issue templates and a pull request template;
- whether it has a label that the issue label normalization (`issue-analysis` "Label normalization") maps to `good first issue`, and one it maps to `help wanted`;
- root dependency manifests, parsed into dependency names the same way as for the developer's own repositories;
- setup facts: whether CI configuration, tests, a dev environment configuration and a Docker Compose file were found;
- activity signals (see `repository-activity`);
- its open issues (see `issue-ingestion`).

Repository data SHALL be stored once and shared by every developer whose pool contains the repository. A repository whose data is still fresh SHALL NOT be fetched again for another developer's discovery.

Setup facts SHALL be detected from the repository's root entries and, when the root has a `.github` directory, the entries of `.github/workflows`, and SHALL be refreshed together with the dependency manifests, from the same root listing:
- CI: a workflow file (`.yml` or `.yaml`) in `.github/workflows`, or a root CI configuration of another service (for example `.gitlab-ci.yml`, `.travis.yml`, a `.circleci` directory, `azure-pipelines.yml`, `Jenkinsfile`);
- tests: a root test directory (for example `tests`, `test`, `spec`, `__tests__`) or a root test-runner configuration (for example `pytest.ini`, `tox.ini`, `jest.config.*`, `vitest.config.*`, `phpunit.xml`);
- dev environment: a `.devcontainer` directory, a `.devcontainer.json` file or a `.gitpod.yml` file;
- Docker Compose: `docker-compose.yml`, `docker-compose.yaml`, `compose.yml` or `compose.yaml`.

A fact not found SHALL be stored as not found, which means only that nothing matched at those locations; a repository not yet analyzed for them SHALL have them unknown. Setup facts SHALL NOT be used by any scoring signal, reason, filter or evaluation dataset.

#### Scenario: Candidate analyzed
- **WHEN** a newly discovered candidate is analyzed
- **THEN** its metadata, languages, topics, README, community files, labels, dependencies, setup facts, activity snapshot and open issues are stored

#### Scenario: Shared analysis
- **WHEN** two developers' discovery runs both find `encode/httpx` and its data is fresh after the first run
- **THEN** the second run makes no request for `encode/httpx` beyond its search result

#### Scenario: Missing optional files
- **WHEN** a repository has no README, no CONTRIBUTING file, no labels and no open issues
- **THEN** it is analyzed successfully and records that each of these is absent

#### Scenario: Entry labels with a scope or an alias
- **WHEN** a repository's labels are `type: good first issue` and `contributions welcome`, and issue analysis maps them to `good first issue` and `help wanted`
- **THEN** the repository is stored as having a `good first issue` and a `help wanted` label

#### Scenario: Setup facts found
- **WHEN** a repository's root holds `.github` (with `ci.yml` in `.github/workflows`), `tests/`, `.devcontainer/` and `docker-compose.yml`
- **THEN** CI, tests, dev environment and Docker Compose are all stored as found

#### Scenario: Nothing found
- **WHEN** a repository's root holds only `README.md` and `main.go`
- **THEN** its four setup facts are stored as not found, no request is made for `.github/workflows`, and the analysis succeeds

#### Scenario: Empty workflows directory
- **WHEN** a repository's root holds a `.github` directory whose `workflows` directory is missing or holds no `.yml` or `.yaml` file
- **THEN** CI is stored as not found, unless a root CI configuration of another service was found

#### Scenario: Analyzed before setup facts existed
- **WHEN** a repository's dependencies were last fetched before setup facts were collected
- **THEN** its setup facts are unknown until its dependencies are refreshed

#### Scenario: Setup facts never change ranking
- **WHEN** two otherwise identical candidates differ only in their setup facts
- **THEN** they receive the same score, reasons and match label

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
A repository that GitHub reports as not found, unavailable for legal reasons, or blocked SHALL move to FAILED with a machine-readable error code, and its candidates SHALL be ineligible with the reason `repository_unavailable`. A repository whose analysis hits any other non-retryable GitHub client error SHALL move to FAILED with the error code `client_error`, and one whose GitHub response cannot be interpreted SHALL move to FAILED with the error code `invalid_response`, with the same ineligibility. A FAILED repository SHALL be retried after a configured delay (default 24 hours), counted from when it became FAILED. The retry SHALL fetch every data type, whichever data types the refresh asked for, so a repository that no longer exists is never made eligible again. A rate limit (including a secondary rate limit without `Retry-After`), a transient failure, rejected credentials, cancellation or a database failure SHALL NOT mark the repository FAILED: it SHALL return to the state it had before the analysis started, keeping that state's transition time, and the analysis SHALL be retried later. A renamed or transferred repository SHALL be followed to its current name and SHALL NOT be a failure.

Stored repository rows SHALL NOT be deleted because another repository took their name. When storing a repository finds its name held by a stored repository with a different GitHub ID, the holder SHALL give the name up: it keeps its data, candidates, saves and dismissals, is marked as needing a metadata refresh, and, because its name and URL are no longer its own, SHALL be ineligible with the reason `name_released` (not RECOMMENDABLE) until that refresh decides its eligibility again. Its next analysis SHALL look it up by GitHub ID, store it under its current name, and mark it FAILED with `not_found` only when GitHub no longer has that ID. The same applies when a lookup by name returns a repository with a different GitHub ID.

A missing README, community file or label SHALL NOT be a failure, and a manifest that cannot be parsed SHALL contribute no dependencies without being a failure. A failure of one repository SHALL NOT fail the discovery job.

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

#### Scenario: Name taken by a new repository
- **WHEN** stored repository `org/tool` (GitHub ID 1) was renamed to `org/tool-legacy`, a new repository `org/tool` (GitHub ID 2) was created, and a search stores GitHub ID 2
- **THEN** GitHub ID 1 gives up the name, keeps its candidates, is not recommended until resolved, and its next analysis looks it up by ID, stores it as `org/tool-legacy` and decides its eligibility again

#### Scenario: Released name of a deleted repository
- **WHEN** a repository gave up its name and GitHub answers 404 for its GitHub ID
- **THEN** it is FAILED with error code `not_found` and ineligible with the reason `repository_unavailable`

#### Scenario: Failed repository retried for one data type
- **WHEN** a README refresh queued earlier runs for a repository that is now FAILED and due for retry, and GitHub answers 404 for the repository
- **THEN** the retry fetches the repository's metadata, and the repository stays FAILED and ineligible

#### Scenario: Unexpected client error
- **WHEN** GitHub answers a request for one candidate repository with 400, and the discovery job has more repositories to analyze
- **THEN** that repository is FAILED with error code `client_error`, and the discovery job analyzes the remaining repositories and completes

#### Scenario: Response that cannot be interpreted
- **WHEN** GitHub's answer for one candidate repository lacks a field the analysis needs
- **THEN** that repository is FAILED with error code `invalid_response`, and the discovery job continues with the next repository

#### Scenario: Deeply nested manifest in a candidate
- **WHEN** a candidate repository's package.json nests arrays too deeply to parse
- **THEN** the analysis completes with no dependencies from that manifest, and the repository is not FAILED

### Requirement: Per-data-type freshness
The system SHALL record, per repository, when its metadata, README, community files and labels, dependencies, activity signals and issues were last fetched. Each data type SHALL become stale after its own configured age (defaults: issues 6 hours, metadata 12 hours, activity 24 hours, community files and labels 7 days, dependencies 7 days, README 7 days). A periodic background task SHALL move RECOMMENDABLE and INDEXED repositories with any stale data type to STALE and record which data types are stale.

#### Scenario: Metadata stale
- **WHEN** a RECOMMENDABLE repository's metadata was fetched 13 hours ago, the metadata age limit is 12 hours, and the README was fetched yesterday
- **THEN** the periodic task marks it STALE with metadata stale and README not stale

#### Scenario: Issues stale
- **WHEN** a RECOMMENDABLE repository's issues were fetched 7 hours ago, the issues age limit is 6 hours, and every other data type is fresh
- **THEN** the periodic task marks it STALE with only issues stale

### Requirement: Background refresh
A periodic background task SHALL refresh, in batches of a configured size (default 50), the repositories that are in at least one developer's pool and are STALE, DISCOVERED and not analyzed within the configured grace period (default 10 minutes), or FAILED and due for retry. A refresh SHALL fetch only the data types that are stale when it runs, also when it was queued for particular data types, and SHALL use conditional requests. Repositories in no pool SHALL NOT be refreshed. Refreshing SHALL NOT block any HTTP request.

A repository queued for a refresh SHALL NOT be queued again while that refresh can still run: until the configured stale-job time plus the maximum retry delay has passed since it was queued or since its refresh last scheduled a retry, or until an analysis completes or fails it. A refresh whose task could not be sent SHALL NOT count as queued. Overlapping background runs SHALL NOT queue the same repository twice. The recovery of an analysis abandoned by a dead worker SHALL NOT wait for this. A refresh that finds nothing stale on a repository that is not STALE (another analysis refreshed it after it was queued) SHALL change nothing, not even the time of the last transition.

A repository that gives up its name and is in at least one developer's pool SHALL have its refresh queued once the change that released the name is committed, without waiting for the periodic task, and SHALL count as queued from then on. This SHALL NOT apply to a repository that is FAILED or whose queued refresh can still run; those keep the paths above. A repository that another analysis holds SHALL NOT be queued then; that analysis, which discards what it fetched under the old name, SHALL queue its refresh again when it ends. It SHALL NOT apply when the application's client credentials are not configured or when background tasks run inline: the periodic task stays the fallback, and storing a repository SHALL NOT run another repository's analysis. A recorded refresh failure SHALL NOT hold this refresh back, unless GitHub rejected the application's client credentials within the configured delay.

A refresh that ends without being retried and without marking the repository FAILED (for example a rate-limit wait beyond the maximum, transient failures that used up the attempts, or rejected client credentials) SHALL record its error code and time on the repository, SHALL keep the repository's state and its stored data, and SHALL NOT be queued again by the background task until a configured delay (default 60 minutes) has passed. The failure SHALL NOT be recorded on a repository that another analysis holds, or that another analysis completed or failed after this refresh started. The delay SHALL NOT hold back a FAILED repository's retry or the recovery of an analysis abandoned by a dead worker. A later completed analysis SHALL clear the recorded error.

#### Scenario: Only stale parts fetched
- **WHEN** a STALE repository has only stale metadata and activity signals
- **THEN** the refresh fetches metadata and activity data, does not fetch the README, community files or manifests, and the repository ends RECOMMENDABLE or INDEXED

#### Scenario: Queued part no longer stale
- **WHEN** an issues refresh was queued, and another analysis fetched the repository's issues before it runs
- **THEN** the refresh does not fetch the issues again

#### Scenario: Queued part refreshed meanwhile
- **WHEN** an issues refresh was queued for a STALE repository, and a discovery run's analysis refreshed it to RECOMMENDABLE before the refresh runs
- **THEN** the refresh fetches nothing and leaves the repository's state and transition time unchanged

#### Scenario: Queued refresh not queued twice
- **WHEN** a STALE repository was queued 15 minutes ago and its refresh is waiting for a retry
- **THEN** the next background run does not queue it again

#### Scenario: Lost refresh queued again
- **WHEN** a STALE repository was queued and its refresh never ran, and the stale-job time plus the maximum retry delay has passed
- **THEN** the next background run queues it again

#### Scenario: Orphan repository not refreshed
- **WHEN** a STALE repository is in no developer's pool
- **THEN** the background task does not refresh it

#### Scenario: Released name refreshed right away
- **WHEN** a discovery search stores `org/tool` with GitHub ID 2 while the pooled RECOMMENDABLE repository with GitHub ID 1 holds that name
- **THEN** after the search's transaction commits, a refresh of the repository with GitHub ID 1 is queued and stamped as queued, the next periodic run does not queue it again, and its analysis looks it up by GitHub ID

#### Scenario: Released name rolled back
- **WHEN** the transaction that released a name rolls back
- **THEN** no refresh is queued for the holder

#### Scenario: Released name of a repository in no pool
- **WHEN** a repository in no developer's pool gives up its name
- **THEN** no refresh is queued for it

#### Scenario: Released name while analyzed
- **WHEN** a pooled repository gives up its name while its README refresh, fetched by the old name, is running
- **THEN** no refresh is queued while that analysis holds it; the analysis discards the README, restores the repository and queues its refresh again

#### Scenario: Released name after rejected credentials
- **WHEN** a pooled repository gives up its name within the configured delay after a refresh recorded `github_auth_invalid`
- **THEN** no refresh is queued for it, and the periodic task refreshes it after the delay

#### Scenario: Released name without a worker
- **WHEN** a pooled repository gives up its name while background tasks run inline
- **THEN** no refresh runs, it is not stamped as queued, and the periodic task refreshes it later

#### Scenario: Refresh fails without a retry
- **WHEN** a STALE repository's refresh keeps getting 503 until its attempts are used up
- **THEN** the repository is still STALE and eligible as before, its recorded error is `github_unavailable`, and the background task does not queue it again within the configured delay

#### Scenario: Rejected client credentials
- **WHEN** GitHub rejects the application's client credentials during a refresh
- **THEN** the repository keeps its state, its recorded error is `github_auth_invalid`, and the background task does not queue it again within the configured delay

#### Scenario: Completed by another run meanwhile
- **WHEN** a refresh fails after another analysis completed the same repository
- **THEN** the repository keeps the other analysis's result with no recorded error

#### Scenario: Refresh retried after the delay
- **WHEN** the configured delay has passed since a recorded refresh failure, and the next refresh completes
- **THEN** the background task queues the repository, and after the analysis it has no recorded error

#### Scenario: Retried refresh stays queued
- **WHEN** a queued refresh hits rate limits and schedules its second retry after the stale-job time plus the maximum retry delay has passed since it was queued
- **THEN** the next background run does not queue the repository again, because the retry renewed its queued time

#### Scenario: Refresh task not sent
- **WHEN** the background run picks three repositories and the broker refuses the second task
- **THEN** the first and third repositories count as queued, the second does not, and the next background run can queue it

### Requirement: Credentials for shared repository data
Analysis during a developer's discovery run SHALL use that developer's token. Background refresh SHALL NOT use any user's token: it SHALL authenticate with the application's OAuth client credentials and request public data only. If client credentials are not configured, background refresh SHALL do nothing and log a warning. Neither tokens nor the client secret SHALL appear in repository records, task arguments, error messages or logs.

#### Scenario: Refresh without a user
- **WHEN** the background task refreshes a stale repository
- **THEN** its GitHub requests are authenticated with the application's client credentials and no user token is decrypted

#### Scenario: No secrets stored or logged
- **WHEN** any repository analysis or refresh runs, succeeds or fails
- **THEN** stored repository fields, queued task arguments and log output contain no access token and no client secret

### Requirement: Identity confirmed before a refresh without metadata
A refresh that does not fetch a repository's metadata SHALL first look the repository up by its stored name and SHALL continue under that name only when GitHub answers with the same GitHub ID under the stored name. When GitHub answers with the same GitHub ID under another name (a rename it redirects), that answer SHALL be stored as the repository's metadata. When GitHub answers with another GitHub ID or not found, the refresh SHALL fetch the repository's metadata by GitHub ID, without asking for the name again. In both cases the other data types SHALL be fetched under the name GitHub gives for that ID. Data that GitHub serves for another GitHub ID SHALL NOT be stored under the repository.

#### Scenario: Name taken before an issues refresh
- **WHEN** stored repository `org/tool` (GitHub ID 1) was renamed on GitHub to `org/tool-legacy`, a new repository `org/tool` (GitHub ID 2) was created and is not stored, and an issues-only refresh of GitHub ID 1 runs
- **THEN** the refresh fetches GitHub ID 1's metadata by ID, stores it as `org/tool-legacy`, and stores the issues of `org/tool-legacy`, never those of GitHub ID 2

#### Scenario: Renamed before a README refresh
- **WHEN** stored repository `org/tool` (GitHub ID 1) was renamed to `org/tool-new`, and a README-only refresh runs
- **THEN** the lookup of `org/tool` answers GitHub ID 1 as `org/tool-new`, that answer is stored as the metadata (no lookup by ID), and the README of `org/tool-new` is stored

#### Scenario: Same repository
- **WHEN** an issues-only refresh runs and GitHub answers the lookup of the stored name with the same GitHub ID
- **THEN** the refresh fetches and stores only the issues

#### Scenario: Deleted before a README refresh
- **WHEN** a README-only refresh runs, GitHub answers the stored name with not found, and answers the lookup by GitHub ID with not found
- **THEN** the repository is FAILED with error code `not_found` and ineligible with the reason `repository_unavailable`

### Requirement: Repository names compare case-insensitively
When storing a repository looks for a stored repository holding the same name (see "Analysis failures are recorded"), names SHALL be compared case-insensitively, as GitHub compares them. A holder whose stored name differs only in letter case SHALL give the name up as any other holder.

#### Scenario: Recreated with different case
- **WHEN** stored repository `Org/Tool` (GitHub ID 1) was deleted on GitHub, a new repository `org/tool` (GitHub ID 2) was created, and a search stores GitHub ID 2
- **THEN** GitHub ID 1 gives up its name, is ineligible as `name_released`, and its refresh is queued as for any released name

#### Scenario: Same repository with a case change
- **WHEN** a stored repository `org/Tool` is stored again under `org/tool` with the same GitHub ID
- **THEN** no name is released and the repository is stored as `org/tool`

### Requirement: Broker refusal while queuing a released name
When the refresh of a repository that released its name cannot be sent because the broker refuses the task, the change that released the name SHALL still succeed with everything it stored. The repository whose task was refused SHALL NOT count as queued, so the periodic background task can queue it, and every other repository of that change SHALL still have its refresh sent.

#### Scenario: Broker down after a search
- **WHEN** a discovery search stores `org/tool` (GitHub ID 3) while pooled repositories `Org/Tool` (GitHub ID 1) and `ORG/TOOL` (GitHub ID 2) hold that name, and the broker refuses the first of their two refresh tasks
- **THEN** the search's results stay stored and its step does not fail, the second task is sent, and the first repository is not stamped as queued
