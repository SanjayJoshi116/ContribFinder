## MODIFIED Requirements

### Requirement: Search queries from the developer profile
The system SHALL generate GitHub repository search queries from the developer's stored profile, using these strategies:
- **language search**: the developer's top language skills;
- **skill search**: their top non-language skills that have a GitHub topic (frameworks, libraries, databases, tools);
- **interest search**: their detected interests, through each interest's topics;
- **topic search**: the topics that recur across their own non-fork repositories and are not already covered by a skill or interest query that is planned within the budget. A skill or interest query the budget leaves out SHALL NOT keep its topic out of topic search.

Skills whose only evidence is a README mention SHALL NOT generate queries. Each query SHALL be run once per configured star band, so that every query returns both smaller and established projects; the lowest band's lower bound is the minimum number of stars. When the bands are not configured, they SHALL derive from the minimum number of stars: from the minimum to 999 and 1000 or more (default 20 to 999 and 1000 or more), or a single open-ended band from the minimum when the minimum is 1000 or more, so that changing only the minimum never stops the application. The number of search requests per run (one query in one band) SHALL NOT exceed a configured budget (default 20), split across strategies by configured shares. When the shares do not divide the budget exactly, each strategy SHALL first get the whole part of its share, and the slots left over SHALL go one each to the strategies with the largest fractional parts, ties broken in strategy order (language, skill, interest, topic). A query SHALL be planned in all bands or not at all, and budget a strategy cannot use SHALL pass to the next strategy. A budget that is not a multiple of the number of bands SHALL produce a configuration warning naming the requests it leaves unused. Every request SHALL restrict results to public, non-archived, non-fork repositories that were pushed within the configured window (default 180 days), have a star count inside its band, and are not owned by the developer. Bands SHALL be ascending and non-overlapping; an invalid band configuration SHALL stop the application at startup. The same profile and configuration SHALL produce the same requests in the same order. Generation SHALL NOT call GitHub.

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

#### Scenario: Skill query cut by the budget
- **WHEN** the skill strategy has room for 3 queries, the developer's sixth qualifying skill searches the topic `fastapi`, and `fastapi` is a topic of 3 of their own repositories
- **THEN** the skill query for `fastapi` is not planned, and the topic search for `fastapi` is planned if the topic strategy has room

#### Scenario: Leftover slots by largest remainder
- **WHEN** 5 queries are split by the shares language 1, skill 1, interest 1, topic 9, and every strategy has enough queries
- **THEN** topic gets 4 queries and one of language, skill and interest gets 1 (language, by strategy order)

#### Scenario: Default split unchanged
- **WHEN** the budget is 20, there are two bands and the shares are the defaults (language 2, skill 4, interest 3, topic 1)
- **THEN** language gets 2 queries, skill 4, interest 3 and topic 1, as before

### Requirement: Discovery provenance
For every candidate the system SHALL record each way it was discovered: the source (`language_search`, `topic_search`, `skill_search`, `interest_search`, `similar_repo` or `previously_interacted`), the query text for search sources, the result's rank within that query, and when that source first and last found it. The recorded query text SHALL NOT include the star band or the other request qualifiers: a query run in several bands is one query. A repository found by several sources or queries SHALL be one candidate with several discovery records. The candidate SHALL record when it was first discovered and when a discovery run last found it. Once a run has searched and collected interactions, discovery records of the developer that this run did not find again SHALL be removed, so a rank from a query that no longer finds the repository never orders the pool; the candidate itself stays until its retention period ends. A run that made no search (no query qualified) SHALL remove no records, and the records of a query GitHub rejected in this run SHALL be kept. When one query finds a repository in two bands in the same run, its record SHALL keep the better rank, also when the run was retried between the two requests: a record counts as found by this run when it was last found at or after the run's search started.

#### Scenario: Found by two strategies
- **WHEN** `encode/httpx` is returned by the Python language search at rank 4 and by the developer-tooling interest search at rank 12
- **THEN** the developer has one candidate for `encode/httpx` with two discovery records, holding those sources, queries and ranks

#### Scenario: Rediscovered later
- **WHEN** a later run finds an existing candidate again through the same query
- **THEN** the candidate's last-found time is updated, and no duplicate candidate or discovery record is created

#### Scenario: Repository crosses a band
- **WHEN** a repository was found at rank 1 by the Python language search in the 20–999 band, and a later run finds it at rank 28 by the same search in the 1000+ band
- **THEN** the candidate has one discovery record for that search, with rank 28, and its query text has no star qualifier

#### Scenario: Better rank kept across a retry
- **WHEN** a run finds a repository at rank 2 by the Django skill search in the 20–999 band, is retried after a rate limit, and its next attempt finds the repository at rank 25 by the same search in the 1000+ band
- **THEN** the discovery record for that search keeps rank 2

#### Scenario: Rejected query keeps its records
- **WHEN** a candidate was found at rank 3 by the Python language search, and in the next run GitHub rejects that query as invalid
- **THEN** the candidate keeps that record and rank

#### Scenario: Query no longer finds the repository
- **WHEN** a candidate was found at rank 1 by an interest search, and the next run's interest search no longer returns it while a language search finds it at rank 20
- **THEN** after that run the candidate has only the language search record, ranked 20

### Requirement: Discovery yield report
A management command SHALL report how discovery's search requests were spent, from the query yield recorded on finished discovery jobs (completed, failed or cancelled), without changing any stored data. It SHALL accept a time window in days (by job start, or by job creation for a job that never started; default all time) and a JSON output file. Per strategy, per star band, and per strategy and band together, it SHALL give: the number of requests, the number refused by GitHub, the results returned, the rejections per reason, the candidates recorded, the results per request, and the share of results recorded. It SHALL give the same figures for all requests together, and the number of runs. It SHALL count on their own lines the runs that made no search request (no query planned, or ended before searching) and the runs that searched but recorded no query yield (from before the yield was recorded); neither enters any figure. The report SHALL contain aggregates only: no user, job, repository or query-text identifiers. It SHALL NOT change any ranking, query plan or budget.

#### Scenario: Rejections per strategy
- **WHEN** finished runs recorded 10 language requests with 300 results, 90 rejected as `no_license` and 150 recorded, and 10 interest requests with 200 results, 20 rejected as `no_license` and 170 recorded
- **THEN** the report shows `no_license` 90 for language and 20 for interest, and a recorded share of 0.50 for language and 0.85 for interest

#### Scenario: Yield per band
- **WHEN** runs recorded requests in the `20..999` and `1000+` bands
- **THEN** the report gives the results per request and the recorded share for each band

#### Scenario: Runs from before the yield was recorded
- **WHEN** some finished discovery runs planned queries but have no recorded query yield
- **THEN** they are counted as runs without yield and enter no figure

#### Scenario: Runs without a search
- **WHEN** a discovery run was cancelled before it started, and another planned no query
- **THEN** both are counted as runs without a search, not as runs without yield, and enter no figure

#### Scenario: Window includes never-started runs
- **WHEN** a discovery job created 2 days ago was cancelled before it started, and the report covers the last 7 days
- **THEN** the job is counted, as it is in the all-time report

#### Scenario: Aggregates only
- **WHEN** the report is written as JSON
- **THEN** it contains no user, job or repository identifier and no query text, and no stored row changes
