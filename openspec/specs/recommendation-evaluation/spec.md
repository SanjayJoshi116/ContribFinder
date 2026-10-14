# recommendation-evaluation Specification

## Purpose

Measures recommendation quality offline against a fixed, hand-labeled benchmark of developers, so a change to signals, weights or ranking counts as an improvement only when it wins on the benchmark, and an unintended ranking change is caught before it ships.

## Requirements

### Requirement: Benchmark dataset
The system SHALL read benchmark datasets from versioned, checked-in files. A dataset SHALL have a name, a format version and a list of benchmark developers. Each developer SHALL have an identifier, a free-text description, the matching inputs the ranking uses (skills with confidence, category and number of supporting repositories; interests with strength; internal experience level) and a candidate pool. Each candidate SHALL carry the repository data the ranking uses (full name, languages with bytes, topics, dependencies, contribution files and labels, activity snapshot, best search rank) and its eligible issues with their stored analysis (canonical labels, contribution type, difficulty, technologies). Each developer SHALL have relevance judgments by repository full name: `0` not relevant, `1` relevant, `2` highly relevant. A candidate without a judgment SHALL count as not relevant.

#### Scenario: Unjudged candidate
- **WHEN** a candidate in a developer's pool has no judgment
- **THEN** metrics treat it as not relevant and the report counts it as unjudged

### Requirement: Dataset validation
Loading a dataset SHALL fail with a message naming the developer and field when: the format version is unknown; an identifier is duplicated; a value is outside its allowed range (confidence and strength 0..1, judgment 0..2, experience level and issue difficulty outside their choice sets); a skill, interest or issue technology is not in the current catalog; a judgment names a repository that is not in that developer's pool; or a developer has no judgment of 1 or more. Evaluation SHALL NOT run on an invalid dataset.

#### Scenario: Judgment outside the pool
- **WHEN** a developer's judgments name a repository that is not one of their candidates
- **THEN** loading fails and names the developer and the repository

#### Scenario: No relevant judgment
- **WHEN** a developer has judgments but none is 1 or 2
- **THEN** loading fails, because recall and the rank metrics are undefined for them

### Requirement: Seed benchmark
The repository SHALL include a seed dataset `benchmark-v1` with at least five benchmark developers of different profiles (including at least one beginner) over a shared catalog of at least 30 fictional repositories, with every developer's top candidates judged by hand. It SHALL NOT contain data about real GitHub users.

#### Scenario: Seed dataset loads
- **WHEN** `benchmark-v1` is loaded
- **THEN** it validates, with at least five developers and every developer having at least one relevant judgment

### Requirement: Evaluation ranks as generation does
Evaluation SHALL rank each benchmark developer's pool with exactly the stages recommendation generation uses (repository technologies, signals, issue matching for candidates that pass the relevance gate, weighted score, relevance gate, minimum score, top-N cut and tie-breaking) and the same minimum score and top-N settings. Evaluation SHALL use no database data besides scoring configurations and SHALL make no GitHub, LLM or embedding calls. For the same dataset and configuration it SHALL produce the same ranking every time.

#### Scenario: Same order as generation
- **WHEN** a developer's stored features and candidates are ranked by generation and the same values are ranked by evaluation under the same configuration
- **THEN** both produce the same repositories in the same order

#### Scenario: Gate applies
- **WHEN** a benchmark candidate has no skill, language, framework or interest match
- **THEN** it is not in the evaluated ranking, even if it is judged relevant, and so lowers recall

### Requirement: Ranking metrics
For each developer the system SHALL compute, on the ranked list: Precision@5 and Precision@10 (relevant results in the top k divided by k, so a list shorter than k is penalized), Recall@10 (relevant results in the top 10 divided by the developer's relevant judgments), MRR (1 divided by the rank of the first relevant result, 0 if none) and NDCG@10 (gain `2^grade - 1`, discount `log2(rank + 1)`, normalized by the ideal ordering of the developer's judgments). A result is relevant when its judgment is 1 or more. The system SHALL also report, per developer, the number of unjudged results in the top 10. Dataset-level metrics SHALL be the mean over developers. Values SHALL be reported to 4 decimal places.

#### Scenario: Hand-computed values
- **WHEN** a developer judges A=2 and B=1 and the ranking is B, C, A
- **THEN** Precision@5 is 0.4, Recall@10 is 1.0, MRR is 1.0, and NDCG@10 is (1/log2(2) + 3/log2(4)) / (3/log2(2) + 1/log2(3)) rounded to 4 places

#### Scenario: Short list
- **WHEN** the ranking contains 3 results, all relevant
- **THEN** Precision@5 is 0.6 and Precision@10 is 0.3

### Requirement: Evaluation command
A management command SHALL evaluate one or more scoring configurations against a dataset (default `benchmark-v1`). A configuration SHALL be given as a stored version or as a JSON file holding weights and params; both SHALL pass the same validation as stored configurations, and an unknown version or invalid configuration SHALL stop the command with an error before any evaluation. The first configuration SHALL be the baseline (default: the active configuration when none is given). The command SHALL print, per configuration, the dataset-level metrics and the difference from the baseline, and per developer the metrics and the top 10 with their judgments. With a JSON output option it SHALL also write the full report to a file. It SHALL NOT change any stored data.

#### Scenario: Compare two stored versions
- **WHEN** the command runs with `v1-deterministic` and `v2-deterministic`
- **THEN** it prints both configurations' metrics with v2's difference from v1, and no stored row changes

#### Scenario: Unknown version
- **WHEN** a requested version does not exist
- **THEN** the command exits with an error and evaluates nothing

#### Scenario: Unsaved configuration
- **WHEN** a configuration is given as a JSON file that passes validation
- **THEN** it is evaluated without being stored

### Requirement: Improvement rule
A configuration SHALL count as an improvement over the baseline only when its mean NDCG@10 is higher than the baseline's and none of its other dataset-level metrics is lower than the baseline's by more than a tolerance (default 0.01). When asked to require improvement, the command SHALL exit with a non-zero status unless every non-baseline configuration is an improvement, and SHALL name each metric that failed.

#### Scenario: Better NDCG, worse precision
- **WHEN** a candidate raises NDCG@10 but lowers Precision@5 by 0.05 with the default tolerance
- **THEN** it is not an improvement and the command, asked to require improvement, exits non-zero naming Precision@5

#### Scenario: Tie
- **WHEN** a candidate's NDCG@10 equals the baseline's
- **THEN** it is not an improvement

### Requirement: Regression baseline
The repository SHALL keep recorded dataset-level metrics of each seeded scoring configuration on `benchmark-v1`. The test suite SHALL recompute them and fail when any differs, naming the configuration and metric, so a change that moves the ranking fails until the recorded values are updated deliberately in the same change.

#### Scenario: Ranking change detected
- **WHEN** a code change alters a signal so that v2's NDCG@10 on `benchmark-v1` moves
- **THEN** the test suite fails, naming v2 and NDCG@10

### Requirement: Export a developer snapshot
A management command SHALL export one user's stored developer features and candidate pool (with eligible issues) into the dataset format, for a person to judge. It SHALL make no GitHub calls. The export SHALL contain no username, name, email, GitHub id, avatar or token; the developer identifier SHALL be given by the person exporting. Every candidate SHALL be left unjudged, and the export SHALL say that judgments must be added by hand. A user without an analyzed profile SHALL produce an error, not an empty export.

#### Scenario: Anonymized export
- **WHEN** a person exports a user's snapshot with identifier `dev-f`
- **THEN** the file holds that user's skills, interests, experience level and candidates under `dev-f`, no identifying field of the user, and no judgments

#### Scenario: Not analyzed
- **WHEN** the user has no developer profile
- **THEN** the command exits with an error and writes no file
