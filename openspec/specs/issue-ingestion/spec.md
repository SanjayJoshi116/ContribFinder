# issue-ingestion Specification

## Purpose

Fetches and keeps an up-to-date local copy of the open issues of repositories in developers' candidate pools, so issue analysis and matching run from stored data and never wait on GitHub.
## Requirements
### Requirement: Issue collection
For each repository in at least one developer's pool, the system SHALL fetch its open issues from GitHub, most recently updated first, up to a configured number of pages (default 1 page of 100). When that listing reached its page cap, the system SHALL in addition fetch, for each configured entry label (default `good first issue` and `help wanted`; an empty list fetches none), one page of open issues carrying that label, most recently updated first; a listing that did not reach its cap already holds every open issue. The stored issues SHALL be the union of these listings, each issue once. Pull requests returned by GitHub's issue listing SHALL be ignored. For each issue it SHALL store: GitHub ID, number, title, body (plain text without HTML comments, such as the hints an issue template leaves, capped at a configured length, default 10,000 characters, after the comments are removed; the long-description threshold of `issue-analysis` SHALL be lower than that length), raw label names as GitHub sent them, state, whether it is locked, whether it has an assignee, comment count, URL, and GitHub's creation and update times. Issues SHALL be stored once per repository and shared by every developer whose pool contains it. The fetch SHALL be recorded as truncated when the most-recent listing reached its page cap; the labeled listings SHALL NOT change that record. Fetching SHALL use the same GitHub client rules as other repository data: conditional requests, caching, timeouts, retries with backoff and rate-limit handling. A failure of any of these listings SHALL be a failure of the issue fetch.

#### Scenario: Issues stored
- **WHEN** a pooled repository with 30 open issues and 5 open pull requests is analyzed
- **THEN** 30 issues are stored with their labels, and no pull request is stored as an issue

#### Scenario: Long template comments before the report
- **WHEN** an issue's body starts with 12,000 characters of HTML comments from its template, followed by a three-line report, and the cap is 10,000 characters
- **THEN** the stored body is the three-line report

#### Scenario: Cap reached
- **WHEN** a repository has 450 open issues, none with an entry label, and the cap is one page of 100
- **THEN** the 100 most recently updated open issues are stored and the fetch is recorded as truncated

#### Scenario: Older entry issue beyond the cap
- **WHEN** a repository has 450 open issues and one labeled `good first issue` was last updated before the 100 most recent
- **THEN** that issue is stored together with the 100 most recent ones, and the fetch is recorded as truncated

#### Scenario: Issue in several listings
- **WHEN** the recent listing reached its cap and a recently updated issue carries both `good first issue` and `help wanted`
- **THEN** it is stored once

#### Scenario: Small repository
- **WHEN** a repository has 30 open issues, some labeled `good first issue`
- **THEN** only the most recently updated issues are fetched (one request), and all 30 are stored

#### Scenario: Entry labels turned off
- **WHEN** the configured entry labels are an empty list
- **THEN** only the most recently updated issues are fetched, as before

#### Scenario: Labeled listing fails
- **WHEN** the most-recent listing reaches its cap and the `help wanted` listing fails with a server error after retries
- **THEN** the issue fetch fails and the previously stored issues remain

#### Scenario: No issues
- **WHEN** a repository has issues disabled or no open issues
- **THEN** analysis succeeds and the repository has no stored issues

### Requirement: Issue set replaced on refresh
Each successful issue fetch SHALL replace the repository's stored issues with the fetched set: issues that are closed or no longer returned SHALL be removed, and issues still returned SHALL keep their identity with updated fields. A failed fetch SHALL keep the previously stored issues and SHALL be recorded as an analysis failure, never treated as "no issues".

#### Scenario: Issue closed
- **WHEN** an issue stored yesterday is closed on GitHub and the repository's issues are refreshed
- **THEN** the issue is no longer stored

#### Scenario: Fetch fails
- **WHEN** the issue fetch fails with a server error after retries are exhausted
- **THEN** the previously stored issues remain and the failure is recorded

### Requirement: Issue freshness
Issues SHALL be a separate repository data type with their own last-fetched time and a configured staleness age (default 6 hours), shorter than other repository data. A periodic refresh SHALL fetch only issues when issues are the only stale data type. Issue data SHALL be removed together with its repository.

#### Scenario: Issues only
- **WHEN** a RECOMMENDABLE repository's issues were fetched 7 hours ago and all other data is fresh
- **THEN** the background refresh fetches its issues and nothing else

#### Scenario: Repository removed
- **WHEN** a repository no developer references any more is deleted
- **THEN** its issues are deleted with it

