## MODIFIED Requirements

### Requirement: Repository data collection
For each candidate repository the system SHALL collect and store:
- metadata: owner, name, description, URL, default branch, stars, forks, open issues, primary language, license, creation, update and push dates, archived and fork flags;
- languages (bytes) and topics;
- the README;
- whether it has CONTRIBUTING documentation, a code of conduct, issue templates and a pull request template;
- whether it has a `good first issue` and a `help wanted` label;
- root dependency manifests, parsed into dependency names the same way as for the developer's own repositories;
- activity signals (see `repository-activity`);
- its open issues (see `issue-ingestion`).

Repository data SHALL be stored once and shared by every developer whose pool contains the repository. A repository whose data is still fresh SHALL NOT be fetched again for another developer's discovery.

#### Scenario: Candidate analyzed
- **WHEN** a newly discovered candidate is analyzed
- **THEN** its metadata, languages, topics, README, community files, labels, dependencies, activity snapshot and open issues are stored

#### Scenario: Shared analysis
- **WHEN** two developers' discovery runs both find `encode/httpx` and its data is fresh after the first run
- **THEN** the second run makes no request for `encode/httpx` beyond its search result

#### Scenario: Missing optional files
- **WHEN** a repository has no README, no CONTRIBUTING file, no labels and no open issues
- **THEN** it is analyzed successfully and records that each of these is absent

### Requirement: Per-data-type freshness
The system SHALL record, per repository, when its metadata, README, community files and labels, dependencies, activity signals and issues were last fetched. Each data type SHALL become stale after its own configured age (defaults: issues 6 hours, metadata 12 hours, activity 24 hours, community files and labels 7 days, dependencies 7 days, README 7 days). A periodic background task SHALL move RECOMMENDABLE and INDEXED repositories with any stale data type to STALE and record which data types are stale.

#### Scenario: Metadata stale
- **WHEN** a RECOMMENDABLE repository's metadata was fetched 13 hours ago, the metadata age limit is 12 hours, and the README was fetched yesterday
- **THEN** the periodic task marks it STALE with metadata stale and README not stale

#### Scenario: Issues stale
- **WHEN** a RECOMMENDABLE repository's issues were fetched 7 hours ago, the issues age limit is 6 hours, and every other data type is fresh
- **THEN** the periodic task marks it STALE with only issues stale
