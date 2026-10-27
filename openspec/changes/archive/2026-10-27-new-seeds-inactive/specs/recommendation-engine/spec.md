## MODIFIED Requirements

### Requirement: Versioned scoring configuration
The system SHALL keep scoring configurations as versioned records, each with a unique version name, a weight per signal, match-label score bands, the parameters of the activity, openness and issue signals, and a creation time. Exactly one configuration SHALL be active at a time whenever any is stored, also after the seeding migrations are applied, reversed and re-applied in any order. The initial configuration `v1-deterministic` SHALL use the weights skill 0.40, language 0.20, interest 0.15, framework 0.10, activity 0.10 and contribution openness 0.05, and SHALL be described as experimental; it SHALL remain stored unchanged, and scoring under it SHALL treat the issue fit and difficulty fit weights as 0. The configuration `v2-deterministic` SHALL use the weights skill 0.35, language 0.15, interest 0.15, framework 0.10, activity 0.10, contribution openness 0.05, issue fit 0.05 and difficulty fit 0.05, SHALL include the issue matching parameters (issue score weights, minimum issue score, relevant issues kept per recommendation, difficulty fit table, issue fit saturation count), SHALL be described as experimental, and SHALL become the active configuration when seeding creates it while no configuration or only `v1-deterministic` is active; when an operator has activated any other configuration, seeding SHALL store `v2-deterministic` inactive and leave the operator's choice active. When `v2-deterministic` is already stored as seeding runs (it was kept by a rollback because it produced recommendations, or an operator deactivated it), seeding SHALL NOT change which configuration is active. Every configuration seeded after `v2-deterministic` SHALL be stored inactive, and its seed SHALL NOT change which configuration is active, whether or not the version is already stored; the operator activates it under "Activating a configuration" in `recommendation-evaluation`. Reversing such a seed SHALL delete its version only when that version is inactive and produced no recommendations, and SHALL otherwise leave it stored and the active configuration unchanged. A configuration MAY set the difficulty fit mode (`best` or `weighted`), enable relevance scaling, and set a minimum score with its basis; a configuration that sets none of them SHALL score exactly as before these options existed, and neither `v1-deterministic` nor `v2-deterministic` sets them. A new configuration SHALL replace the active one only under the rule in `recommendation-evaluation` ("Replacing the active configuration"). A new configuration SHALL be rejected when a weight is negative, a signal is missing, a parameter is missing or out of range, an optional parameter has an unknown value, the weights do not sum to 1, or the openness points sum to more than 1. A configuration that produced recommendations SHALL NOT be deletable. Once stored, a configuration's version name, weights and parameters SHALL NOT change, whether or not it produced recommendations; different numbers SHALL need a new version. Activation SHALL remain possible.

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
- **WHEN** the seeding migrations are reversed to before `v2-deterministic` and applied again, with or without recommendations under `v1-deterministic`, and `v2-deterministic` had produced no recommendations
- **THEN** after each step that leaves any configuration stored exactly one is active, and `v2-deterministic` is active at the end

#### Scenario: Re-applied after a rollback that kept v2
- **WHEN** `v2-deterministic` produced recommendations, the seeding migrations are reversed to before it (so `v1-deterministic` becomes active and `v2-deterministic` stays stored inactive) and applied again
- **THEN** `v1-deterministic` stays the only active configuration

#### Scenario: Operator's v1 kept on re-apply
- **WHEN** an operator activated `v1-deterministic` while `v2-deterministic` was stored, and the `v2-deterministic` seed is reversed and applied again
- **THEN** `v1-deterministic` stays the only active configuration

#### Scenario: Later seed stored inactive
- **WHEN** a migration seeds a configuration version after `v2-deterministic` while `v2-deterministic` (or any operator choice) is active
- **THEN** the new version is stored inactive and the previously active configuration stays the only active one

#### Scenario: Later seed re-applied after the operator activated it
- **WHEN** an operator activated a version seeded after `v2-deterministic`, and its seed is applied again
- **THEN** the seed changes nothing: the version keeps its stored values and stays active

#### Scenario: Later seed reversed
- **WHEN** a seed after `v2-deterministic` is reversed while its version is inactive and produced no recommendations
- **THEN** the version is deleted and the active configuration is unchanged

#### Scenario: Later seed reversed while in use
- **WHEN** a seed after `v2-deterministic` is reversed while its version is active, or produced recommendations
- **THEN** the version stays stored and exactly one configuration stays active, unchanged

#### Scenario: Fully migrated database
- **WHEN** every migration has been applied to an empty database
- **THEN** the only active configuration is `v2-deterministic`, and every other stored configuration is inactive

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

#### Scenario: Openness points over 1
- **WHEN** a new configuration gives contribution guidelines 0.6 and `good first issue` 0.6
- **THEN** it is rejected, naming the openness points

#### Scenario: Stored configuration unchanged
- **WHEN** an operator edits the weights of a stored configuration that never produced recommendations
- **THEN** the change is refused and the stored weights stay as they were
