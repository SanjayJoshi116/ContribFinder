# developer-profile Specification

## Purpose

Builds and serves the user's structured, evidence-backed developer profile (summary, skills, interests, languages and internal matching signals) from stored GitHub data. It also presents that profile in the UI without claiming to measure expertise.

## Requirements

### Requirement: Structured developer profile
Each user with a completed analysis SHALL have exactly one developer profile. It SHALL contain:
- a summary;
- skills with confidence and evidence;
- interests with evidence;
- a language breakdown;
- an experience level;
- a preferred project size and a preferred issue difficulty;
- the time of the analysis.

Raw GitHub data (including the raw README) SHALL remain stored separately from the profile, and the profile SHALL contain only conclusions derived from it.

#### Scenario: Profile after first analysis
- **WHEN** a user's first sync completes including analysis
- **THEN** the user has one developer profile with an analysis time, and their raw profile README is unchanged

#### Scenario: Re-analysis replaces conclusions
- **WHEN** the profile is analyzed again after a repository gained the topic `kubernetes`
- **THEN** the user still has one profile, its skills include Kubernetes, and no skill or interest from the previous analysis remains unless the current data still supports it

### Requirement: Summary from computed signals
The profile summary SHALL be generated from templates filled only with computed signals: top languages, highest-confidence skills and top interests. It SHALL NOT contain claims that no signal supports. When there are not enough signals, the summary SHALL say that too little public activity was found.

#### Scenario: Summary content
- **WHEN** the top languages are Python and TypeScript, the top frameworks Django and React, and the top interest developer tooling
- **THEN** the summary mentions those and nothing else about the developer's skills

#### Scenario: Sparse account
- **WHEN** the user has no owned non-fork repositories, no README and no contributions
- **THEN** the summary states that little public activity was found, and the profile has no skills

### Requirement: Language breakdown
The profile SHALL include the user's languages aggregated across their owned non-fork repositories. Each language SHALL have total bytes, a share of all bytes and the number of repositories using it, ordered by bytes.

#### Scenario: Aggregation
- **WHEN** repository A has Python 7000 and TypeScript 3000 bytes and repository B has Python 1000 bytes
- **THEN** the breakdown is Python 8000 bytes (share 0.73, 2 repositories) followed by TypeScript 3000 bytes (share 0.27, 1 repository)

### Requirement: Internal experience level
The system SHALL estimate an experience level of beginner, intermediate or experienced from several observable signals. The signals are account age, active owned non-fork repositories, merged external pull requests, distinct repositories contributed to and the number of well-evidenced skills. The thresholds are configurable. When fewer than two signals have data, the level SHALL be `unknown`; repository count alone SHALL never decide the level. The experience level is an internal matching signal and SHALL NOT be shown in the UI or returned by the profile API.

#### Scenario: Multiple signals
- **WHEN** an account is 6 years old, has 15 active repositories, 25 merged external pull requests to 6 repositories and 10 well-evidenced skills
- **THEN** the experience level is experienced

#### Scenario: Insufficient signals
- **WHEN** an account is 2 weeks old and has no repositories or contributions
- **THEN** the experience level is unknown

#### Scenario: Not exposed
- **WHEN** the user requests their profile
- **THEN** the response contains no experience level

### Requirement: Preferences default
The preferred project size SHALL default to `any` and the preferred issue difficulty SHALL default to `unknown` until the user can set them. Analysis SHALL NOT overwrite values that differ from those defaults.

#### Scenario: Defaults
- **WHEN** a profile is created by the first analysis
- **THEN** its preferred project size is `any` and its preferred issue difficulty is `unknown`

### Requirement: Analysis runs from stored data
Profile analysis SHALL read only data stored in ContribFinder and SHALL make no GitHub requests. It SHALL run as the final step of every sync and SHALL also be available as a standalone background job for all users or one user, which operators start when weights or the catalog change. Analysis SHALL be idempotent: the same stored data and configuration SHALL produce the same profile. If analysis fails, the previous profile SHALL remain unchanged and the failure SHALL be recorded on the job.

#### Scenario: No GitHub calls
- **WHEN** a standalone analysis job runs for a user
- **THEN** no GitHub request is made and the profile's analysis time is updated

#### Scenario: Failure keeps previous profile
- **WHEN** analysis fails part-way through
- **THEN** the previous skills, interests and summary are unchanged and the job records the failure with error code `analysis_failed`

#### Scenario: Refresh re-analyzes
- **WHEN** the user presses Refresh and the sync completes
- **THEN** the profile's analysis time is later than before and reflects the newly synced data

### Requirement: Profile API
The system SHALL provide the requesting user's profile, skills and interests from stored data only:
- `GET /api/v1/profile` returns the summary, language breakdown, preferences and analysis time. A user without an analyzed profile gets HTTP 404 with error code `not_analyzed`.
- `GET /api/v1/profile/skills` returns a paginated list ordered by confidence. Each skill has its name, category, confidence, evidence summary (counts per source, distinct supporting repositories, last observed date) and evidence records (source, supporting repository name and URL, detail, observed date). It can be filtered by category.
- `GET /api/v1/profile/interests` returns a paginated list ordered by strength, each interest with its evidence records.

These endpoints SHALL expose only the requesting user's data.

#### Scenario: Skills with evidence
- **WHEN** a signed-in user with an analyzed profile requests `GET /api/v1/profile/skills?category=framework`
- **THEN** only framework skills are returned, each with its evidence summary and evidence records

#### Scenario: Not analyzed
- **WHEN** a user whose profile has never been analyzed requests `GET /api/v1/profile`
- **THEN** the response is HTTP 404 with error code `not_analyzed`

#### Scenario: Isolation
- **WHEN** user A requests their skills
- **THEN** no skill or evidence of user B is returned

### Requirement: Profile page
The signed-in profile page SHALL show:
- the summary;
- skills grouped by category, each with a bar whose label describes its evidence (for example "8 repositories · dependencies · README") rather than a percentage or an expertise claim;
- each skill's evidence records on demand, with links to supporting repositories;
- interests with their evidence;
- a languages chart;
- the repository list, the last-synced time and Refresh.

The page SHALL NOT display numeric confidence values or the experience level.

#### Scenario: Evidence label
- **WHEN** Python has evidence from 8 repositories including dependency and README evidence
- **THEN** its bar is labeled with those evidence facts and no percentage is shown

#### Scenario: Evidence detail
- **WHEN** the user expands the Django skill
- **THEN** the page lists each evidence record with its source and a link to the supporting repository

#### Scenario: Profile not yet analyzed
- **WHEN** the user has synced data but no analyzed profile
- **THEN** the page shows the synced repositories and a message that the profile is being prepared, instead of an error
