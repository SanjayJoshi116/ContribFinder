## ADDED Requirements

### Requirement: Uncertainty of a comparison
For every configuration after the baseline, evaluation SHALL estimate the uncertainty of each metric's difference from the baseline with a paired bootstrap over developers: each resample draws as many developers as the dataset holds, with replacement, and takes the mean over the drawn developers of the candidate's value minus the baseline's value for the same developer, from unrounded per-developer values. The report SHALL give, per metric, the observed mean difference, the 2.5th and 97.5th percentiles of the resampled differences as a 95% interval, and the share of resamples whose difference is 0 or below, and SHALL mark a difference whose interval lies entirely above or entirely below 0. The number of resamples (default 10,000) and the random seed (default fixed) SHALL be settable, and the same dataset, configurations, resample count and seed SHALL always give the same figures. A dataset with one developer SHALL report an interval of zero width at the observed difference. These figures SHALL NOT change the improvement verdict, the regression baseline or activation.

#### Scenario: Reproducible interval
- **WHEN** the same comparison is evaluated twice with the default resample count and seed
- **THEN** both reports give the same intervals and shares

#### Scenario: Noise is visible
- **WHEN** a candidate is better than the baseline for one of six developers and equal for the other five
- **THEN** its NDCG@10 interval includes 0 and the difference is not marked

#### Scenario: Consistent improvement
- **WHEN** a candidate's NDCG@10 is higher than the baseline's for every developer
- **THEN** its interval lies above 0, the difference is marked, and the share of resamples not better is 0

#### Scenario: Verdict unchanged
- **WHEN** a candidate meets the improvement rule but its NDCG@10 interval includes 0
- **THEN** it is still reported as an improvement, and `--require-improvement` succeeds

## MODIFIED Requirements

### Requirement: Evaluation command
A management command SHALL evaluate one or more scoring configurations against a dataset (default: the selection benchmark, `benchmark-v2` once it exists with at least one judged real developer, otherwise `benchmark-v1`). A configuration SHALL be given as a stored version or as a JSON file holding weights and params; both SHALL pass the same validation as stored configurations, and an unknown version or invalid configuration SHALL stop the command with an error before any evaluation. The first configuration SHALL be the baseline (default: the active configuration when none is given). The command SHALL print, per configuration, the dataset-level metrics and the difference from the baseline, for every configuration after the baseline the uncertainty of each metric's difference (see "Uncertainty of a comparison"), and per developer the metrics and the top 10 with their judgments. With a JSON output option it SHALL also write the full report, including the uncertainty of each comparison, to a file, creating the file's folder when missing; a report that cannot be written SHALL end the command with an error naming the path, not a traceback. It SHALL NOT change any stored data.

#### Scenario: Compare two stored versions
- **WHEN** the command runs with `v1-deterministic` and `v2-deterministic`
- **THEN** it prints both configurations' metrics with v2's difference from v1, and no stored row changes

#### Scenario: Unknown version
- **WHEN** a requested version does not exist
- **THEN** the command exits with an error and evaluates nothing

#### Scenario: Unsaved configuration
- **WHEN** a configuration is given as a JSON file that passes validation
- **THEN** it is evaluated without being stored

#### Scenario: JSON report in a new folder
- **WHEN** the JSON output path is in a folder that does not exist yet
- **THEN** the folder is created and the report is written there

#### Scenario: Comparison with its uncertainty
- **WHEN** the command runs with `v1-deterministic` and `v2-deterministic`
- **THEN** for each metric it prints v2's difference from v1 with a 95% interval and the share of resamples in which v2 is not better

