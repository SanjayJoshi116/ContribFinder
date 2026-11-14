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
Loading a dataset SHALL fail with a message naming the developer and field when: the format version is unknown; an identifier is duplicated; a value is outside its allowed range (confidence and strength 0..1, judgment 0..2, experience level and issue difficulty outside their choice sets); a skill, interest or issue technology is not in the current catalog; a judgment names a repository that is not in that developer's pool; an issue's update time is not an ISO 8601 time with a UTC offset; or a developer has no judgment of 1 or more. Evaluation SHALL NOT run on an invalid dataset.

#### Scenario: Update time without an offset
- **WHEN** an issue's `updated_at` is `2026-09-20T12:00:00`
- **THEN** loading fails naming the issue and the field, so issue order cannot depend on the machine's time zone

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

### Requirement: Improvement rule
A configuration SHALL count as an improvement over the baseline only when its mean NDCG@10 is higher than the baseline's and none of its other dataset-level metrics is lower than the baseline's by more than a tolerance (default 0.01). When asked to require improvement, the command SHALL exit with a non-zero status unless every non-baseline configuration is an improvement, and SHALL name each metric that failed.

#### Scenario: Better NDCG, worse precision
- **WHEN** a candidate raises NDCG@10 but lowers Precision@5 by 0.05 with the default tolerance
- **THEN** it is not an improvement and the command, asked to require improvement, exits non-zero naming Precision@5

#### Scenario: Tie
- **WHEN** a candidate's NDCG@10 equals the baseline's
- **THEN** it is not an improvement

### Requirement: Uncertainty of a comparison
For every configuration after the baseline, evaluation SHALL estimate the uncertainty of each metric's difference from the baseline with a paired bootstrap over developers: each resample draws as many developers as the dataset holds, with replacement, and takes the mean over the drawn developers of the candidate's value minus the baseline's value for the same developer, from unrounded per-developer values. The report SHALL give, per metric, the observed mean difference, the 2.5th and 97.5th percentiles of the resampled differences as a 95% interval, and the share of resamples whose difference is 0 or below, and SHALL mark a difference whose interval lies entirely above or entirely below 0 only when the dataset holds at least 6 developers, the fewest for which an exact two-sided sign test can reach 5%. With fewer developers no difference SHALL be marked, and the report SHALL give the developer count and say that there are too few developers to mark. The number of resamples (default 10,000) and the random seed (default fixed) SHALL be settable, and the same dataset, configurations, resample count and seed SHALL always give the same figures. A dataset with one developer SHALL report an interval of zero width at the observed difference, not marked. These figures SHALL NOT change the improvement verdict, the regression baseline or activation.

#### Scenario: Reproducible interval
- **WHEN** the same comparison is evaluated twice with the default resample count and seed
- **THEN** both reports give the same intervals and shares

#### Scenario: Noise is visible
- **WHEN** a candidate is better than the baseline for one of six developers and equal for the other five
- **THEN** its NDCG@10 interval includes 0 and the difference is not marked

#### Scenario: Consistent improvement
- **WHEN** a candidate's NDCG@10 is higher than the baseline's for every one of six developers
- **THEN** its interval lies above 0, the difference is marked, and the share of resamples not better is 0

#### Scenario: Too few developers to mark
- **WHEN** a candidate's NDCG@10 is higher than the baseline's for every one of four developers
- **THEN** its interval lies above 0, the difference is not marked, and the report says four developers are too few to mark

#### Scenario: Verdict unchanged
- **WHEN** a candidate meets the improvement rule but its NDCG@10 interval includes 0
- **THEN** it is still reported as an improvement, and `--require-improvement` succeeds

### Requirement: Feedback report
A management command SHALL report how users acted on recommendations, per scoring configuration
version, from the stored feedback events and their snapshots, without changing any stored data.
It SHALL group events by configuration version and by rank bucket (1–5, 6–10, 11–20, 21 and
below), and SHALL give per group the count of each action (every event) and the number of distinct users.
Saved, opened repository and opened issue SHALL count as positive actions; these and dismissed
SHALL count as decisive actions; viewed, unsaved and undismissed SHALL be counted but be neither.
Shares SHALL count outcomes, not events: each user, repository and configuration version SHALL
have at most one outcome, its latest decisive event that was not undone, where unsaved undoes the
latest save before it and undismissed the latest dismissal before it; the outcome SHALL be
positive or dismissed by that event's action and SHALL fall in that event's rank bucket and match
label. Per group the report SHALL give the positive share, positive outcomes divided by decisive
outcomes. Per configuration it SHALL give the raw positive share over all its groups and a
position-adjusted share: the mean of its bucket shares weighted by the number of decisive
outcomes per bucket over all configurations in the report, using only the buckets where the
configuration has a share and renormalizing the weights over them, together with its coverage,
the part of the total weight those buckets carry; a configuration with no such
bucket SHALL have no adjusted share and no coverage. Per configuration the report SHALL also give one row per
match label (strong, good, partial) with the same counts, distinct users and positive share, not
adjusted for position, and a calibration verdict: `ordered` when the share of every label that
has one is at least the share of every lower label that has one, `not ordered` naming the first
higher label whose share is below a lower label's, or `not enough data` when fewer than two
labels have a share; a stored label outside these SHALL get its own row after them and SHALL NOT
enter the calibration verdict. A group with fewer decisive outcomes than a minimum
(configurable, default 10) SHALL show its counts but no share and SHALL be left out of the
adjusted share. Events without a configuration version or rank (a rank below 1 counts as none) SHALL be counted on their own
line and left out of every share; events without a match label SHALL be left out of the label
rows only. Per configuration it SHALL also count dismissals by reason (including those without one), and the dismissals without a configuration version or rank SHALL be counted by reason on their own line, a stored reason outside the current choices under its own value; reasons SHALL NOT change any share. The command SHALL accept a time window in days, the
configuration versions to include and a JSON output file. The report SHALL contain aggregates
only: no user, repository, recommendation or issue identifiers. It SHALL NOT change any ranking.

#### Scenario: Shares per configuration and bucket
- **WHEN** under `v2-deterministic` users saved 12 and dismissed 8 recommendations ranked 1 to 5
- **THEN** the report shows for `v2-deterministic`, ranks 1–5: 12 saved, 8 dismissed, the number of users, and a positive share of 0.60

#### Scenario: Position adjustment
- **WHEN** configuration A has 32 positive of 40 decisive actions at ranks 1–5 and 4 of 10 at ranks 6–10, and configuration B has 8 of 10 at ranks 1–5 and 16 of 40 at ranks 6–10
- **THEN** A's raw positive share is 0.72 and B's 0.48, and both have a position-adjusted share of 0.60 with coverage 1.00

#### Scenario: Partial coverage
- **WHEN** configuration A has a share only at ranks 1–5, which carry 50 of the report's 100 decisive outcomes
- **THEN** A's adjusted share equals its ranks 1–5 share and its coverage is 0.50

#### Scenario: Repeated and undone actions
- **WHEN** under `v2-deterministic` one user opened one recommended repository 6 times, dismissed two others, and saved then unsaved a fourth
- **THEN** the counts show 6 opened, 2 dismissed, 1 saved and 1 unsaved, and the positive share is 1 of 3 decisive outcomes

#### Scenario: Too few actions
- **WHEN** a group has 4 decisive actions and the minimum is 10
- **THEN** it shows its counts, no share, and does not enter the adjusted share

#### Scenario: Events without a recommendation snapshot
- **WHEN** some events have no configuration version or rank
- **THEN** they are counted on a separate line and enter no share

#### Scenario: Aggregates only
- **WHEN** the report is written as JSON
- **THEN** it contains no user, repository, recommendation or issue identifier, and no stored row changes

#### Scenario: Labels in order
- **WHEN** under `v2-deterministic` the positive shares are 0.70 for strong, 0.55 for good and 0.40 for partial recommendations
- **THEN** the report shows the three label rows and the calibration verdict `ordered`

#### Scenario: Labels out of order
- **WHEN** the shares are 0.45 for strong and 0.60 for good
- **THEN** the calibration verdict is `not ordered` and names strong below good

#### Scenario: One label with a share
- **WHEN** only strong recommendations reach the minimum number of decisive actions
- **THEN** the calibration verdict is `not enough data`

#### Scenario: Dismiss reasons per configuration
- **WHEN** under `v2-deterministic` users dismissed 6 recommendations as `inactive`, 3 as `not_my_stack` and 4 without a reason
- **THEN** the report shows those counts for `v2-deterministic`, and its shares are the same as if no reason had been given

#### Scenario: Reason no longer offered
- **WHEN** 2 stored dismissals carry a reason that is no longer one of the choices
- **THEN** the reasons line lists that value with 2 after the current reasons, so the reasons add up to the dismissals

### Requirement: Regression baseline
The repository SHALL keep recorded dataset-level metrics of each seeded scoring configuration on `benchmark-v1` and, once it exists, on `benchmark-v2`, each dataset with the top N its metrics were computed at. The test suite SHALL recompute them at each dataset's recorded top N and fail when any differs, naming the configuration and metric, so a change that moves the ranking fails until the recorded values are updated deliberately in the same change.

The evaluation command's baseline option SHALL write the recorded values, at the pinned minimum score default and top N unless a top N is given:
- Without a dataset option it SHALL rewrite every baseline dataset: `benchmark-v1`, each already recorded dataset whose file exists, and the selection benchmark. With a dataset option it SHALL rewrite only that dataset.
- It SHALL record stored configurations only (all of them unless versions are given). A configuration evaluated in the run SHALL replace its recorded entry; configurations recorded for the dataset but not evaluated SHALL keep theirs, and other datasets SHALL stay unchanged.
- A run at a top N different from the one recorded for a dataset SHALL cover every configuration recorded for it, otherwise the command SHALL fail before writing anything.
- It SHALL refuse a minimum score override, because the test recomputes each configuration at its own minimum score.
- It SHALL refuse, before evaluating, a dataset that is not the file named after the dataset in the evaluation data folder (`<name>.json`), because the test and the default rewrite find recorded datasets only there.
- It SHALL write the file whole or not at all; a failed write SHALL end the command with an error naming the file, not a traceback.

#### Scenario: Ranking change detected
- **WHEN** a code change alters a signal so that v2's NDCG@10 on `benchmark-v1` moves
- **THEN** the test suite fails, naming v2 and NDCG@10

#### Scenario: Baseline written with a selection benchmark present
- **WHEN** `benchmark-v2` holds a judged real developer and the baseline is written without a dataset option
- **THEN** the recorded values of both `benchmark-v1` and `benchmark-v2` are rewritten

#### Scenario: One configuration rewritten
- **WHEN** the baseline is written for `v2-deterministic` only
- **THEN** v2's recorded metrics are replaced and v1's recorded metrics stay in the file unchanged

#### Scenario: Different top N for part of a dataset
- **WHEN** the baseline is written at top N 20 for one configuration of a dataset recorded at top N 50 with two configurations
- **THEN** the command fails and the file is unchanged

#### Scenario: Minimum score override refused
- **WHEN** the baseline is written with a minimum score override
- **THEN** the command fails and the file is unchanged

#### Scenario: Dataset outside the evaluation folder
- **WHEN** the baseline is written with a dataset option pointing to a judged export in `judging/`
- **THEN** the command fails naming the expected file, evaluates nothing and the file is unchanged

### Requirement: Export a developer snapshot
A management command SHALL export one user's stored developer features and candidate pool (with eligible issues) into the dataset format, for a person to judge. The exported pool SHALL be the candidates a generation would score, including repositories whose stored data is stale, plus the candidates the user dismissed, so the export does not depend on when the staleness sweep last ran. It SHALL make no GitHub calls. The export SHALL contain no username, name, email, GitHub id, avatar or token; the developer identifier SHALL be given by the person exporting. By default it SHALL also leave out every candidate the user interacted with (a repository they contributed to or that entered the pool as previously interacted with), because the set of those repositories identifies the person; an explicit option SHALL include them for private use. Every candidate SHALL be left unjudged, and the export SHALL say that judgments must be added by hand. A user without an analyzed profile SHALL produce an error, not an empty export.

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

#### Scenario: Stale and dismissed candidates exported
- **WHEN** the user's pool holds an eligible repository marked stale and a repository they dismissed
- **THEN** both are in the file

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

### Requirement: Activating a configuration
An operator SHALL activate a stored scoring configuration only through a management command that
takes its version; activation SHALL never run inside a web request. The admin SHALL NOT offer an
activation action: the page of a stored configuration SHALL show the command that activates it,
or that it is already active, and SHALL NOT let the operator change which configuration is
active. Activation SHALL first validate the configuration as stored configurations are
validated; an unknown version or invalid configuration SHALL be refused with an error and change
nothing. Unless forced, it SHALL evaluate the configuration against the active one on the
selection benchmark with the pinned baseline minimum score and top N (never local settings), and
SHALL refuse it when it is not an improvement under the improvement rule, naming each failed
metric and changing nothing. Forcing SHALL require a non-empty reason. When the comparison
cannot run (unusable benchmark, invalid active configuration), an unforced activation SHALL fail
with an error and a forced one SHALL proceed, recording that it was not compared. An activation
SHALL be recorded as forced only when the improvement rule was not met or not evaluated. When
the active configuration changes between the comparison and the switch, or the configuration
being activated no longer exists at the switch, the activation SHALL fail and change nothing. A successful activation SHALL deactivate the previous configuration and
activate the new one in one step, so that exactly one configuration is active at every moment,
and SHALL record an audit event with the new and previous versions, whether it was forced, the
reason and any failed metrics. Activating the configuration that is already active SHALL change
nothing, record nothing and report that it is already active. The acceptance holdout check (see
"Replacing the active configuration") SHALL remain the operator's step before activation; the
command SHALL NOT read a holdout.

#### Scenario: Activation refused by the benchmark
- **WHEN** `v2-deterministic` is active and an operator activates `v1-deterministic` without forcing
- **THEN** the command fails naming the metrics where `v1-deterministic` is not an improvement, and `v2-deterministic` stays the only active configuration

#### Scenario: Forced rollback with a reason
- **WHEN** an operator forces the activation of `v1-deterministic` with the reason "rollback after incident"
- **THEN** `v1-deterministic` is the only active configuration, and an audit event records `v1-deterministic`, `v2-deterministic` as the previous version, that it was forced, the reason and the failed metrics

#### Scenario: Forced without a reason
- **WHEN** an operator forces an activation and gives no reason
- **THEN** the command fails before evaluating, and nothing changes

#### Scenario: Improvement activated
- **WHEN** an operator activates a stored configuration that is an improvement over the active one on the selection benchmark
- **THEN** it becomes the only active configuration and an audit event records it as not forced

#### Scenario: Unknown version
- **WHEN** an operator activates `v9-missing`
- **THEN** the command fails with an error naming the version, and nothing changes

#### Scenario: Already active
- **WHEN** an operator activates the configuration that is already active
- **THEN** the command reports that it is already active, and no audit event is recorded

#### Scenario: Admin shows the command
- **WHEN** an administrator opens the admin page of the stored configuration `v1-deterministic` while `v2-deterministic` is active
- **THEN** the page shows `npm run manage -- activate_scoring_config v1-deterministic`, offers no activation action, and no benchmark comparison runs

#### Scenario: Configuration removed before the switch
- **WHEN** the configuration being activated is deleted after it was judged and before the switch
- **THEN** the activation fails with an error, the previously active configuration stays the only active one, and no audit event is recorded

### Requirement: Blind judging sheet
A management command SHALL turn an exported developer snapshot into a judging sheet (CSV) with one row per candidate: repository full name, link, description, main languages with their share, topics, contribution files present, activity label, number of eligible open issues, an empty grade column and an empty note column, preceded by a grading guide (0 not relevant, 1 relevant, 2 highly relevant; blank = not judged). Rows SHALL be in alphabetical order of repository name. A language without a byte count SHALL count as zero for the shares; when no language of a repository has a byte count, its languages SHALL be listed by name without shares. The sheet SHALL NOT contain any score, signal value, rank, match label or reason computed by any scoring configuration, and SHALL NOT contain identifying data of the developer. A text cell starting with `=`, `+`, `-`, `@`, a tab or a carriage return SHALL be written with a leading `'`, so a spreadsheet shows repository text instead of evaluating it. An export whose catalog is not an object or lacks a candidate SHALL fail naming the repository, with no traceback and no file written.

#### Scenario: Description that looks like a formula
- **WHEN** a candidate's description is `=HYPERLINK("https://example.com")`
- **THEN** its cell is `'=HYPERLINK("https://example.com")`, and importing the graded sheet reads the grades as usual

#### Scenario: Candidate missing from the catalog
- **WHEN** an export lists a candidate that its repositories do not describe
- **THEN** writing the sheet fails naming that repository

#### Scenario: Blind sheet
- **WHEN** a sheet is written for an export with 30 candidates
- **THEN** it has 30 rows in alphabetical order with the listed facts and empty grades, and no score, rank, match label or reason

#### Scenario: Missing byte counts
- **WHEN** an export lists a repository's languages without byte counts
- **THEN** the sheet is written and that row names the languages without shares

### Requirement: Importing judgments
A management command SHALL read a filled judging sheet back into its export. Guide lines SHALL be recognized only before the header row; any later line, including a line inside a quoted multi-line field, SHALL be read as sheet content. A row whose cells are all blank SHALL be ignored. A grade SHALL be 0, 1, 2 or blank; blank rows SHALL stay unjudged. The import SHALL fail, naming the row, for an unknown repository, a repository listed more than once, a row with a grade but no repository, or an invalid grade, and SHALL fail when no row is graded 1 or 2. A successful import SHALL produce an export that passes dataset validation, with its developer marked `real` and its description stating that the developer was judged blind from a sheet, in place of the export's request to add judgments.

#### Scenario: Valid sheet
- **WHEN** a sheet grades 12 of 30 rows, three of them 2
- **THEN** the export holds those 12 judgments, the other 18 candidates stay unjudged, the developer kind is `real`, and the description no longer asks for judgments

#### Scenario: Invalid grade
- **WHEN** a row's grade is `3` or `yes`
- **THEN** the import fails naming that repository, and the export is unchanged

#### Scenario: Hash line inside a description
- **WHEN** a quoted description spans two lines and the second starts with `#`
- **THEN** the row keeps its full description and its grade is imported

#### Scenario: Blank rows saved by a spreadsheet
- **WHEN** the sheet ends with rows whose cells are all empty
- **THEN** those rows are ignored and the import succeeds

#### Scenario: Repeated repository
- **WHEN** the same repository appears in two rows
- **THEN** the import fails naming that repository, and the export is unchanged

### Requirement: Benchmark with real developers
A management command SHALL build a dataset from several datasets and judged exports: developers are concatenated (identifiers must be unique, otherwise the build fails naming them); repository catalogs are merged, identical entries once, and the build SHALL fail naming the repository when two entries with the same name differ, unless the person building chooses which source wins. An input that is not a dataset object, whose format version differs from the current one, whose repositories are not an object or whose developers are not a list of objects SHALL fail the build naming that input, with no traceback and no file written. A repository resolved by choosing a source SHALL be reported once. `benchmark-v2` SHALL be built from `benchmark-v1` and at least one judged real developer; until one is judged it does not exist and `benchmark-v1` remains the selection benchmark. Real developers SHALL be exported only from accounts whose owner agreed. Committing `benchmark-v2` SHALL be a deliberate decision of the person who judged, since it holds real public repository names and anonymized skill profiles.

#### Scenario: Build
- **WHEN** `benchmark-v1` and two judged exports with distinct identifiers are built
- **THEN** the result validates, holds the six personas and two real developers, and merges the repository catalogs

#### Scenario: Conflicting repository
- **WHEN** two exports describe the same repository with different data and no source is chosen
- **THEN** the build fails naming the repository

#### Scenario: Input is not a dataset
- **WHEN** one input file holds a JSON list (for example an evaluation report)
- **THEN** the build fails naming that input and writes no file

### Requirement: Persona and real subsets
Evaluation reports SHALL show, besides the dataset-level means, the means over persona developers and over real developers separately whenever a dataset contains both kinds.

#### Scenario: Mixed dataset
- **WHEN** `benchmark-v2` is evaluated
- **THEN** the report shows the means over all developers, over the six personas and over the real developers
