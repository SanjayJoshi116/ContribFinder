## MODIFIED Requirements

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
bucket SHALL have no adjusted share. Per configuration the report SHALL also give one row per
match label (strong, good, partial) with the same counts, distinct users and positive share, not
adjusted for position, and a calibration verdict: `ordered` when the share of every label that
has one is at least the share of every lower label that has one, `not ordered` naming the first
higher label whose share is below a lower label's, or `not enough data` when fewer than two
labels have a share. A group with fewer decisive actions than a minimum
(configurable, default 10) SHALL show its counts but no share and SHALL be left out of the
adjusted share. Events without a configuration version or rank SHALL be counted on their own
line and left out of every share; events without a match label SHALL be left out of the label
rows only. Per configuration it SHALL also count dismissals by reason (including those without one); reasons SHALL NOT change any share. The command SHALL accept a time window in days, the
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

#### Scenario: Labels in order
- **WHEN** under `v2-deterministic` the positive shares are 0.70 for strong, 0.55 for good and 0.40 for partial recommendations
- **THEN** the report shows the three label rows and the calibration verdict `ordered`

#### Scenario: Labels out of order
- **WHEN** the shares are 0.45 for strong and 0.60 for good
- **THEN** the calibration verdict is `not ordered` and names strong below good

#### Scenario: One label with a share
- **WHEN** only strong recommendations reach the minimum number of decisive actions
- **THEN** the calibration verdict is `not enough data`

#### Scenario: Dismiss reasons per configuration
- **WHEN** under `v2-deterministic` users dismissed 6 recommendations as `inactive`, 3 as `not_my_stack` and 4 without a reason
- **THEN** the report shows those counts for `v2-deterministic`, and its shares are the same as if no reason had been given
