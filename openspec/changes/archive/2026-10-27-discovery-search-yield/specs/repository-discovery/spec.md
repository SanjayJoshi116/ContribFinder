## MODIFIED Requirements

### Requirement: Candidate search
The system SHALL run the generated queries against GitHub repository search with the developer's own token. It SHALL keep at most the configured number of results per query (default 30), and store the metadata of each result as a shared repository. It SHALL NOT index repositories that no query or interaction produced. A query that GitHub rejects as invalid SHALL be skipped and recorded, without failing the run. Rate limits and transient failures SHALL be handled as for sync requests, and a retried run SHALL NOT repeat queries it already completed. Each query SHALL run in one configured star band; with more than one band, the band SHALL be part of the query. For every query it runs or GitHub refuses, a run SHALL record on its job the query's strategy and star band, the results returned, the rejections per reason (pre-filtering, and `not_code` found when storing) and the number of candidates recorded, or that GitHub refused it; the run's totals SHALL stay recorded as before. The recorded query yield SHALL NOT contain the query text.

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

#### Scenario: Yield per query
- **WHEN** a language query in the `20..999` band returns 30 results, of which 9 are rejected as `no_license` and 1 as `archived`
- **THEN** the job records for that query: strategy `language_search`, band `20..999`, 30 results, rejections `no_license` 9 and `archived` 1, and 20 candidates recorded

#### Scenario: Refused query in the yield
- **WHEN** GitHub answers a skill query in the `1000+` band with 422
- **THEN** the job records that query as refused, with its strategy and band and no results

#### Scenario: One star band
- **WHEN** only one star band is configured
- **THEN** each query's yield has an empty band


## ADDED Requirements

### Requirement: Discovery yield report
A management command SHALL report how discovery's search requests were spent, from the query yield recorded on finished discovery jobs (completed, failed or cancelled), without changing any stored data. It SHALL accept a time window in days (by job start; default all time) and a JSON output file. Per strategy, per star band, and per strategy and band together, it SHALL give: the number of requests, the number refused by GitHub, the results returned, the rejections per reason, the candidates recorded, the results per request, and the share of results recorded. It SHALL give the same figures for all requests together, and the number of runs, and SHALL count runs that recorded no query yield on their own line. The report SHALL contain aggregates only: no user, job, repository or query-text identifiers. It SHALL NOT change any ranking, query plan or budget.

#### Scenario: Rejections per strategy
- **WHEN** finished runs recorded 10 language requests with 300 results, 90 rejected as `no_license` and 150 recorded, and 10 interest requests with 200 results, 20 rejected as `no_license` and 170 recorded
- **THEN** the report shows `no_license` 90 for language and 20 for interest, and a recorded share of 0.50 for language and 0.85 for interest

#### Scenario: Yield per band
- **WHEN** runs recorded requests in the `20..999` and `1000+` bands
- **THEN** the report gives the results per request and the recorded share for each band

#### Scenario: Runs from before the yield was recorded
- **WHEN** some finished discovery runs have no recorded query yield
- **THEN** they are counted as runs without yield and enter no figure

#### Scenario: Aggregates only
- **WHEN** the report is written as JSON
- **THEN** it contains no user, job or repository identifier and no query text, and no stored row changes
