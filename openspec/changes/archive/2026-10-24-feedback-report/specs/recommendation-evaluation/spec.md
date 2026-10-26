## ADDED Requirements

### Requirement: Feedback report
A management command SHALL report how users acted on recommendations, per scoring configuration
version, from the stored feedback events and their snapshots, without changing any stored data.
It SHALL group events by configuration version and by rank bucket (1–5, 6–10, 11–20, 21 and
below), and SHALL give per group the count of each action and the number of distinct users.
Saved, opened repository and opened issue SHALL count as positive actions; these and dismissed
SHALL count as decisive actions; viewed, unsaved and undismissed SHALL be counted but be neither.
Per group the report SHALL give the positive share, positive actions divided by decisive
actions. Per configuration it SHALL give the raw positive share over all its groups and a
position-adjusted share: the mean of its bucket shares weighted by the number of decisive
actions per bucket over all configurations in the report, using only the buckets where the
configuration has a share and renormalizing the weights over them; a configuration with no such
bucket SHALL have no adjusted share. A group with fewer decisive actions than a minimum
(configurable, default 10) SHALL show its counts but no share and SHALL be left out of the
adjusted share. Events without a configuration version or rank SHALL be counted on their own
line and left out of every share. The command SHALL accept a time window in days, the
configuration versions to include and a JSON output file. The report SHALL contain aggregates
only: no user, repository, recommendation or issue identifiers. It SHALL NOT change any ranking.

#### Scenario: Shares per configuration and bucket
- **WHEN** under `v2-deterministic` users saved 12 and dismissed 8 recommendations ranked 1 to 5
- **THEN** the report shows for `v2-deterministic`, ranks 1–5: 12 saved, 8 dismissed, the number of users, and a positive share of 0.60

#### Scenario: Position adjustment
- **WHEN** configuration A has 32 positive of 40 decisive actions at ranks 1–5 and 4 of 10 at ranks 6–10, and configuration B has 8 of 10 at ranks 1–5 and 16 of 40 at ranks 6–10
- **THEN** A's raw positive share is 0.72 and B's 0.48, and both have a position-adjusted share of 0.60

#### Scenario: Too few actions
- **WHEN** a group has 4 decisive actions and the minimum is 10
- **THEN** it shows its counts, no share, and does not enter the adjusted share

#### Scenario: Events without a recommendation snapshot
- **WHEN** some events have no configuration version or rank
- **THEN** they are counted on a separate line and enter no share

#### Scenario: Aggregates only
- **WHEN** the report is written as JSON
- **THEN** it contains no user, repository, recommendation or issue identifier, and no stored row changes
