## ADDED Requirements

### Requirement: Holdout benchmark
The repository SHALL include a holdout dataset `holdout-v1`, in the benchmark format, with at least four benchmark developers whose profiles differ from those in `benchmark-v1` (including at least one beginner and one developer whose strongest match is a quiet, low-activity repository). Its judgments SHALL be written before any candidate configuration of the change that introduces it is evaluated. The holdout SHALL only be used to accept or reject a configuration already chosen on `benchmark-v1`, never to choose between candidates. It SHALL contain no real GitHub user data.

#### Scenario: Holdout loads
- **WHEN** `holdout-v1` is loaded
- **THEN** it validates, with at least four developers, none sharing an identifier with `benchmark-v1`

### Requirement: Replacing the active configuration
A new configuration SHALL replace the active one only when, under the improvement rule, it is an improvement over every stored configuration on `benchmark-v1`, and on `holdout-v1` none of its dataset-level metrics is lower than the active configuration's by more than the tolerance. Every candidate configuration evaluated while choosing it SHALL be recorded with its metrics on both datasets, including those not chosen. When no candidate qualifies, the active configuration SHALL stay active.

#### Scenario: Wins on benchmark, regresses on holdout
- **WHEN** a candidate is an improvement over v1 and v2 on `benchmark-v1` but its Recall@10 on `holdout-v1` is 0.05 below v2's
- **THEN** it does not replace v2

#### Scenario: No qualifying candidate
- **WHEN** no evaluated candidate meets the rule
- **THEN** the active configuration is unchanged and the recorded candidates show why each failed
