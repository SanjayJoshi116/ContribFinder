# recommendation-explanations Specification

## Purpose

Explains every recommendation with machine-readable reasons built only from the scoring evidence that produced it, and classifies each match with a label instead of a numeric score or percentage.

## Requirements

### Requirement: Reasons from scoring evidence
Every recommendation SHALL have machine-readable reasons, each with a type, a human-readable text, its contribution to the score, and structured detail naming the evidence (for example the matched skills, languages with their code share, interests, activity label, openness affordances, relevant issue counts by contribution type, or issue difficulties). Reason types SHALL be `skill`, `language`, `framework`, `interest`, `activity`, `openness`, `issue_availability` and `difficulty`. A reason SHALL be created only for a signal that contributes to the score (its value is above 0 and the configuration weights it above 0), and its text and detail SHALL mention only evidence that signal actually used. Difficulty reasons SHALL describe difficulty as an estimate. An `issue_availability` reason SHALL say how its issues matched: through technologies the developer uses, only through `good first issue` or `help wanted` labels, or both, giving the number that mention the developer's technologies; it SHALL NOT claim a match with the developer's technologies for an issue that matched only by label. Reasons SHALL be ordered by their contribution to the score, highest first. Reasons SHALL be regenerated with their recommendation and SHALL NOT outlive it.

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

#### Scenario: Signal weighted 0
- **WHEN** a configuration weights interest 0 and a recommendation's interest signal is above 0
- **THEN** it has no `interest` reason

#### Scenario: Issues matched only by label
- **WHEN** a recommendation's two relevant issues mention none of the developer's technologies and are labeled `good first issue`
- **THEN** its `issue_availability` reason says two open issues are labeled `good first issue` or `help wanted` and does not say they match the developer's technologies

#### Scenario: Mixed issue matches
- **WHEN** a recommendation has three relevant issues, one mentioning a technology the developer uses and two matched only by label
- **THEN** its `issue_availability` reason gives three relevant issues, one of them mentioning the developer's technologies

### Requirement: Match labels
Each recommendation SHALL carry a match label derived from its score and the active configuration's bands: `strong`, `good` or `partial`. With `v1-deterministic` the bands SHALL be: strong at 0.55 or more, good at 0.35 or more, partial below that. The label, not the score, SHALL be what users see. The system SHALL NOT present any score as a percentage, a probability of success, or a measure of expertise.

#### Scenario: Band boundaries
- **WHEN** recommendations score 0.60, 0.40 and 0.20 under `v1-deterministic`
- **THEN** their labels are strong, good and partial

#### Scenario: No percentages
- **WHEN** a user views any recommendation
- **THEN** no percentage or numeric match score is shown
