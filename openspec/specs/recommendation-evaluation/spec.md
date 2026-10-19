# recommendation-evaluation Specification

## Purpose

Measures recommendation quality offline against a fixed, hand-labeled benchmark of developers, so a change to signals, weights or ranking counts as an improvement only when it wins on the benchmark, and an unintended ranking change is caught before it ships.

## Requirements

### Requirement: Benchmark dataset
The system SHALL read benchmark datasets from versioned, checked-in files. A dataset SHALL have a name, a format version and a list of benchmark developers. Each developer SHALL have an identifier, a free-text description, a kind (`persona`, the default, or `real` for a judged export of a real developer), the matching inputs the ranking uses (skills with confidence, category and number of supporting repositories; interests with strength; internal experience level) and a candidate pool. Each candidate SHALL carry the repository data the ranking uses (full name, languages with bytes, topics, dependencies, contribution files and labels, activity snapshot, best search rank) and its eligible issues with their stored analysis (canonical labels, contribution type, difficulty, technologies). Each developer SHALL have relevance judgments by repository full name: `0` not relevant, `1` relevant, `2` highly relevant. A candidate without a judgment SHALL count as not relevant.

#### Scenario: Kind defaults to persona
- **WHEN** a developer entry has no kind
- **THEN** it is loaded as a persona

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
Evaluation SHALL rank each benchmark developer's pool with exactly the stages recommendation generation uses (repository technologies, signals, issue matching for candidates that pass the relevance gate, weighted score, relevance gate, minimum score, top-N cut and tie-breaking) and the same minimum score (the configuration's own when it sets one, otherwise the setting) and top-N setting. An explicit override of the minimum score or top N SHALL apply to every evaluated configuration and SHALL be shown in the report. Evaluation SHALL use no database data besides scoring configurations and SHALL make no GitHub, LLM or embedding calls. For the same dataset and configuration it SHALL produce the same ranking every time.

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
A management command SHALL evaluate one or more scoring configurations against a dataset (default: the selection benchmark, `benchmark-v2` once it exists with at least one judged real developer, otherwise `benchmark-v1`). A configuration SHALL be given as a stored version or as a JSON file holding weights and params; both SHALL pass the same validation as stored configurations, and an unknown version or invalid configuration SHALL stop the command with an error before any evaluation. The first configuration SHALL be the baseline (default: the active configuration when none is given). The command SHALL print, per configuration, the dataset-level metrics and the difference from the baseline, and per developer the metrics and the top 10 with their judgments. With a JSON output option it SHALL also write the full report to a file. It SHALL NOT change any stored data.

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
The repository SHALL keep recorded dataset-level metrics of each seeded scoring configuration on `benchmark-v1` and, once it exists, on `benchmark-v2`. The test suite SHALL recompute them and fail when any differs, naming the configuration and metric, so a change that moves the ranking fails until the recorded values are updated deliberately in the same change.

#### Scenario: Ranking change detected
- **WHEN** a code change alters a signal so that v2's NDCG@10 on `benchmark-v1` moves
- **THEN** the test suite fails, naming v2 and NDCG@10

### Requirement: Export a developer snapshot
A management command SHALL export one user's stored developer features and candidate pool (with eligible issues) into the dataset format, for a person to judge. It SHALL make no GitHub calls. The export SHALL contain no username, name, email, GitHub id, avatar or token; the developer identifier SHALL be given by the person exporting. By default it SHALL also leave out every candidate the user interacted with (a repository they contributed to or that entered the pool as previously interacted with), because the set of those repositories identifies the person; an explicit option SHALL include them for private use. Every candidate SHALL be left unjudged, and the export SHALL say that judgments must be added by hand. A user without an analyzed profile SHALL produce an error, not an empty export.

#### Scenario: Anonymized export
- **WHEN** a person exports a user's snapshot with identifier `dev-f`
- **THEN** the file holds that user's skills, interests, experience level and candidates under `dev-f`, no identifying field of the user, and no judgments

#### Scenario: Interacted repositories left out
- **WHEN** the user's pool holds a repository found through search and a repository they contributed to, and the snapshot is exported without the include option
- **THEN** the file holds the searched repository and not the contributed one, and the command reports how many candidates were left out

#### Scenario: Interacted repositories on request
- **WHEN** the same snapshot is exported with the include option
- **THEN** both repositories are in the file

#### Scenario: Not analyzed
- **WHEN** the user has no developer profile
- **THEN** the command exits with an error and writes no file

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
A new configuration SHALL replace the active one only when, under the improvement rule, it is an improvement over every stored configuration on the selection benchmark (`benchmark-v2` once it exists with at least one judged real developer, otherwise `benchmark-v1`), and on the current acceptance holdout (see "Holdout benchmark") none of its dataset-level metrics is lower than the active configuration's by more than the tolerance. Every candidate configuration evaluated while choosing it SHALL be recorded with its metrics on both datasets, including those not chosen. When no candidate qualifies, the active configuration SHALL stay active.

#### Scenario: Wins on benchmark, regresses on holdout
- **WHEN** a candidate is an improvement over v1 and v2 on `benchmark-v1` but its Recall@10 on the acceptance holdout is 0.05 below v2's
- **THEN** it does not replace v2

#### Scenario: No qualifying candidate
- **WHEN** no evaluated candidate meets the rule
- **THEN** the active configuration is unchanged and the recorded candidates show why each failed

### Requirement: Blind judging sheet
A management command SHALL turn an exported developer snapshot into a judging sheet (CSV) with one row per candidate: repository full name, link, description, main languages with their share, topics, contribution files present, activity label, number of eligible open issues, an empty grade column and an empty note column, preceded by a grading guide (0 not relevant, 1 relevant, 2 highly relevant; blank = not judged). Rows SHALL be in alphabetical order of repository name. The sheet SHALL NOT contain any score, signal value, rank, match label or reason computed by any scoring configuration, and SHALL NOT contain identifying data of the developer.

#### Scenario: Blind sheet
- **WHEN** a sheet is written for an export with 30 candidates
- **THEN** it has 30 rows in alphabetical order with the listed facts and empty grades, and no score, rank, match label or reason

### Requirement: Importing judgments
A management command SHALL read a filled judging sheet back into its export. A grade SHALL be 0, 1, 2 or blank; blank rows SHALL stay unjudged. The import SHALL fail, naming the row, for an unknown repository or an invalid grade, and SHALL fail when no row is graded 1 or 2. A successful import SHALL produce an export that passes dataset validation, with its developer marked `real`.

#### Scenario: Valid sheet
- **WHEN** a sheet grades 12 of 30 rows, three of them 2
- **THEN** the export holds those 12 judgments, the other 18 candidates stay unjudged, and the developer kind is `real`

#### Scenario: Invalid grade
- **WHEN** a row's grade is `3` or `yes`
- **THEN** the import fails naming that repository, and the export is unchanged

### Requirement: Benchmark with real developers
A management command SHALL build a dataset from several datasets and judged exports: developers are concatenated (identifiers must be unique, otherwise the build fails naming them); repository catalogs are merged, identical entries once, and the build SHALL fail naming the repository when two entries with the same name differ, unless the person building chooses which source wins. `benchmark-v2` SHALL be built from `benchmark-v1` and at least one judged real developer; until one is judged it does not exist and `benchmark-v1` remains the selection benchmark. Real developers SHALL be exported only from accounts whose owner agreed. Committing `benchmark-v2` SHALL be a deliberate decision of the person who judged, since it holds real public repository names and anonymized skill profiles.

#### Scenario: Build
- **WHEN** `benchmark-v1` and two judged exports with distinct identifiers are built
- **THEN** the result validates, holds the six personas and two real developers, and merges the repository catalogs

#### Scenario: Conflicting repository
- **WHEN** two exports describe the same repository with different data and no source is chosen
- **THEN** the build fails naming the repository

### Requirement: Persona and real subsets
Evaluation reports SHALL show, besides the dataset-level means, the means over persona developers and over real developers separately whenever a dataset contains both kinds.

#### Scenario: Mixed dataset
- **WHEN** `benchmark-v2` is evaluated
- **THEN** the report shows the means over all developers, over the six personas and over the real developers
