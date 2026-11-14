# repository-activity Specification

## Purpose

Describes how active a candidate repository is through observable, dated signals and a coarse activity label, never as a verdict on whether a repository is "healthy" or "good".
## Requirements
### Requirement: Activity signals
When a repository's activity data is fetched, the system SHALL compute and store:
- days since the last push;
- commits to the default branch in the last 90 days;
- pull requests opened and pull requests merged in the last 90 days;
- the contributor count;
- the date of the latest release;
- open issues;
- stars and forks at that time.

A signal GitHub cannot provide (for example, a contributor count for a very large repository) SHALL be stored as unknown, not as zero. The pull request counts SHALL come from a bounded sample of recently updated pull requests, and the snapshot SHALL record when that bound was reached.

#### Scenario: Signals computed
- **WHEN** a repository pushed 3 days ago has 42 default-branch commits, 12 opened and 9 merged pull requests in the last 90 days, 57 contributors and a release 20 days ago
- **THEN** its snapshot stores those values with the time they were captured

#### Scenario: Contributor count unavailable
- **WHEN** GitHub refuses to list contributors for a repository because it is too large
- **THEN** the contributor count is unknown and the other signals are stored

#### Scenario: Empty repository
- **WHEN** a repository has no commits on its default branch
- **THEN** its commit count is 0 and the analysis succeeds

### Requirement: Activity label
Each snapshot SHALL carry exactly one label, computed from configurable thresholds:
- `recently_active`: pushed within 30 days, and at least 10 default-branch commits or at least 5 merged pull requests in the last 90 days;
- `moderately_active`: pushed within 90 days, and at least 1 commit or 1 merged pull request in the last 90 days;
- `low_activity`: otherwise.

An unknown count SHALL never be treated as 0. When the commit and pull request counts are both unknown, the label SHALL be decided from the push date alone and SHALL NOT be `recently_active`. When only one count is unknown, `recently_active` SHALL require the known count to meet its threshold, and `moderately_active` SHALL accept the unknown count as it does when both are unknown. The same signals and thresholds SHALL always give the same label. When recommendations are generated, the label used for scoring, reasons and the activity filter SHALL be computed at that time: from the days since the repository's last known push, measured at generation, and the latest snapshot's counts, under the thresholds configured then. The saved list and the candidate pool SHALL show the label computed the same way when they are read, and a recommendation's activity facts SHALL give the days since the last push as measured at its generation, so no page contradicts the label it shows. Stored snapshots SHALL keep the label they were captured with. Wherever activity is shown to users, it SHALL be shown as the label and the observable signals behind it (for example, "Recently active · last push 3 days ago"), and SHALL NOT be described as health, quality or a probability of success.

#### Scenario: Recently active
- **WHEN** a repository was pushed 3 days ago and has 42 commits in the last 90 days
- **THEN** its label is `recently_active`

#### Scenario: Low activity
- **WHEN** a repository was last pushed 200 days ago
- **THEN** its label is `low_activity`

#### Scenario: Counts unknown
- **WHEN** a repository was pushed 5 days ago and its commit and pull request counts could not be fetched
- **THEN** its label is `moderately_active`

#### Scenario: Threshold change
- **WHEN** the recently-active commit threshold is changed from 10 to 50 and a repository with 42 commits is refreshed
- **THEN** its new snapshot is labeled `moderately_active`

#### Scenario: One count unknown
- **WHEN** a repository was pushed 5 days ago, its commit count could not be fetched, and it has 0 merged pull requests in the last 90 days
- **THEN** its label is `moderately_active`

#### Scenario: One count unknown, the other high
- **WHEN** a repository was pushed 5 days ago, its commit count could not be fetched, and it has 9 merged pull requests in the last 90 days
- **THEN** its label is `recently_active`

#### Scenario: Snapshot aged since capture
- **WHEN** a repository's latest snapshot was captured 40 days ago, with its last push that day and 42 commits, its activity could not be refreshed since, and recommendations are generated now
- **THEN** the label used for the recommendation is `moderately_active`, and its reason says the last push was 40 days ago

#### Scenario: Threshold change before a refresh
- **WHEN** the recently-active commit threshold is changed from 10 to 50, and recommendations are generated before a repository with 42 commits, pushed 3 days ago, is refreshed
- **THEN** the label used for the recommendation is `moderately_active`, and the stored snapshot still says `recently_active`

### Requirement: Activity history
Snapshots SHALL be kept as a dated history per repository, up to a configured number (default 10), removing the oldest first. The latest snapshot SHALL be the repository's current activity.

#### Scenario: History bounded
- **WHEN** a repository with 10 stored snapshots is refreshed and the limit is 10
- **THEN** it still has 10 snapshots, the newest is the one just captured, and the oldest was removed

