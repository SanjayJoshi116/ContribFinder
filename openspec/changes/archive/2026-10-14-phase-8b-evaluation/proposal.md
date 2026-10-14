## Why

ContribFinder ranks with versioned scoring configurations (`v1-deterministic`, now `v2-deterministic`), but nothing measures whether a new configuration ranks better than the one before: Phase 7 activated v2 on judgment alone. SRS-2 §30 and §61 (and SRS-1 §57) require a fixed evaluation dataset of developers with hand-labeled relevant repositories, scored with Precision@5, Precision@10, Recall@10, MRR and NDCG, and say a recommendation change counts as an improvement only if it wins there. This must exist before ranking grows more signals (Phase 6 semantic matching, feedback-based ranking), so it comes next.

## What Changes

- **Benchmark dataset**: a versioned, checked-in JSON dataset of benchmark developers. Each developer is a frozen snapshot of matching inputs (skills with confidence, category and repository count; interests with strength; internal experience level), a candidate pool of repositories (languages, topics, dependencies, contribution files and labels, activity snapshot, search rank, eligible issues with their analysis) and graded relevance judgments per repository (`0` not relevant, `1` relevant, `2` highly relevant). Unjudged candidates count as not relevant and are reported. The dataset is validated on load; a developer without at least one relevant judgment is rejected.
- **Seed dataset `benchmark-v1`**: persona developers (for example a Python/Django backend developer, a TypeScript/React frontend developer, a Rust systems developer, a data engineer, a beginner) over a shared catalog of fictional repositories, labeled by hand against each persona. It holds no GitHub user data.
- **Export from real data**: a management command `export_benchmark_developer` snapshots one developer's stored profile features and candidate pool into the dataset format, anonymized (no username, email or GitHub ids), with every judgment left empty for a person to fill in. It makes no GitHub calls.
- **Shared ranking stage**: the in-memory part of recommendation generation (technologies → signals → issue matching → score → rank) becomes one pure function that both generation and evaluation call, so evaluation measures exactly what users get, with the same `RECOMMENDATION_MIN_SCORE` and `RECOMMENDATIONS_TOP_N`. Generation behavior does not change.
- **Metrics**: Precision@5, Precision@10, Recall@10, MRR and NDCG@10 (graded gains) per developer and as the mean over developers, plus judgment coverage of the top 10.
- **Evaluation command**: `evaluate_ranking` scores one or more configurations (stored `ScoringConfig` versions and/or a JSON file for a configuration not yet stored, both validated like stored configs) against a dataset and prints a comparison table with per-developer detail and deltas against the first (baseline) configuration; `--json` writes a machine-readable report. With `--require-improvement` it exits non-zero unless every candidate configuration beats the baseline on NDCG@10 and regresses no other metric by more than a tolerance.
- **Regression baseline in CI**: a checked-in baseline file records the metrics of the stored configurations on `benchmark-v1`; a test recomputes them, so any change to signals, scoring or ranking that moves the numbers fails CI until the baseline is updated on purpose.
- No API, frontend, model or migration changes. No GitHub, LLM or embedding calls.

## Capabilities

### New Capabilities
- `recommendation-evaluation`: benchmark dataset format and validation, the seed dataset, export of a real developer snapshot, ranking metrics, the evaluation command and improvement rule, and the CI regression baseline.

### Modified Capabilities
<!-- None: generation keeps its behavior; it only calls the shared ranking stage. -->

## Impact

- **Backend**:
  - `services/ranking/`: new pure `pipeline` stage extracted from `RecommendationService._score` + `rank`; the service calls it with issues loaded from the database;
  - new `services/evaluation/`: `dataset` (load, validate, convert to `DeveloperFeatures` / `RepoData` / `IssueFeature`), `metrics` (pure), `runner` (rank each developer under each configuration, aggregate, compare), `export` (snapshot from the database);
  - new management commands `evaluate_ranking` and `export_benchmark_developer` (in `recommendations/management/commands/`);
  - new data directory `apps/backend/evaluation/` with `benchmark-v1.json` and `baselines.json`.
- **Tests**: metric unit tests against hand-computed values, dataset validation, pipeline parity with generation, export anonymization, command output and exit codes, and the baseline regression test.
- **Runtime**: none. Evaluation runs offline from the command line and in CI.
- **Privacy**: the seed dataset is fictional. Exports from real data drop identifying fields; the person exporting decides whether a snapshot is committed.
