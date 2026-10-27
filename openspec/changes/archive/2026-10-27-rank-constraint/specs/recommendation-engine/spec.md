## ADDED Requirements

### Requirement: Stored ranks start at 1
The system SHALL store every recommendation's rank, and every matched issue's rank within its recommendation, as a whole number of at least 1, and the database SHALL refuse a rank of 0. Upgrading SHALL keep every stored recommendation and matched issue: where a developer's recommendations, or a recommendation's matched issues, include a rank of 0, all of that group's ranks SHALL be raised by one, so their order is unchanged.

#### Scenario: Rank 0 refused
- **WHEN** any writer stores a recommendation or a matched issue with rank 0
- **THEN** the database refuses the row and nothing is stored

#### Scenario: Generation writes valid ranks
- **WHEN** a generation stores recommendations with matched issues
- **THEN** every recommendation's rank and every matched issue's rank is at least 1

#### Scenario: Upgrade repairs a rank 0
- **WHEN** the upgrade runs while a developer has recommendations ranked 0, 1 and 2
- **THEN** they are ranked 1, 2 and 3 in the same order, and no recommendation is deleted
