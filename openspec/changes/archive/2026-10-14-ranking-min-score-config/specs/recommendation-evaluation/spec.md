## MODIFIED Requirements

### Requirement: Evaluation ranks as generation does
Evaluation SHALL rank each benchmark developer's pool with exactly the stages recommendation generation uses (repository technologies, signals, issue matching for candidates that pass the relevance gate, weighted score, relevance gate, minimum score, top-N cut and tie-breaking) and the same minimum score (the configuration's own when it sets one, otherwise the setting) and top-N setting. An explicit override of the minimum score or top N SHALL apply to every evaluated configuration and SHALL be shown in the report. Evaluation SHALL use no database data besides scoring configurations and SHALL make no GitHub, LLM or embedding calls. For the same dataset and configuration it SHALL produce the same ranking every time.

#### Scenario: Same order as generation
- **WHEN** a developer's stored features and candidates are ranked by generation and the same values are ranked by evaluation under the same configuration
- **THEN** both produce the same repositories in the same order

#### Scenario: Gate applies
- **WHEN** a benchmark candidate has no skill, language, framework or interest match
- **THEN** it is not in the evaluated ranking, even if it is judged relevant, and so lowers recall

### Requirement: Holdout benchmark
The repository SHALL include a holdout dataset `holdout-v1`, in the benchmark format, with at least four benchmark developers whose profiles differ from those in `benchmark-v1` (including at least one beginner and one developer whose strongest match is a quiet, low-activity repository). Its judgments SHALL be written before any candidate configuration of the change that introduces it is evaluated. The holdout SHALL only be used to accept or reject a configuration already chosen on `benchmark-v1`, never to choose between candidates. A holdout whose results for a change's candidates were recorded SHALL NOT be the acceptance set of a later change; that change SHALL add a fresh holdout, judged before any of its candidates is evaluated. `holdout-v1` was used this way by `ranking-v3-deterministic` and `holdout-v2` by `ranking-min-score-config`; the next change that evaluates candidates SHALL add `holdout-v3`. It SHALL contain no real GitHub user data.

#### Scenario: Used holdout
- **WHEN** a change evaluates candidates after `holdout-v1` and `holdout-v2` results for earlier candidates were recorded
- **THEN** it adds `holdout-v3` and accepts or rejects its chosen candidate on it, not on `holdout-v1` or `holdout-v2`

#### Scenario: Fresh holdout loads
- **WHEN** `holdout-v2` is loaded
- **THEN** it validates, with at least four developers, none sharing an identifier with `benchmark-v1` or `holdout-v1`

#### Scenario: Holdout loads
- **WHEN** `holdout-v1` is loaded
- **THEN** it validates, with at least four developers, none sharing an identifier with `benchmark-v1`

### Requirement: Replacing the active configuration
A new configuration SHALL replace the active one only when, under the improvement rule, it is an improvement over every stored configuration on `benchmark-v1`, and on the current acceptance holdout (see "Holdout benchmark") none of its dataset-level metrics is lower than the active configuration's by more than the tolerance. Every candidate configuration evaluated while choosing it SHALL be recorded with its metrics on both datasets, including those not chosen. When no candidate qualifies, the active configuration SHALL stay active.

#### Scenario: Wins on benchmark, regresses on holdout
- **WHEN** a candidate is an improvement over v1 and v2 on `benchmark-v1` but its Recall@10 on the acceptance holdout is 0.05 below v2's
- **THEN** it does not replace v2

#### Scenario: No qualifying candidate
- **WHEN** no evaluated candidate meets the rule
- **THEN** the active configuration is unchanged and the recorded candidates show why each failed
