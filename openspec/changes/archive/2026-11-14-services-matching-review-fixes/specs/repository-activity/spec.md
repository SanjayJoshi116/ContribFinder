## MODIFIED Requirements

### Requirement: Activity label
Each snapshot SHALL carry exactly one label, computed from configurable thresholds:
- `recently_active`: pushed within 30 days, and at least 10 default-branch commits or at least 5 merged pull requests in the last 90 days;
- `moderately_active`: pushed within 90 days, and at least 1 commit or 1 merged pull request in the last 90 days;
- `low_activity`: otherwise.

An unknown count SHALL never be treated as 0. When the commit and pull request counts are both unknown, the label SHALL be decided from the push date alone and SHALL NOT be `recently_active`. When only one count is unknown, `recently_active` SHALL require the known count to meet its threshold, and `moderately_active` SHALL accept the unknown count as it does when both are unknown. The same signals and thresholds SHALL always give the same label. When recommendations are generated, the label used for scoring, reasons and the activity filter SHALL be computed at that time: from the days since the repository's last known push, measured at generation, and the latest snapshot's counts, under the thresholds configured then. Stored snapshots SHALL keep the label they were captured with. Wherever activity is shown to users, it SHALL be shown as the label and the observable signals behind it (for example, "Recently active · last push 3 days ago"), and SHALL NOT be described as health, quality or a probability of success.

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
