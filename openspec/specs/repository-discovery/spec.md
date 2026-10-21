# repository-discovery Specification

## Purpose

Builds each developer's pool of candidate open-source repositories from their evidence-backed profile, records why every repository entered the pool, and removes clearly unsuitable repositories before any ranking happens.

## Requirements

### Requirement: Search queries from the developer profile
The system SHALL generate GitHub repository search queries from the developer's stored profile, using these strategies:
- **language search**: the developer's top language skills;
- **skill search**: their top non-language skills that have a GitHub topic (frameworks, libraries, databases, tools);
- **interest search**: their detected interests, through each interest's topics;
- **topic search**: the topics that recur across their own non-fork repositories and are not already covered by a skill or interest query.

Skills whose only evidence is a README mention SHALL NOT generate queries. Each query SHALL be run once per configured star band, so that every query returns both smaller and established projects; the lowest band's lower bound is the minimum number of stars. When the bands are not configured, they SHALL derive from the minimum number of stars: from the minimum to 999 and 1000 or more (default 20 to 999 and 1000 or more), or a single open-ended band from the minimum when the minimum is 1000 or more, so that changing only the minimum never stops the application. The number of search requests per run (one query in one band) SHALL NOT exceed a configured budget (default 20), split across strategies by configured shares; a query SHALL be planned in all bands or not at all, and budget a strategy cannot use SHALL pass to the next strategy. A budget that is not a multiple of the number of bands SHALL produce a configuration warning naming the requests it leaves unused. Every request SHALL restrict results to public, non-archived, non-fork repositories that were pushed within the configured window (default 180 days), have a star count inside its band, and are not owned by the developer. Bands SHALL be ascending and non-overlapping; an invalid band configuration SHALL stop the application at startup. The same profile and configuration SHALL produce the same requests in the same order. Generation SHALL NOT call GitHub.

#### Scenario: Queries from skills and interests
- **WHEN** the developer's top skills are Python and Django (with dependency evidence) and their top interest is developer tooling
- **THEN** the queries include a Python language search, a Django skill search and a developer-tooling interest search, each run in every star band and restricted to public, non-archived, non-fork, recently pushed repositories inside the band that the developer does not own

#### Scenario: Every query in every band
- **WHEN** the bands are 20–999 and 1000+ and the plan holds a Python language search
- **THEN** it is requested twice, once restricted to 20–999 stars and once to 1000 or more

#### Scenario: README-only skill ignored
- **WHEN** the developer's only evidence for Rust is a README mention
- **THEN** no query is generated for Rust

#### Scenario: Budget respected
- **WHEN** the profile could produce 25 queries, there are two bands and the budget is 20
- **THEN** exactly 10 queries are planned, each in both bands (20 requests), allocated by the configured strategy shares

#### Scenario: Sparse profile
- **WHEN** the developer has no skills or interests that qualify for a query
- **THEN** no search is made, the discovery job completes, and the pool contains only previously interacted repositories, if any

#### Scenario: Only the minimum stars changed
- **WHEN** the minimum number of stars is set to 50 and the bands are not configured
- **THEN** the application starts, and the bands are 50–999 and 1000 or more

#### Scenario: Budget not a multiple of the bands
- **WHEN** the budget is 25 and there are 3 bands
- **THEN** the application starts with a configuration warning that 1 request of the budget is unused

### Requirement: Candidate search
The system SHALL run the generated queries against GitHub repository search with the developer's own token. It SHALL keep at most the configured number of results per query (default 30), and store the metadata of each result as a shared repository. It SHALL NOT index repositories that no query or interaction produced. A query that GitHub rejects as invalid SHALL be skipped and recorded, without failing the run. Rate limits and transient failures SHALL be handled as for sync requests, and a retried run SHALL NOT repeat queries it already completed.

Storing a search result SHALL update the stored repository's metadata fields and topics but SHALL NOT count as a metadata fetch: the time its metadata was last fetched, which decides when languages and metadata are refreshed, SHALL be set only by an analysis or by the developer's own profile sync. Storing a search result SHALL NOT delete any stored repository: when another stored repository holds the result's name under a different GitHub ID, that repository SHALL keep its data and links and SHALL be resolved by its next analysis (see `repository-analysis`). Concurrent discovery runs storing overlapping results SHALL NOT fail on a database deadlock.

#### Scenario: Results stored
- **WHEN** a Python language search returns 30 repositories
- **THEN** those 30 repositories (minus pre-filtered ones) are stored with their metadata and topics, and become candidates of the developer

#### Scenario: Invalid query skipped
- **WHEN** GitHub answers one of 10 queries with 422
- **THEN** that query is recorded as skipped in the job metadata, the other 9 run, and the job completes

#### Scenario: Retry resumes
- **WHEN** a run hits a search rate limit after 4 of 10 queries and is retried
- **THEN** the retried run executes only the remaining 6 queries

#### Scenario: Search result is not a metadata fetch
- **WHEN** a repository analyzed 13 hours ago (metadata age limit 12 hours) is returned by a search an hour ago
- **THEN** its stars and push date are the search result's, and its metadata is still stale, so its next refresh fetches metadata and languages

#### Scenario: Name taken by a renamed repository
- **WHEN** a stored repository `org/tool` with GitHub ID 1 was renamed on GitHub, and a search returns a new repository `org/tool` with GitHub ID 2
- **THEN** the new repository is stored as `org/tool`, and the repository with GitHub ID 1 still exists with its candidates, saves and dismissals, ineligible as `name_released` until its next analysis

#### Scenario: Concurrent runs
- **WHEN** two developers' discovery runs store result sets that share 20 repositories at the same time
- **THEN** both runs complete

### Requirement: Previously interacted repositories
Repositories the developer is linked to as a contributor SHALL be added to their pool with the source `previously_interacted`, without a search. The minimum-stars rule SHALL NOT apply to them. Repositories the developer owns SHALL never be candidates.

#### Scenario: Contributed repository added
- **WHEN** the developer has merged pull requests in `pallets/flask`
- **THEN** `pallets/flask` is a candidate with the source `previously_interacted`

#### Scenario: Own repository excluded
- **WHEN** a search result is a repository the developer owns
- **THEN** it is not added to the developer's pool

### Requirement: Discovery provenance
For every candidate the system SHALL record each way it was discovered: the source (`language_search`, `topic_search`, `skill_search`, `interest_search`, `similar_repo` or `previously_interacted`), the query text for search sources, the result's rank within that query, and when that source first and last found it. The recorded query text SHALL NOT include the star band or the other request qualifiers: a query run in several bands is one query. A repository found by several sources or queries SHALL be one candidate with several discovery records. The candidate SHALL record when it was first discovered and when a discovery run last found it. Once a run has searched and collected interactions, discovery records of the developer that this run did not find again SHALL be removed, so a rank from a query that no longer finds the repository never orders the pool; the candidate itself stays until its retention period ends. A run that made no search (no query qualified) SHALL remove no records, and the records of a query GitHub rejected in this run SHALL be kept. When one query finds a repository in two bands in the same run, its record SHALL keep the better rank.

#### Scenario: Found by two strategies
- **WHEN** `encode/httpx` is returned by the Python language search at rank 4 and by the developer-tooling interest search at rank 12
- **THEN** the developer has one candidate for `encode/httpx` with two discovery records, holding those sources, queries and ranks

#### Scenario: Rediscovered later
- **WHEN** a later run finds an existing candidate again through the same query
- **THEN** the candidate's last-found time is updated, and no duplicate candidate or discovery record is created

#### Scenario: Repository crosses a band
- **WHEN** a repository was found at rank 1 by the Python language search in the 20–999 band, and a later run finds it at rank 28 by the same search in the 1000+ band
- **THEN** the candidate has one discovery record for that search, with rank 28, and its query text has no star qualifier

#### Scenario: Rejected query keeps its records
- **WHEN** a candidate was found at rank 3 by the Python language search, and in the next run GitHub rejects that query as invalid
- **THEN** the candidate keeps that record and rank

#### Scenario: Query no longer finds the repository
- **WHEN** a candidate was found at rank 1 by an interest search, and the next run's interest search no longer returns it while a language search finds it at rank 20
- **THEN** after that run the candidate has only the language search record, ranked 20

### Requirement: Candidate pre-filtering
Before a search result becomes a candidate, the system SHALL reject it if it is archived, a fork, not pushed within the configured window, without a detected license, below the minimum stars (except previously interacted repositories), owned by the developer, or not a code project (`not_code`). At this stage `not_code` SHALL mean: without a detected primary language, or a suspected list (see below) whose stored repository a completed analysis already found to be `not_code`. A suspected list is a repository named `awesome` or starting with `awesome-`, or one with a configured list or documentation topic (default including `awesome`, `awesome-list`, `curated-list`, `list`, `lists`, `books`, `interview-questions`). A suspected list not yet decided by an analysis SHALL become a candidate, and its analysis decides (see "Candidate eligibility"). Filtering SHALL be a separate stage from search and ranking. The number of rejections per reason SHALL be recorded on the discovery job. Rejected results SHALL NOT be stored as candidates.

#### Scenario: Archived result rejected
- **WHEN** a search result is archived
- **THEN** it does not become a candidate and the job's rejection count for `archived` increases by one

#### Scenario: Unlicensed result rejected
- **WHEN** a search result has no detected license
- **THEN** it does not become a candidate and the rejection is counted as `no_license`

#### Scenario: No language rejected
- **WHEN** a search result has no detected primary language
- **THEN** it does not become a candidate and the rejection is counted as `not_code`

#### Scenario: Known list rejected
- **WHEN** a search result is named `awesome-python`, and an earlier analysis of the stored repository found it to be `not_code`
- **THEN** it does not become a candidate, is not analyzed again, and the rejection is counted as `not_code`

#### Scenario: Suspected list analyzed
- **WHEN** a search result named `awesome-lint` has a primary language and has never been analyzed
- **THEN** it becomes a candidate, and its analysis decides whether it is a code project

#### Scenario: Library tagged like a list
- **WHEN** a linked-list library with a primary language is tagged `list`
- **THEN** it is not rejected at search, and after analysis it is eligible when its manifest declares dependencies

#### Scenario: Previously interacted list
- **WHEN** the developer has contributed to a repository that an analysis found to be a curated list
- **THEN** it is rejected as `not_code` like any other result

### Requirement: Candidate eligibility
After a candidate repository is analyzed, the system SHALL re-check the same repository-level rules on the fresh data (archived, fork, push window, license, not a code project) and record whether it is eligible, and if not, why. Eligibility SHALL be decided from the repository's current stored data, including metadata stored by searches while the analysis ran. After analysis, a repository is not a code project when it has no detected primary language, or when it is a suspected list without any manifest dependency. An ineligible candidate SHALL stay in the pool with its reason, so it can be inspected, but SHALL NOT be counted as an eligible candidate.

#### Scenario: Archived after discovery
- **WHEN** a candidate found last week is archived by its owner and then refreshed
- **THEN** the candidate is ineligible with the reason `archived`

#### Scenario: List already in the pool
- **WHEN** a candidate discovered before this rule existed is a curated list and is analyzed again
- **THEN** the candidate is ineligible with the reason `not_code`

#### Scenario: Tool named like a list
- **WHEN** `sindresorhus/awesome-lint` is analyzed and its manifest declares dependencies
- **THEN** it is eligible, unless another rule applies

#### Scenario: Suspected list without dependencies
- **WHEN** `vinta/awesome-python` is analyzed and its root manifests declare no dependencies
- **THEN** it is ineligible with the reason `not_code`

#### Scenario: Search update during analysis
- **WHEN** a repository's issues are being refreshed and a search stores that it is now archived before the refresh stores its result
- **THEN** the refresh ends with the repository ineligible with the reason `archived`

### Requirement: Candidate pool maintenance
A candidate that no discovery run has found for the configured retention period (default 30 days) SHALL be removed from the pool. On every discovery run, before the size cap applies:
- a candidate whose stored repository data shows it is not a code project (the `not_code` rule of "Candidate eligibility" for an analyzed repository, of "Candidate pre-filtering" otherwise) SHALL be removed from the pool, and the job SHALL record how many were removed;
- every eligibility rule of "Candidate eligibility" SHALL be re-checked on the stored data of the pool's analyzed repositories, with the current settings and time, without waiting for their next analysis. A repository whose eligibility changes SHALL get the new eligibility and reason, and SHALL be RECOMMENDABLE when eligible and INDEXED when not (a STALE repository keeps STALE and returns to the matching state after its refresh). A repository that an analysis currently holds, a FAILED repository and a repository never analyzed SHALL be left unchanged, and an existing reason SHALL be replaced only by the reason the rules give now.

The pool SHALL NOT exceed the configured size (default 300). When it would, the system SHALL keep the candidates first in the pool order (previously interacted, then best search rank, then most recently found, then repository name) and remove the rest. The cap SHALL apply before the run analyzes anything, so the run analyzes only kept candidates, in the same order. Because search ranks are counted per band, the kept pool SHALL contain candidates from every band that returned results. The discovery job SHALL record the number of pool candidates in each star band, counting a repository in the band whose range holds its current stars, under `below` when it has fewer stars than the lowest band, and under `other` when no band holds it. Deleting the developer profile SHALL delete its candidates and discovery records. Shared repository data SHALL NOT be deleted when a candidate is removed.

#### Scenario: Expired candidate
- **WHEN** a candidate was last found 31 days ago and the retention period is 30 days
- **THEN** the next discovery run removes it from the pool

#### Scenario: Pool cap
- **WHEN** a run would bring the pool to 320 candidates and the cap is 300
- **THEN** the 20 candidates with the worst search rank that are not previously interacted are removed

#### Scenario: Small pool for fast runs
- **WHEN** the cap is 10 and a run finds 220 candidates
- **THEN** the pool keeps the 10 best-ranked candidates, and the run analyzes no other candidate

#### Scenario: List found before the rule
- **WHEN** a pool holds `public-apis/public-apis` (topic `lists`, no manifest dependencies) from a run before the `not_code` rule, and its analysis is still fresh
- **THEN** the next discovery run removes it from the pool, marks the repository ineligible with `not_code`, and records one removal

#### Scenario: Settings change re-checked
- **WHEN** the push window is shortened from 180 to 90 days and a RECOMMENDABLE pool repository was last pushed 120 days ago
- **THEN** the next discovery run makes it INDEXED and ineligible with the reason `inactive`

#### Scenario: Failed repository keeps its reason
- **WHEN** a FAILED repository in the pool has the reason `repository_unavailable` and is also a curated list
- **THEN** the discovery run leaves its state and reason unchanged

#### Scenario: Repository under analysis left alone
- **WHEN** a pool repository is REFRESHING for another developer's discovery when the pool step runs
- **THEN** the pool step does not change its eligibility or state, and the refresh decides them

#### Scenario: Mixed sizes kept
- **WHEN** the cap is 40, there are two bands, and every query returns 30 results in each band
- **THEN** the kept pool holds candidates from both bands, and the job metadata records how many are in each

#### Scenario: Band with a gap
- **WHEN** the bands are 20–99 and 200–999 and the pool holds repositories with 150 and 5000 stars
- **THEN** both are counted under `other`, not in a band

### Requirement: Discovery job
Discovery SHALL run as a background job per user, tracked like a sync job: at most one active job per user, a status (PENDING, RUNNING, RETRYING, COMPLETED, FAILED or CANCELLED), attempts, a machine-readable error code on failure, and per-step status for the steps queries, search, interactions, pool and analysis, in that order. A retried job SHALL resume after its completed steps and completed per-item work. The repositories a run analyzes SHALL be chosen once, when its analysis step first starts, capped at the configured number per run (default 60); a resumed analysis step SHALL analyze only the rest of that choice and SHALL keep its recorded total. A discovery job SHALL NOT start for a user without an analyzed developer profile or without a connected GitHub account. HTTP requests SHALL NOT wait for discovery.

#### Scenario: Successful discovery
- **WHEN** a discovery job runs to completion
- **THEN** its status is COMPLETED, every step is done or skipped, and the job metadata records the queries run, results found, rejections per reason and repositories analyzed

#### Scenario: Token rejected
- **WHEN** GitHub answers a discovery search with 401
- **THEN** the job ends as FAILED with error code `github_auth_invalid` and is not retried

#### Scenario: No profile yet
- **WHEN** discovery is requested for a user whose profile has never been analyzed
- **THEN** no discovery job is created

#### Scenario: Resumed analysis keeps its cap
- **WHEN** the cap is 10, 25 pool repositories need analysis, and the job is retried after analyzing 4 of its 10
- **THEN** the retried job analyzes the other 6 of those 10, no more, and its recorded total stays 25

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
The system SHALL provide `GET /api/v1/discovery/candidates`: a paginated list of the requesting user's candidates. Each item SHALL contain the repository's name, owner, description, URL, primary language, stars, topics and license, its processing state, eligibility and reason, its latest activity label, the candidate's discovery records, and when it was first and last found. The list SHALL be filterable by source, eligibility and activity label. It SHALL list eligible candidates first, then candidates awaiting analysis, then ineligible ones; within each group, in the pool order of "Candidate pool maintenance" (previously interacted, best search rank, most recently found, repository name), the order in which discovery keeps and analyzes them. It SHALL NOT imply relevance: the response SHALL contain no score or rank across candidates. It SHALL be served from stored data with a query count that does not grow with the page size.

#### Scenario: Filter by source
- **WHEN** the user requests `GET /api/v1/discovery/candidates?source=previously_interacted`
- **THEN** only candidates with a previously-interacted discovery record are returned

#### Scenario: Another user's candidates are not visible
- **WHEN** user A requests the candidate list
- **THEN** no candidate of user B is returned

#### Scenario: Analysed candidates first
- **WHEN** the pool holds an eligible, an unanalysed and an ineligible candidate
- **THEN** the list returns the eligible one first, then the unanalysed one, then the ineligible one

#### Scenario: Same order as the pool
- **WHEN** two eligible candidates have the same best search rank and one was found more recently
- **THEN** the more recently found one is listed first, as the pool cap would keep it first

### Requirement: Discovery status on the profile page
The profile page SHALL show a project discovery card with the discovery state: finding projects while a job is active, the number of eligible candidate projects and when discovery last completed, or a readable message when the last job failed. It SHALL update without a page reload while a job is active. It SHALL NOT show scores, match percentages or a ranked list.

#### Scenario: Discovery running
- **WHEN** the user's discovery job is RUNNING
- **THEN** the card says that projects are being found, and it changes to the completed state when the job completes, without a reload

#### Scenario: Discovery completed
- **WHEN** the user's last discovery completed with 95 eligible candidates
- **THEN** the card shows 95 candidate projects and when discovery last completed
