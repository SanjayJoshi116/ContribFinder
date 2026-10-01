# recommendation-explanations Specification

## Purpose

Explains every recommendation with machine-readable reasons built only from the scoring evidence that produced it, and classifies each match with a label instead of a numeric score or percentage.

## Requirements

### Requirement: Reasons from scoring evidence
Every recommendation SHALL have machine-readable reasons, each with a type, a human-readable text, its contribution to the score, and structured detail naming the evidence (for example the matched skills, languages with their code share, interests, activity label or openness affordances). Reason types SHALL be `skill`, `language`, `framework`, `interest`, `activity` and `openness`. A reason SHALL be created only for a signal whose value is above 0, and its text and detail SHALL mention only evidence that signal actually used. Reasons SHALL be ordered by their contribution to the score, highest first. Reasons SHALL be regenerated with their recommendation and SHALL NOT outlive it.

#### Scenario: Reasons for a Django project
- **WHEN** a recommendation's framework signal matched Django and its interest signal matched developer tooling
- **THEN** it has a `framework` reason naming Django and an `interest` reason naming developer tooling, each with detail listing that evidence

#### Scenario: No invented reasons
- **WHEN** a recommendation's interest signal is 0
- **THEN** it has no `interest` reason

#### Scenario: Reasons replaced on regeneration
- **WHEN** a recommendation is regenerated and its activity signal drops to 0
- **THEN** its previous `activity` reason is gone

### Requirement: Match labels
Each recommendation SHALL carry a match label derived from its score and the active configuration's bands: `strong`, `good` or `partial`. With `v1-deterministic` the bands SHALL be: strong at 0.55 or more, good at 0.35 or more, partial below that. The label, not the score, SHALL be what users see. The system SHALL NOT present any score as a percentage, a probability of success, or a measure of expertise.

#### Scenario: Band boundaries
- **WHEN** recommendations score 0.60, 0.40 and 0.20 under `v1-deterministic`
- **THEN** their labels are strong, good and partial

#### Scenario: No percentages
- **WHEN** a user views any recommendation
- **THEN** no percentage or numeric match score is shown
