## MODIFIED Requirements

### Requirement: Issue reasons
Every relevant issue SHALL have reasons generated only from the signals that scored it: the matched technologies, the difficulty and how it fits, and the approachability labels. A signal with value 0 SHALL produce no reason. An issue of `unknown` difficulty whose difficulty fit is above 0 SHALL have a reason saying its difficulty was not estimated. Reason texts SHALL use words, never percentages, and SHALL describe difficulty as an estimate.

#### Scenario: Reasons
- **WHEN** an issue matched Django, is estimated beginner for a beginner developer, and is labeled `good first issue`
- **THEN** its reasons name Django, the estimated beginner difficulty, and the `good first issue` label

#### Scenario: Unknown difficulty
- **WHEN** a relevant issue's difficulty is `unknown` and the configured neutral difficulty fit for the developer's level is above 0
- **THEN** its reasons include one saying the difficulty was not estimated, and no reason names a difficulty level
