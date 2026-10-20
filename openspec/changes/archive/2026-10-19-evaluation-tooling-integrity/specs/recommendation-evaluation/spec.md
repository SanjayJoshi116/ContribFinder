## MODIFIED Requirements

### Requirement: Evaluation command
A management command SHALL evaluate one or more scoring configurations against a dataset (default: the selection benchmark, `benchmark-v2` once it exists with at least one judged real developer, otherwise `benchmark-v1`). A configuration SHALL be given as a stored version or as a JSON file holding weights and params; both SHALL pass the same validation as stored configurations, and an unknown version or invalid configuration SHALL stop the command with an error before any evaluation. The first configuration SHALL be the baseline (default: the active configuration when none is given). The command SHALL print, per configuration, the dataset-level metrics and the difference from the baseline, and per developer the metrics and the top 10 with their judgments. With a JSON output option it SHALL also write the full report to a file, creating the file's folder when missing; a report that cannot be written SHALL end the command with an error naming the path, not a traceback. It SHALL NOT change any stored data.

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

### Requirement: Regression baseline
The repository SHALL keep recorded dataset-level metrics of each seeded scoring configuration on `benchmark-v1` and, once it exists, on `benchmark-v2`, each dataset with the top N its metrics were computed at. The test suite SHALL recompute them at each dataset's recorded top N and fail when any differs, naming the configuration and metric, so a change that moves the ranking fails until the recorded values are updated deliberately in the same change.

The evaluation command's baseline option SHALL write the recorded values, at the pinned minimum score default and top N unless a top N is given:
- Without a dataset option it SHALL rewrite every baseline dataset: `benchmark-v1`, each already recorded dataset whose file exists, and the selection benchmark. With a dataset option it SHALL rewrite only that dataset.
- It SHALL record stored configurations only (all of them unless versions are given). A configuration evaluated in the run SHALL replace its recorded entry; configurations recorded for the dataset but not evaluated SHALL keep theirs, and other datasets SHALL stay unchanged.
- A run at a top N different from the one recorded for a dataset SHALL cover every configuration recorded for it, otherwise the command SHALL fail before writing anything.
- It SHALL refuse a minimum score override, because the test recomputes each configuration at its own minimum score.

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

### Requirement: Blind judging sheet
A management command SHALL turn an exported developer snapshot into a judging sheet (CSV) with one row per candidate: repository full name, link, description, main languages with their share, topics, contribution files present, activity label, number of eligible open issues, an empty grade column and an empty note column, preceded by a grading guide (0 not relevant, 1 relevant, 2 highly relevant; blank = not judged). Rows SHALL be in alphabetical order of repository name. A language without a byte count SHALL count as zero for the shares; when no language of a repository has a byte count, its languages SHALL be listed by name without shares. The sheet SHALL NOT contain any score, signal value, rank, match label or reason computed by any scoring configuration, and SHALL NOT contain identifying data of the developer.

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
A management command SHALL build a dataset from several datasets and judged exports: developers are concatenated (identifiers must be unique, otherwise the build fails naming them); repository catalogs are merged, identical entries once, and the build SHALL fail naming the repository when two entries with the same name differ, unless the person building chooses which source wins. An input that is not a dataset object, or whose format version differs from the current one, SHALL fail the build naming that input, with no traceback and no file written. `benchmark-v2` SHALL be built from `benchmark-v1` and at least one judged real developer; until one is judged it does not exist and `benchmark-v1` remains the selection benchmark. Real developers SHALL be exported only from accounts whose owner agreed. Committing `benchmark-v2` SHALL be a deliberate decision of the person who judged, since it holds real public repository names and anonymized skill profiles.

#### Scenario: Build
- **WHEN** `benchmark-v1` and two judged exports with distinct identifiers are built
- **THEN** the result validates, holds the six personas and two real developers, and merges the repository catalogs

#### Scenario: Conflicting repository
- **WHEN** two exports describe the same repository with different data and no source is chosen
- **THEN** the build fails naming the repository

#### Scenario: Input is not a dataset
- **WHEN** one input file holds a JSON list (for example an evaluation report)
- **THEN** the build fails naming that input and writes no file
