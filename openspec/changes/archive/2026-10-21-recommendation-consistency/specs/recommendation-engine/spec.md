## MODIFIED Requirements

### Requirement: Recommendation score and ranking
The system SHALL score each candidate as the weighted sum of its signals under the active configuration, giving a value from 0.0 to 1.0 used only for internal ranking. When the configuration enables relevance scaling, the weighted contributions of activity, contribution openness, issue fit and difficulty fit SHALL each be multiplied by the candidate's relevance strength, which is the weighted mean of its skill, language, framework and interest signals under the configuration's weights (0 when those weights sum to 0); stored signal values SHALL NOT change. Only candidates whose repository is eligible and has completed analysis SHALL be scored: a repository that is recommendable, or that is stale or being refreshed and was recommendable before, SHALL be scored from its stored data. Repositories the developer dismissed SHALL be left out before the top N is taken, including those dismissed while the generation runs, so a dismissal never leaves fewer than N recommendations while other candidates qualify. Every stored score, signal value, match label, reason and relevant issue SHALL be computed from the same set of issues, all of which exist when the result is stored. Candidates SHALL be ranked by score, then by best search rank, then by repository name. The system SHALL keep the top N (configured, default 50, never fewer than 20) whose score is at least the minimum score and that have at least one relevance signal (skill, language, framework or interest match) above 0 as the developer's recommendations; activity, contribution openness, issue fit and difficulty fit alone SHALL NOT make a candidate a recommendation. The minimum score SHALL come from the configuration when it sets one (`min_score`, 0..1), otherwise from the installation setting (default 0.10). The configuration MAY set the basis the minimum applies to: `score` (the default: the whole weighted score) or `relevance` (the sum of the skill, language, framework and interest contributions only, which relevance scaling never changes). Each recommendation SHALL store its score, each signal's value, its rank, its match label, its generation time, its relevant issues and a non-null reference to the configuration that produced it. Candidates that fall out of the top N SHALL stop being recommendations. A recommendation for the same developer and repository SHALL keep its identity across regenerations.

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
- **WHEN** a matched issue of repository R is deleted by an issue refresh after the generation loaded it and before the result is stored
- **THEN** R's stored issue count, issue signals, match label and reasons do not count that issue

### Requirement: Recommendation generation job
The system SHALL generate recommendations in a background job per user, tracked like other jobs, that reads only stored data. A job SHALL start when the user's repository discovery completes. At most one generation job SHALL be active per user. When a generation is requested while the user's generation job is already running, that job SHALL be followed by another generation once it completes, so the request is reflected even if the running job loaded its inputs before it. When matched issues change between ranking and storing, the job SHALL rank again from stored data, at most 3 times in total, and then fail without changing the stored recommendations. A failed generation SHALL keep the user's previous recommendations unchanged. A developer with no eligible candidates SHALL end with no recommendations and a completed job.

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
The system SHALL periodically (configured interval, default 30 minutes) start a generation job for every developer whose recommendations are older than their profile analysis, older than the latest analysis of a repository in their pool, or produced by a configuration that is no longer active. A repository being marked stale or picked up for a refresh SHALL NOT by itself make recommendations outdated; a completed refresh, a failure or any other analysis SHALL. A developer who has recommendations but no candidates left SHALL also get a generation job. It SHALL NOT start a job for a developer whose recommendations are current, or who has an active generation job.

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

#### Scenario: Pool emptied
- **WHEN** a developer has recommendations and their candidate pool became empty
- **THEN** the next freshness run starts a generation job, which leaves them with no recommendations
