## MODIFIED Requirements

### Requirement: Recommendation score and ranking
The system SHALL score each candidate as the weighted sum of its signals under the active configuration, giving a value from 0.0 to 1.0 used only for internal ranking. When the configuration enables relevance scaling, the weighted contributions of activity, contribution openness, issue fit and difficulty fit SHALL each be multiplied by the candidate's relevance strength, which is the weighted mean of its skill, language, framework and interest signals under the configuration's weights (0 when those weights sum to 0); stored signal values SHALL NOT change. Only candidates whose repository is eligible and recommendable SHALL be scored. Candidates SHALL be ranked by score, then by best search rank, then by repository name. The system SHALL keep the top N (configured, default 50, never fewer than 20) whose score is at least the minimum score and that have at least one relevance signal (skill, language, framework or interest match) above 0 as the developer's recommendations; activity, contribution openness, issue fit and difficulty fit alone SHALL NOT make a candidate a recommendation. The minimum score SHALL come from the configuration when it sets one (`min_score`, 0..1), otherwise from the installation setting (default 0.10). The configuration MAY set the basis the minimum applies to: `score` (the default: the whole weighted score) or `relevance` (the sum of the skill, language, framework and interest contributions only, which relevance scaling never changes). Each recommendation SHALL store its score, each signal's value, its rank, its match label, its generation time, its relevant issues and a non-null reference to the configuration that produced it. Candidates that fall out of the top N SHALL stop being recommendations. A recommendation for the same developer and repository SHALL keep its identity across regenerations.

#### Scenario: Ranking
- **WHEN** a developer has 30 eligible candidates and the top N is 20
- **THEN** the 20 highest-scoring candidates at or above the minimum score are stored as recommendations, in score order

#### Scenario: Activity alone is not relevance
- **WHEN** a candidate matches none of the developer's skills, languages, frameworks or interests but is recently active and open to contributions
- **THEN** it is not a recommendation, whatever its score

#### Scenario: Issues alone are not relevance
- **WHEN** a candidate matches none of the developer's skills, languages, frameworks or interests but has many beginner-labeled issues
- **THEN** it is not a recommendation, whatever its score

#### Scenario: Relevance scaling
- **WHEN** relevance scaling is enabled and two candidates have identical activity, openness and issue signals, one with relevance strength 0.8 and one with 0.3
- **THEN** the offer signals add 0.8 and 0.3 times their weighted value respectively, and the stored signal values of both are unchanged

#### Scenario: Scaling off reproduces the weighted sum
- **WHEN** a configuration does not enable relevance scaling
- **THEN** its scores equal the plain weighted sum, as for `v1-deterministic` and `v2-deterministic`

#### Scenario: Configuration minimum wins
- **WHEN** the installation minimum is 0.10 and the active configuration sets `min_score` 0.05
- **THEN** a relevant candidate scoring 0.07 is kept

#### Scenario: Relevance basis
- **WHEN** the configuration sets `min_score` 0.10 with basis `relevance`, and a candidate has relevance contributions summing to 0.08 but a whole score of 0.20
- **THEN** it is not kept; a candidate with relevance contributions of 0.12 and a whole score of 0.15 is kept

#### Scenario: No configuration minimum
- **WHEN** a configuration sets neither `min_score` nor its basis, as `v1-deterministic` and `v2-deterministic`
- **THEN** the installation minimum applies to the whole score, as before

#### Scenario: Ineligible candidates excluded
- **WHEN** a candidate's repository is ineligible, failed or not yet analyzed
- **THEN** it is not scored and is not a recommendation

#### Scenario: Config recorded
- **WHEN** recommendations are generated under the active configuration
- **THEN** every recommendation references that configuration

#### Scenario: Stable identity
- **WHEN** recommendations are regenerated and repository R stays in the top N
- **THEN** R's recommendation keeps its id, with updated score, signals, rank, relevant issues and generation time

### Requirement: Versioned scoring configuration
The system SHALL keep scoring configurations as versioned records, each with a unique version name, a weight per signal, match-label score bands, the parameters of the activity, openness and issue signals, and a creation time. Exactly one configuration SHALL be active at a time. The initial configuration `v1-deterministic` SHALL use the weights skill 0.40, language 0.20, interest 0.15, framework 0.10, activity 0.10 and contribution openness 0.05, and SHALL be described as experimental; it SHALL remain stored unchanged, and scoring under it SHALL treat the issue fit and difficulty fit weights as 0. The configuration `v2-deterministic` SHALL use the weights skill 0.35, language 0.15, interest 0.15, framework 0.10, activity 0.10, contribution openness 0.05, issue fit 0.05 and difficulty fit 0.05, SHALL include the issue matching parameters (issue score weights, minimum issue score, relevant issues kept per recommendation, difficulty fit table, issue fit saturation count), SHALL be described as experimental, and SHALL become the active configuration when it is seeded. A configuration MAY set the difficulty fit mode (`best` or `weighted`), enable relevance scaling, and set a minimum score with its basis; a configuration that sets none of them SHALL score exactly as before these options existed, and neither `v1-deterministic` nor `v2-deterministic` sets them. A new configuration SHALL replace the active one only under the rule in `recommendation-evaluation` ("Replacing the active configuration"). A new configuration SHALL be rejected when a weight is negative, a signal is missing, a parameter is missing or out of range, an optional parameter has an unknown value, or the weights do not sum to 1. A configuration that produced recommendations SHALL NOT be deletable.

#### Scenario: Seeded configurations
- **WHEN** the system is migrated from an empty database
- **THEN** `v1-deterministic` and `v2-deterministic` exist with their documented weights, and `v2-deterministic` is active

#### Scenario: Upgrade activates v2
- **WHEN** a system running `v1-deterministic` is migrated
- **THEN** `v2-deterministic` becomes active and the next freshness sweep regenerates recommendations under it

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
