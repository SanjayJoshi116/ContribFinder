## MODIFIED Requirements

### Requirement: Search queries from the developer profile
The system SHALL generate GitHub repository search queries from the developer's stored profile, using these strategies:
- **language search**: the developer's top language skills;
- **skill search**: their top non-language skills that have a GitHub topic (frameworks, libraries, databases, tools);
- **interest search**: their detected interests, through each interest's topics;
- **topic search**: the topics that recur across their own non-fork repositories and are not already covered by a skill or interest query.

Skills whose only evidence is a README mention SHALL NOT generate queries. Each query SHALL be run once per configured star band (default two bands: 20 to 999 stars, and 1000 or more), so that every query returns both smaller and established projects; the lowest band's lower bound is the minimum number of stars. The number of search requests per run (one query in one band) SHALL NOT exceed a configured budget (default 20), split across strategies by configured shares; a query SHALL be planned in all bands or not at all, and budget a strategy cannot use SHALL pass to the next strategy. Every request SHALL restrict results to public, non-archived, non-fork repositories that were pushed within the configured window (default 180 days), have a star count inside its band, and are not owned by the developer. Bands SHALL be ascending and non-overlapping; an invalid band configuration SHALL stop the application at startup. The same profile and configuration SHALL produce the same requests in the same order. Generation SHALL NOT call GitHub.

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

### Requirement: Candidate pre-filtering
Before a search result becomes a candidate, the system SHALL reject it if it is archived, a fork, not pushed within the configured window, without a detected license, below the minimum stars (except previously interacted repositories), owned by the developer, or not a code project (`not_code`): a repository named `awesome` or starting with `awesome-`, a repository with one of the configured list or documentation topics (default including `awesome`, `awesome-list`, `curated-list`, `books`, `interview-questions`), or a repository without a detected primary language. Filtering SHALL be a separate stage from search and ranking. The number of rejections per reason SHALL be recorded on the discovery job. Rejected results SHALL NOT be stored as candidates.

#### Scenario: Archived result rejected
- **WHEN** a search result is archived
- **THEN** it does not become a candidate and the job's rejection count for `archived` increases by one

#### Scenario: Unlicensed result rejected
- **WHEN** a search result has no detected license
- **THEN** it does not become a candidate and the rejection is counted as `no_license`

#### Scenario: Curated list rejected
- **WHEN** a search result is named `awesome-python`, or has the topic `awesome-list`, or has no detected primary language
- **THEN** it does not become a candidate and the rejection is counted as `not_code`

#### Scenario: Previously interacted list
- **WHEN** the developer has contributed to a repository that is a curated list
- **THEN** it is rejected as `not_code` like any other result

### Requirement: Candidate eligibility
After a candidate repository is analyzed, the system SHALL re-check the same repository-level rules on the fresh data (archived, fork, push window, license, not a code project) and record whether it is eligible, and if not, why. An ineligible candidate SHALL stay in the pool with its reason, so it can be inspected, but SHALL NOT be counted as an eligible candidate.

#### Scenario: Archived after discovery
- **WHEN** a candidate found last week is archived by its owner and then refreshed
- **THEN** the candidate is ineligible with the reason `archived`

#### Scenario: List already in the pool
- **WHEN** a candidate discovered before this rule existed is a curated list and is analyzed again
- **THEN** the candidate is ineligible with the reason `not_code`

### Requirement: Candidate pool maintenance
A candidate that no discovery run has found for the configured retention period (default 30 days) SHALL be removed from the pool. On every discovery run, a candidate whose stored repository data shows it is not a code project (the `not_code` rule of "Candidate pre-filtering") SHALL be removed from the pool before the size cap applies, and the repository SHALL be marked ineligible with the reason `not_code`, without waiting for its next analysis; the job SHALL record how many were removed. The pool SHALL NOT exceed the configured size (default 300). When it would, the system SHALL keep the candidates first in analysis order (previously interacted, then best search rank, then most recently found) and remove the rest, so the pool that remains is the one that is analyzed. Because search ranks are counted per band, the kept pool SHALL contain candidates from every band that returned results. The discovery job SHALL record the number of pool candidates in each star band. Deleting the developer profile SHALL delete its candidates and discovery records. Shared repository data SHALL NOT be deleted when a candidate is removed.

#### Scenario: Expired candidate
- **WHEN** a candidate was last found 31 days ago and the retention period is 30 days
- **THEN** the next discovery run removes it from the pool

#### Scenario: Pool cap
- **WHEN** a run would bring the pool to 320 candidates and the cap is 300
- **THEN** the 20 candidates with the worst search rank that are not previously interacted are removed

#### Scenario: Small pool for fast runs
- **WHEN** the cap is 10 and a run finds 220 candidates
- **THEN** the pool keeps the 10 best-ranked candidates, which are the ones the run analyzed

#### Scenario: List found before the rule
- **WHEN** a pool holds `public-apis/public-apis` (topic `lists`) from a run before the `not_code` rule, and its analysis is still fresh
- **THEN** the next discovery run removes it from the pool, marks the repository ineligible with `not_code`, and records one removal

#### Scenario: Mixed sizes kept
- **WHEN** the cap is 40, there are two bands, and every query returns 30 results in each band
- **THEN** the kept pool holds candidates from both bands, and the job metadata records how many are in each
