## MODIFIED Requirements

### Requirement: Versioned scoring configuration
The system SHALL keep scoring configurations as versioned records, each with a unique version name, a weight per signal, match-label score bands, the parameters of the activity, openness and issue signals, and a creation time. Exactly one configuration SHALL be active at a time whenever any is stored, also after the seeding migrations are applied, reversed and re-applied in any order. The initial configuration `v1-deterministic` SHALL use the weights skill 0.40, language 0.20, interest 0.15, framework 0.10, activity 0.10 and contribution openness 0.05, and SHALL be described as experimental; it SHALL remain stored unchanged, and scoring under it SHALL treat the issue fit and difficulty fit weights as 0. The configuration `v2-deterministic` SHALL use the weights skill 0.35, language 0.15, interest 0.15, framework 0.10, activity 0.10, contribution openness 0.05, issue fit 0.05 and difficulty fit 0.05, SHALL include the issue matching parameters (issue score weights, minimum issue score, relevant issues kept per recommendation, difficulty fit table, issue fit saturation count), SHALL be described as experimental, and SHALL become the active configuration when it is seeded while no configuration or only `v1-deterministic` is active; when an operator has activated any other configuration, seeding SHALL store `v2-deterministic` inactive and leave the operator's choice active. A configuration MAY set the difficulty fit mode (`best` or `weighted`), enable relevance scaling, and set a minimum score with its basis; a configuration that sets none of them SHALL score exactly as before these options existed, and neither `v1-deterministic` nor `v2-deterministic` sets them. A new configuration SHALL replace the active one only under the rule in `recommendation-evaluation` ("Replacing the active configuration"). A new configuration SHALL be rejected when a weight is negative, a signal is missing, a parameter is missing or out of range, an optional parameter has an unknown value, or the weights do not sum to 1. A configuration that produced recommendations SHALL NOT be deletable.

#### Scenario: Seeded configurations
- **WHEN** the system is migrated from an empty database
- **THEN** `v1-deterministic` and `v2-deterministic` exist with their documented weights, and `v2-deterministic` is active

#### Scenario: Upgrade activates v2
- **WHEN** a system running `v1-deterministic` is migrated
- **THEN** `v2-deterministic` becomes active and the next freshness sweep regenerates recommendations under it

#### Scenario: Operator's configuration kept on upgrade
- **WHEN** a system whose active configuration is an operator-created one is migrated through the `v2-deterministic` seed
- **THEN** the operator's configuration stays active and `v2-deterministic` is stored inactive

#### Scenario: Seeds reversed and re-applied
- **WHEN** the seeding migrations are reversed to before `v2-deterministic` and applied again, with or without recommendations under `v1-deterministic`
- **THEN** after each step that leaves any configuration stored exactly one is active, and `v2-deterministic` is active at the end

#### Scenario: Earlier versions unchanged
- **WHEN** `v1-deterministic` or `v2-deterministic` is evaluated after the optional parameters were added
- **THEN** its metrics on `benchmark-v1` equal the recorded baseline

#### Scenario: Invalid minimum score basis
- **WHEN** an operator saves a configuration whose `min_score_basis` is `issues`, or whose `min_score` is 1.5
- **THEN** it is rejected with a validation error

#### Scenario: Unknown difficulty fit mode
- **WHEN** an operator saves a configuration whose difficulty fit mode is `average`
- **THEN** it is rejected with a validation error

#### Scenario: Invalid weights
- **WHEN** an operator saves a configuration whose weights sum to 0.9
- **THEN** it is rejected with a validation error

#### Scenario: Config in use
- **WHEN** an operator tries to delete a configuration referenced by recommendations
- **THEN** the deletion is refused
