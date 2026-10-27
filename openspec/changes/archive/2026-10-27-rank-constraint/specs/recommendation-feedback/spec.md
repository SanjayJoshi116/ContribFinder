## ADDED Requirements

### Requirement: Feedback rank snapshot
A feedback event's rank snapshot SHALL be empty when the event had no recommendation, and otherwise a whole number of at least 1; the database SHALL refuse a rank of 0. Upgrading SHALL keep every stored event: an event stored with rank 0 SHALL have its rank emptied, which the feedback report already counts as no rank.

#### Scenario: Rank 0 refused
- **WHEN** any writer stores a feedback event with rank 0
- **THEN** the database refuses the row and nothing is stored

#### Scenario: Event without a recommendation
- **WHEN** a feedback event is stored with no recommendation
- **THEN** its rank is empty and the event is stored

#### Scenario: Upgrade empties a rank 0
- **WHEN** the upgrade runs while an event has rank 0
- **THEN** the event stays stored with an empty rank, and the feedback report counts it as unattributed as before
