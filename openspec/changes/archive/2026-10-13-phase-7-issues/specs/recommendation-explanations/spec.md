## MODIFIED Requirements

### Requirement: Reasons from scoring evidence
Every recommendation SHALL have machine-readable reasons, each with a type, a human-readable text, its contribution to the score, and structured detail naming the evidence (for example the matched skills, languages with their code share, interests, activity label, openness affordances, relevant issue counts by contribution type, or issue difficulties). Reason types SHALL be `skill`, `language`, `framework`, `interest`, `activity`, `openness`, `issue_availability` and `difficulty`. A reason SHALL be created only for a signal whose value is above 0, and its text and detail SHALL mention only evidence that signal actually used. Difficulty reasons SHALL describe difficulty as an estimate. Reasons SHALL be ordered by their contribution to the score, highest first. Reasons SHALL be regenerated with their recommendation and SHALL NOT outlive it.

#### Scenario: Reasons for a Django project
- **WHEN** a recommendation's framework signal matched Django and its interest signal matched developer tooling
- **THEN** it has a `framework` reason naming Django and an `interest` reason naming developer tooling, each with detail listing that evidence

#### Scenario: No invented reasons
- **WHEN** a recommendation's interest signal is 0
- **THEN** it has no `interest` reason

#### Scenario: Reasons replaced on regeneration
- **WHEN** a recommendation is regenerated and its activity signal drops to 0
- **THEN** its previous `activity` reason is gone

#### Scenario: Issue reasons
- **WHEN** a recommendation has three relevant issues, two estimated beginner, and the developer's experience level is beginner
- **THEN** it has an `issue_availability` reason saying relevant issues are available, with their count, and a `difficulty` reason saying some issues look beginner-level

#### Scenario: No issue reasons without issues
- **WHEN** a recommendation has no relevant issues
- **THEN** it has neither an `issue_availability` nor a `difficulty` reason
