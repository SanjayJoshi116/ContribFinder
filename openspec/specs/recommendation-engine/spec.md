# recommendation-engine Specification

## Purpose

Scores and ranks each developer's analyzed candidate repositories against their evidence-backed profile with deterministic, versioned and configurable signals, so that every stored recommendation can be traced to the data and configuration that produced it.

## Requirements

### Requirement: Repository technologies
The system SHALL derive each candidate repository's technologies from its stored data, using the same skill catalog as the developer profile: languages (with their share of the repository's code), topics, and dependency manifest entries. Each detected technology SHALL record its catalog category and the sources that detected it. Technologies SHALL be derived from stored data only, without calling GitHub.

#### Scenario: Stack from several sources
- **WHEN** a repository is 80% Python, has the topic `django`, and its `requirements.txt` lists `django` and `celery`
- **THEN** its technologies are Python (language, from languages, 80% share), Django (framework, from topic and dependency) and Celery (from dependency)

#### Scenario: No detectable technologies
- **WHEN** a repository has no languages, no catalog topics and no manifests
- **THEN** its technology set is empty, and every technology-based signal for it is 0

### Requirement: Relevance signals
For each candidate, the system SHALL calculate these signals independently, each as a value from 0.0 to 1.0 together with the evidence that produced it:
- **skill match**: how much of the repository's technology set the developer has demonstrated, weighted by the developer's confidence in each skill;
- **language match**: the repository's code share in languages the developer knows, weighted by the developer's confidence in each language;
- **framework match**: overlap between the repository's frameworks and the developer's framework skills;
- **interest match**: overlap between the interests the repository's topics and description express and the developer's detected interests, weighted by interest strength;
- **activity signal**: the repository's latest activity label, mapped to a configured value;
- **contribution openness**: observable contribution affordances (contribution guidelines, issue templates, `good first issue` and `help wanted` labels), each worth a configured amount;
- **issue fit**: the availability of relevant issues for the developer in the repository (see `issue-matching`), growing with their number and scores up to a configured saturation count;
- **difficulty fit**: how well the estimated difficulty of the repository's relevant issues suits the developer's internal experience level; issues with `unknown` difficulty SHALL NOT contribute. The configuration SHALL choose the mode: `best` (the default when the configuration names none) takes the best difficulty-table value among the relevant issues with known difficulty; `weighted` takes the mean of their table values weighted by issue score, multiplied by the issue fit value.

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

#### Scenario: One weak fitting issue, weighted mode
- **WHEN** a repository has a single relevant beginner issue for a beginner developer, its issue fit is 0.2, and the configuration uses `weighted` difficulty fit
- **THEN** its difficulty fit is 0.2, whereas under `best` it would be 1.0

#### Scenario: Mixed difficulties, weighted mode
- **WHEN** an intermediate developer's repository has two relevant issues with known difficulty, one beginner (table value 0.7, issue score 0.6) and one intermediate (table value 1.0, issue score 0.3), issue fit is 0.3, and the mode is `weighted`
- **THEN** its difficulty fit is ((0.7 × 0.6 + 1.0 × 0.3) / 0.9) × 0.3 = 0.24

### Requirement: Versioned scoring configuration
The system SHALL keep scoring configurations as versioned records, each with a unique version name, a weight per signal, match-label score bands, the parameters of the activity, openness and issue signals, and a creation time. Exactly one configuration SHALL be active at a time whenever any is stored, also after the seeding migrations are applied, reversed and re-applied in any order. The initial configuration `v1-deterministic` SHALL use the weights skill 0.40, language 0.20, interest 0.15, framework 0.10, activity 0.10 and contribution openness 0.05, and SHALL be described as experimental; it SHALL remain stored unchanged, and scoring under it SHALL treat the issue fit and difficulty fit weights as 0. The configuration `v2-deterministic` SHALL use the weights skill 0.35, language 0.15, interest 0.15, framework 0.10, activity 0.10, contribution openness 0.05, issue fit 0.05 and difficulty fit 0.05, SHALL include the issue matching parameters (issue score weights, minimum issue score, relevant issues kept per recommendation, difficulty fit table, issue fit saturation count), SHALL be described as experimental, and SHALL become the active configuration when seeding creates it while no configuration or only `v1-deterministic` is active; when an operator has activated any other configuration, seeding SHALL store `v2-deterministic` inactive and leave the operator's choice active. When `v2-deterministic` is already stored as seeding runs (it was kept by a rollback because it produced recommendations, or an operator deactivated it), seeding SHALL NOT change which configuration is active. A configuration MAY set the difficulty fit mode (`best` or `weighted`), enable relevance scaling, and set a minimum score with its basis; a configuration that sets none of them SHALL score exactly as before these options existed, and neither `v1-deterministic` nor `v2-deterministic` sets them. A new configuration SHALL replace the active one only under the rule in `recommendation-evaluation` ("Replacing the active configuration"). A new configuration SHALL be rejected when a weight is negative, a signal is missing, a parameter is missing or out of range, an optional parameter has an unknown value, the weights do not sum to 1, or the openness points sum to more than 1. A configuration that produced recommendations SHALL NOT be deletable. Once stored, a configuration's version name, weights and parameters SHALL NOT change, whether or not it produced recommendations; different numbers SHALL need a new version. Activation SHALL remain possible.

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

### Requirement: Recommendation score and ranking
The system SHALL score each candidate as the weighted sum of its signals under the active configuration, giving a value from 0.0 to 1.0 used only for internal ranking. When the configuration enables relevance scaling, the weighted contributions of activity, contribution openness, issue fit and difficulty fit SHALL each be multiplied by the candidate's relevance strength, which is the weighted mean of its skill, language, framework and interest signals under the configuration's weights (0 when those weights sum to 0); stored signal values SHALL NOT change. Only candidates whose repository is eligible and has completed analysis SHALL be scored: a repository that is recommendable, or that is stale or being refreshed and was recommendable before, SHALL be scored from its stored data. Repositories the developer dismissed SHALL be left out before the top N is taken, including those dismissed while the generation runs, so a dismissal never leaves fewer than N recommendations while other candidates qualify. Every stored score, signal value, match label, reason and relevant issue SHALL be computed from the same set of issues, all of which exist, with the same analysis, when the result is stored. Candidates SHALL be ranked by score, then by best search rank, then by repository name. The system SHALL keep the top N (configured, default 50, never fewer than 20) whose score is at least the minimum score and that have at least one relevance signal (skill, language, framework or interest match) that contributes to the score, with a value above 0 and a configured weight above 0, as the developer's recommendations; the same rule SHALL decide which candidates have their issues matched; activity, contribution openness, issue fit and difficulty fit alone SHALL NOT make a candidate a recommendation. The minimum score SHALL come from the configuration when it sets one (`min_score`, 0..1), otherwise from the installation setting (default 0.10). The configuration MAY set the basis the minimum applies to: `score` (the default: the whole weighted score) or `relevance` (the sum of the skill, language, framework and interest contributions only, which relevance scaling never changes). Each recommendation SHALL store its score, each signal's value, its rank, its match label, its generation time, its relevant issues and a non-null reference to the configuration that produced it. Candidates that fall out of the top N SHALL stop being recommendations. A recommendation for the same developer and repository SHALL keep its identity across regenerations.

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
- **WHEN** a candidate's repository is ineligible, failed, not yet analyzed, or stale after it was found ineligible
- **THEN** it is not scored and is not a recommendation

#### Scenario: Config recorded
- **WHEN** recommendations are generated under the active configuration
- **THEN** every recommendation references that configuration

#### Scenario: Stable identity
- **WHEN** recommendations are regenerated and repository R stays in the top N
- **THEN** R's recommendation keeps its id, with updated score, signals, rank, relevant issues and generation time

#### Scenario: Stale repository stays recommended
- **WHEN** repository R is recommended, the staleness sweep marks it stale, and recommendations are regenerated before it is refreshed
- **THEN** R is still recommended, with the same recommendation id, scored from its stored data

#### Scenario: Dismissed while generating
- **WHEN** the top N is 20, a developer has 25 qualifying candidates, and they dismiss one of the top 20 while a generation runs
- **THEN** the generation stores 20 recommendations, none of them the dismissed repository

#### Scenario: Issue closed while generating
- **WHEN** a matched issue of repository R is deleted, or re-analyzed, by an issue refresh after the generation loaded it and before the result is stored
- **THEN** R's stored issue count, issue signals, match label and reasons do not count that issue

#### Scenario: Relevance signal weighted 0
- **WHEN** a configuration weights interest 0 and a candidate matches only the developer's interests
- **THEN** it is not a recommendation and its issues are not matched

### Requirement: Recommendation generation job
The system SHALL generate recommendations in a background job per user, tracked like other jobs, that reads only stored data. A job SHALL start when the user's repository discovery completes. At most one generation job SHALL be active per user. When a generation is requested while the user's generation job is already running, that job SHALL be followed by another generation once it completes, so the request is reflected even if the running job loaded its inputs before it. A run that starts after the request (a pending or retrying job) SHALL NOT run again for it. When matched issues are deleted or re-analyzed between ranking and storing, the job SHALL rank again from stored data, at most 3 times in total, and then fail without changing the stored recommendations. A failed generation SHALL keep the user's previous recommendations unchanged. A developer with no eligible candidates SHALL end with no recommendations and a completed job.

#### Scenario: After discovery
- **WHEN** a user's discovery job completes
- **THEN** a recommendation generation job for that user starts in the background

#### Scenario: Failure keeps old results
- **WHEN** a generation job fails while writing
- **THEN** the user's recommendations are exactly those of the previous successful generation

#### Scenario: Restore during a running generation
- **WHEN** a user restores a dismissed repository while their generation job is running
- **THEN** after that job completes another generation runs, and the restored repository can be among its recommendations

#### Scenario: Request while pending
- **WHEN** a generation is requested while the user's generation job is still pending
- **THEN** no further job is added, and the pending job's result reflects the request

#### Scenario: Issues keep changing
- **WHEN** matched issues disappear before every one of 3 attempts to store the result
- **THEN** the job fails and the user's recommendations are exactly those of the previous successful generation

### Requirement: Recommendation freshness
The system SHALL periodically (configured interval, default 30 minutes) start a generation job for every developer whose recommendations are older than their profile analysis, older than the latest analysis of a repository in their pool, or produced by a configuration that is no longer active. A repository being marked stale or picked up for a refresh SHALL NOT by itself make recommendations outdated; new data fetched for it (even if it was marked stale since), a completed refresh, a failure or any other analysis SHALL. After a failed generation, the next one SHALL wait a configured delay (default 6 hours) unless the user or a pipeline step starts it. A developer who has recommendations but no candidates left SHALL also get a generation job. It SHALL NOT start a job for a developer whose recommendations are current, or who has an active generation job.

#### Scenario: Repository refreshed
- **WHEN** the backlog refreshes a pooled repository after the developer's recommendations were generated
- **THEN** the next freshness run starts a generation job for that developer

#### Scenario: New configuration activated
- **WHEN** an operator activates configuration `v2`
- **THEN** the next freshness run regenerates every developer's recommendations under `v2`

#### Scenario: Nothing changed
- **WHEN** nothing relevant changed since the last generation
- **THEN** no job is started

#### Scenario: Marked stale only
- **WHEN** the staleness sweep marks a pooled repository stale and nothing else changed since the last generation
- **THEN** no job is started

#### Scenario: Analyzed, then marked stale before the sweep
- **WHEN** a pooled repository is analyzed after the last generation and marked stale before the next freshness run
- **THEN** that run starts a generation job

#### Scenario: Running generation left alone
- **WHEN** a developer is due and their generation job is running
- **THEN** the freshness run starts nothing and does not ask the running job to run again

#### Scenario: Failed generation backs off
- **WHEN** a developer's latest generation failed 10 minutes ago and they are otherwise due
- **THEN** the freshness run starts no job; after the configured delay it does

#### Scenario: Pool emptied
- **WHEN** a developer has recommendations and their candidate pool became empty
- **THEN** the next freshness run starts a generation job, which leaves them with no recommendations
