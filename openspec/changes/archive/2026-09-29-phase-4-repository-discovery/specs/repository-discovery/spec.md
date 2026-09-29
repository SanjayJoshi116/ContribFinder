## Purpose

Builds each developer's pool of candidate open-source repositories from their evidence-backed profile, records why every repository entered the pool, and removes clearly unsuitable repositories before any ranking happens.

## ADDED Requirements

### Requirement: Search queries from the developer profile
The system SHALL generate GitHub repository search queries from the developer's stored profile, using these strategies:
- **language search**: the developer's top language skills;
- **skill search**: their top non-language skills that have a GitHub topic (frameworks, libraries, databases, tools);
- **interest search**: their detected interests, through each interest's topics;
- **topic search**: the topics that recur across their own non-fork repositories and are not already covered by a skill or interest query.

Skills whose only evidence is a README mention SHALL NOT generate queries. The number of queries per run SHALL NOT exceed a configured budget (default 10), split across strategies by configured shares, and budget a strategy cannot use SHALL pass to the next strategy. Every query SHALL restrict results to public, non-archived, non-fork repositories that were pushed within the configured window (default 180 days), have at least the configured number of stars (default 20), and are not owned by the developer. The same profile and configuration SHALL produce the same queries in the same order. Generation SHALL NOT call GitHub.

#### Scenario: Queries from skills and interests
- **WHEN** the developer's top skills are Python and Django (with dependency evidence) and their top interest is developer tooling
- **THEN** the queries include a Python language search, a Django skill search and a developer-tooling interest search, each restricted to public, non-archived, non-fork, recently pushed repositories with enough stars that the developer does not own

#### Scenario: README-only skill ignored
- **WHEN** the developer's only evidence for Rust is a README mention
- **THEN** no query is generated for Rust

#### Scenario: Budget respected
- **WHEN** the profile could produce 25 queries and the budget is 10
- **THEN** exactly 10 queries are run, allocated by the configured strategy shares

#### Scenario: Sparse profile
- **WHEN** the developer has no skills or interests that qualify for a query
- **THEN** no search is made, the discovery job completes, and the pool contains only previously interacted repositories, if any

### Requirement: Candidate search
The system SHALL run the generated queries against GitHub repository search with the developer's own token. It SHALL keep at most the configured number of results per query (default 30), and store the metadata of each result as a shared repository. It SHALL NOT index repositories that no query or interaction produced. A query that GitHub rejects as invalid SHALL be skipped and recorded, without failing the run. Rate limits and transient failures SHALL be handled as for sync requests, and a retried run SHALL NOT repeat queries it already completed.

#### Scenario: Results stored
- **WHEN** a Python language search returns 30 repositories
- **THEN** those 30 repositories (minus pre-filtered ones) are stored with their metadata and topics, and become candidates of the developer

#### Scenario: Invalid query skipped
- **WHEN** GitHub answers one of 10 queries with 422
- **THEN** that query is recorded as skipped in the job metadata, the other 9 run, and the job completes

#### Scenario: Retry resumes
- **WHEN** a run hits a search rate limit after 4 of 10 queries and is retried
- **THEN** the retried run executes only the remaining 6 queries

### Requirement: Previously interacted repositories
Repositories the developer is linked to as a contributor SHALL be added to their pool with the source `previously_interacted`, without a search. The minimum-stars rule SHALL NOT apply to them. Repositories the developer owns SHALL never be candidates.

#### Scenario: Contributed repository added
- **WHEN** the developer has merged pull requests in `pallets/flask`
- **THEN** `pallets/flask` is a candidate with the source `previously_interacted`

#### Scenario: Own repository excluded
- **WHEN** a search result is a repository the developer owns
- **THEN** it is not added to the developer's pool

### Requirement: Discovery provenance
For every candidate the system SHALL record each way it was discovered: the source (`language_search`, `topic_search`, `skill_search`, `interest_search`, `similar_repo` or `previously_interacted`), the query text for search sources, the result's rank within that query, and when that source first and last found it. A repository found by several sources or queries SHALL be one candidate with several discovery records. The candidate SHALL record when it was first discovered and when a discovery run last found it.

#### Scenario: Found by two strategies
- **WHEN** `encode/httpx` is returned by the Python language search at rank 4 and by the developer-tooling interest search at rank 12
- **THEN** the developer has one candidate for `encode/httpx` with two discovery records, holding those sources, queries and ranks

#### Scenario: Rediscovered later
- **WHEN** a later run finds an existing candidate again through the same query
- **THEN** the candidate's last-found time is updated, and no duplicate candidate or discovery record is created

### Requirement: Candidate pre-filtering
Before a search result becomes a candidate, the system SHALL reject it if it is archived, a fork, not pushed within the configured window, without a detected license, below the minimum stars (except previously interacted repositories), or owned by the developer. Filtering SHALL be a separate stage from search and ranking. The number of rejections per reason SHALL be recorded on the discovery job. Rejected results SHALL NOT be stored as candidates.

#### Scenario: Archived result rejected
- **WHEN** a search result is archived
- **THEN** it does not become a candidate and the job's rejection count for `archived` increases by one

#### Scenario: Unlicensed result rejected
- **WHEN** a search result has no detected license
- **THEN** it does not become a candidate and the rejection is counted as `no_license`

### Requirement: Candidate eligibility
After a candidate repository is analyzed, the system SHALL re-check the same repository-level rules on the fresh data (archived, fork, push window, license) and record whether it is eligible, and if not, why. An ineligible candidate SHALL stay in the pool with its reason, so it can be inspected, but SHALL NOT be counted as an eligible candidate.

#### Scenario: Archived after discovery
- **WHEN** a candidate found last week is archived by its owner and then refreshed
- **THEN** the candidate is ineligible with the reason `archived`

### Requirement: Candidate pool maintenance
A candidate that no discovery run has found for the configured retention period (default 30 days) SHALL be removed from the pool. The pool SHALL NOT exceed the configured size (default 300). When it would, the system SHALL keep the candidates first in analysis order (previously interacted, then best search rank, then most recently found) and remove the rest, so the pool that remains is the one that is analyzed. Deleting the developer profile SHALL delete its candidates and discovery records. Shared repository data SHALL NOT be deleted when a candidate is removed.

#### Scenario: Expired candidate
- **WHEN** a candidate was last found 31 days ago and the retention period is 30 days
- **THEN** the next discovery run removes it from the pool

#### Scenario: Pool cap
- **WHEN** a run would bring the pool to 320 candidates and the cap is 300
- **THEN** the 20 candidates with the worst search rank that are not previously interacted are removed

#### Scenario: Small pool for fast runs
- **WHEN** the cap is 10 and a run finds 220 candidates
- **THEN** the pool keeps the 10 best-ranked candidates, which are the ones the run analyzed

### Requirement: Discovery job
Discovery SHALL run as a background job per user, tracked like a sync job: at most one active job per user, a status (PENDING, RUNNING, RETRYING, COMPLETED, FAILED or CANCELLED), attempts, a machine-readable error code on failure, and per-step status for the steps queries, search, interactions, analysis and pool, in that order. A retried job SHALL resume after its completed steps and completed per-item work. A discovery job SHALL NOT start for a user without an analyzed developer profile or without a connected GitHub account. HTTP requests SHALL NOT wait for discovery.

#### Scenario: Successful discovery
- **WHEN** a discovery job runs to completion
- **THEN** its status is COMPLETED, every step is done or skipped, and the job metadata records the queries run, results found, rejections per reason and repositories analyzed

#### Scenario: Token rejected
- **WHEN** GitHub answers a discovery search with 401
- **THEN** the job ends as FAILED with error code `github_auth_invalid` and is not retried

#### Scenario: No profile yet
- **WHEN** discovery is requested for a user whose profile has never been analyzed
- **THEN** no discovery job is created

### Requirement: Discovery status endpoint
The system SHALL provide `GET /api/v1/discovery/status` with the requesting user's most recent discovery job (status, steps, error code, start and completion times), the completion time of their last successful discovery, and pool counts: total candidates, eligible, awaiting analysis, ineligible, and candidates per source. It SHALL be served from stored data without calling GitHub, and SHALL expose only the requesting user's data.

#### Scenario: Status after discovery
- **WHEN** a user whose discovery completed with 120 candidates (95 eligible, 15 awaiting analysis, 10 ineligible) requests the status
- **THEN** the response contains the COMPLETED job, the last successful discovery time and those counts

#### Scenario: Never discovered
- **WHEN** a user without any discovery job requests the status
- **THEN** the response has no job, a null last successful discovery time and zero counts

#### Scenario: Signed out
- **WHEN** an unauthenticated client requests the status
- **THEN** the system responds with HTTP 401

### Requirement: Candidate list endpoint
The system SHALL provide `GET /api/v1/discovery/candidates`: a paginated list of the requesting user's candidates. Each item SHALL contain the repository's name, owner, description, URL, primary language, stars, topics and license, its processing state, eligibility and reason, its latest activity label, the candidate's discovery records, and when it was first and last found. The list SHALL be filterable by source, eligibility and activity label. It SHALL list eligible candidates first, then candidates awaiting analysis, then ineligible ones; within each group, previously-interacted candidates first, then by best search rank, then by repository name (the order in which discovery analyses them). It SHALL NOT imply relevance: the response SHALL contain no score or rank across candidates. It SHALL be served from stored data with a query count that does not grow with the page size.

#### Scenario: Filter by source
- **WHEN** the user requests `GET /api/v1/discovery/candidates?source=previously_interacted`
- **THEN** only candidates with a previously-interacted discovery record are returned

#### Scenario: Another user's candidates are not visible
- **WHEN** user A requests the candidate list
- **THEN** no candidate of user B is returned

#### Scenario: Analysed candidates first
- **WHEN** the pool holds an eligible, an unanalysed and an ineligible candidate
- **THEN** the list returns the eligible one first, then the unanalysed one, then the ineligible one

### Requirement: Discovery status on the profile page
The profile page SHALL show a project discovery card with the discovery state: finding projects while a job is active, the number of eligible candidate projects and when discovery last completed, or a readable message when the last job failed. It SHALL update without a page reload while a job is active. It SHALL NOT show scores, match percentages or a ranked list.

#### Scenario: Discovery running
- **WHEN** the user's discovery job is RUNNING
- **THEN** the card says that projects are being found, and it changes to the completed state when the job completes, without a reload

#### Scenario: Discovery completed
- **WHEN** the user's last discovery completed with 95 eligible candidates
- **THEN** the card shows 95 candidate projects and when discovery last completed
