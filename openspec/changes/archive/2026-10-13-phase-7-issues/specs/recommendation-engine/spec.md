## MODIFIED Requirements

### Requirement: Relevance signals
For each candidate, the system SHALL calculate these signals independently, each as a value from 0.0 to 1.0 together with the evidence that produced it:
- **skill match**: how much of the repository's technology set the developer has demonstrated, weighted by the developer's confidence in each skill;
- **language match**: the repository's code share in languages the developer knows, weighted by the developer's confidence in each language;
- **framework match**: overlap between the repository's frameworks and the developer's framework skills;
- **interest match**: overlap between the interests the repository's topics and description express and the developer's detected interests, weighted by interest strength;
- **activity signal**: the repository's latest activity label, mapped to a configured value;
- **contribution openness**: observable contribution affordances (contribution guidelines, issue templates, `good first issue` and `help wanted` labels), each worth a configured amount;
- **issue fit**: the availability of relevant issues for the developer in the repository (see `issue-matching`), growing with their number and scores up to a configured saturation count;
- **difficulty fit**: how well the estimated difficulty of the repository's relevant issues suits the developer's internal experience level; issues with `unknown` difficulty SHALL NOT contribute.

A signal with no supporting data SHALL be 0 with no evidence; it SHALL NOT be guessed. Skills whose only evidence is a README mention SHALL count at their stored (low) confidence and never as full matches. No single signal SHALL determine a recommendation on its own. Signal calculation SHALL NOT call GitHub or any AI service.

#### Scenario: Strong Python/Django match
- **WHEN** the developer has high-confidence Python and Django skills and the repository is mostly Python and depends on Django
- **THEN** language match and framework match are high, and their evidence names Python and Django

#### Scenario: Unknown activity
- **WHEN** a repository has no activity snapshot
- **THEN** its activity signal is 0 with no evidence

#### Scenario: Deterministic
- **WHEN** signals are calculated twice for the same profile, repository data and configuration
- **THEN** the values and evidence are identical

#### Scenario: No relevant issues
- **WHEN** a repository has no relevant issues for the developer
- **THEN** its issue fit and difficulty fit are 0 with no evidence

#### Scenario: Only unknown difficulties
- **WHEN** all of a repository's relevant issues have `unknown` difficulty
- **THEN** its issue fit is above 0 and its difficulty fit is 0

### Requirement: Versioned scoring configuration
The system SHALL keep scoring configurations as versioned records, each with a unique version name, a weight per signal, match-label score bands, the parameters of the activity, openness and issue signals, and a creation time. Exactly one configuration SHALL be active at a time. The initial configuration `v1-deterministic` SHALL use the weights skill 0.40, language 0.20, interest 0.15, framework 0.10, activity 0.10 and contribution openness 0.05, and SHALL be described as experimental; it SHALL remain stored unchanged, and scoring under it SHALL treat the issue fit and difficulty fit weights as 0. The configuration `v2-deterministic` SHALL use the weights skill 0.35, language 0.15, interest 0.15, framework 0.10, activity 0.10, contribution openness 0.05, issue fit 0.05 and difficulty fit 0.05, SHALL include the issue matching parameters (issue score weights, minimum issue score, relevant issues kept per recommendation, difficulty fit table, issue fit saturation count), SHALL be described as experimental, and SHALL become the active configuration when it is seeded. A new configuration SHALL be rejected when a weight is negative, a signal is missing, a parameter is missing or out of range, or the weights do not sum to 1. A configuration that produced recommendations SHALL NOT be deletable.

#### Scenario: Seeded configurations
- **WHEN** the system is migrated from an empty database
- **THEN** `v1-deterministic` and `v2-deterministic` exist with their documented weights, and `v2-deterministic` is active

#### Scenario: Upgrade activates v2
- **WHEN** a system running `v1-deterministic` is migrated
- **THEN** `v2-deterministic` becomes active and the next freshness sweep regenerates recommendations under it

#### Scenario: Invalid weights
- **WHEN** an operator saves a configuration whose weights sum to 0.9
- **THEN** it is rejected with a validation error

#### Scenario: Config in use
- **WHEN** an operator tries to delete a configuration referenced by recommendations
- **THEN** the deletion is refused

### Requirement: Recommendation score and ranking
The system SHALL score each candidate as the weighted sum of its signals under the active configuration, giving a value from 0.0 to 1.0 used only for internal ranking. Only candidates whose repository is eligible and recommendable SHALL be scored. Candidates SHALL be ranked by score, then by best search rank, then by repository name. The system SHALL keep the top N (configured, default 50, never fewer than 20) whose score is at least the configured minimum (default 0.10) and that have at least one relevance signal (skill, language, framework or interest match) above 0 as the developer's recommendations; activity, contribution openness, issue fit and difficulty fit alone SHALL NOT make a candidate a recommendation. Each recommendation SHALL store its score, each signal's value, its rank, its match label, its generation time, its relevant issues and a non-null reference to the configuration that produced it. Candidates that fall out of the top N SHALL stop being recommendations. A recommendation for the same developer and repository SHALL keep its identity across regenerations.

#### Scenario: Ranking
- **WHEN** a developer has 30 eligible candidates and the top N is 20
- **THEN** the 20 highest-scoring candidates at or above the minimum score are stored as recommendations, in score order

#### Scenario: Activity alone is not relevance
- **WHEN** a candidate matches none of the developer's skills, languages, frameworks or interests but is recently active and open to contributions
- **THEN** it is not a recommendation, whatever its score

#### Scenario: Issues alone are not relevance
- **WHEN** a candidate matches none of the developer's skills, languages, frameworks or interests but has many beginner-labeled issues
- **THEN** it is not a recommendation, whatever its score

#### Scenario: Ineligible candidates excluded
- **WHEN** a candidate's repository is ineligible, failed or not yet analyzed
- **THEN** it is not scored and is not a recommendation

#### Scenario: Config recorded
- **WHEN** recommendations are generated under `v2-deterministic`
- **THEN** every recommendation references `v2-deterministic`

#### Scenario: Stable identity
- **WHEN** recommendations are regenerated and repository R stays in the top N
- **THEN** R's recommendation keeps its id, with updated score, signals, rank, relevant issues and generation time
