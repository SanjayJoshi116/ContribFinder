## 1. Shared ranking stage (spec: recommendation-evaluation "Evaluation ranks as generation does"; design D1)

- [x] 1.1 Add `services/ranking/pipeline.py` with `rank_pool(dev, candidates, weights, params, issues_for, *, min_score, top_n)`: technologies → signals → `issues_for` once for gated candidates → `match_issues` → `score_candidate` → `rank`
- [x] 1.2 Switch `RecommendationService.run` to `rank_pool` (issues via `load_issues(ids, now, ISSUE_MAX_AGE_DAYS)`); remove `_score`; `_persist` unchanged
- [x] 1.3 Tests: existing generation tests pass unchanged; `issues_for` is called once and only with gated ids; parity test (generation on database rows vs `rank_pool` on the loaded features: same order and scores)

## 2. Metrics (spec: "Ranking metrics"; design D4)

- [x] 2.1 `services/evaluation/metrics.py`: `precision_at`, `recall_at`, `reciprocal_rank`, `ndcg_at` (gain `2^g - 1`, ideal from all judgments), unjudged count in top k, `DeveloperMetrics`, dataset mean
- [x] 2.2 Unit tests against hand-computed values: spec scenarios (B, C, A example; short list), no relevant result in the list, relevant item cut by the gate lowers NDCG and recall, all-perfect ranking gives 1.0

## 3. Dataset (spec: "Benchmark dataset", "Dataset validation"; design D2, D3)

- [x] 3.1 `services/evaluation/dataset.py`: load JSON format 1, validate (collect every error with developer and field), assign ids, convert to `DeveloperFeatures` / `RepoData` / `IssueFeature` with names from the catalog
- [x] 3.2 Tests: valid minimal dataset converts correctly; each validation failure from the spec (unknown format, duplicate id, out-of-range values, unknown experience level/difficulty, unknown skill/interest/issue technology slug, judgment outside the pool, no relevant judgment); unjudged candidates allowed

## 4. Runner and comparison (spec: "Evaluation command", "Improvement rule"; design D3, D5)

- [x] 4.1 `services/evaluation/runner.py`: `ConfigSpec` from a stored row or a JSON file (validated with `stored=True`), `evaluate(dataset, spec, min_score, top_n) -> Report` (per developer ranked top 10 with judgments, metrics; dataset means), `compare(reports, tolerance)` with the improvement rule
- [x] 4.2 Tests: determinism (two runs identical); improvement rule cases (better, tie, better NDCG with precision drop beyond tolerance, drop within tolerance); report JSON shape

## 5. Commands (spec: "Evaluation command", "Export a developer snapshot"; design D5)

- [x] 5.1 `recommendations/management/commands/evaluate_ranking.py`: `--config`, `--config-file`, `--dataset`, `--json`, `--require-improvement`, `--tolerance`, `--min-score`, `--top-n`, `--write-baseline`; table output with deltas and per-developer top 10; `CommandError` on unknown version or invalid config before evaluating
- [x] 5.2 `services/evaluation/export.py` and `recommendations/management/commands/export_benchmark_developer.py` (`--user-id`, `--as`, `--out`): features, candidates and eligible issues, no identifying fields, no judgments, error when not analyzed
- [x] 5.3 Tests: compare v1 and v2 prints both with deltas and changes no rows; unknown version and invalid file exit non-zero; `--require-improvement` exit codes; `--json` file written; export contains no username/email/GitHub id/token, uses the given id, has empty judgments, and loads with the dataset validator once judgments are added; not-analyzed user errors without writing a file

## 6. Seed dataset and baseline (spec: "Seed benchmark", "Regression baseline"; design D6, D7)

- [x] 6.1 Write `apps/backend/evaluation/benchmark-v1.json`: six personas (Django backend, React/TS frontend, Rust systems, data engineer, Go infrastructure, beginner JS) over ~36 fictional `bench/` repositories with issues; judgments written from the persona descriptions before any evaluation run
- [x] 6.2 Run `evaluate_ranking --config v1-deterministic --config v2-deterministic` and review the per-developer top 10s for dataset mistakes (not for tuning); fix data errors only
- [x] 6.3 Generate `apps/backend/evaluation/baselines.json` with `--write-baseline` (pinned `min_score` 0.10, `top_n` 50)
- [x] 6.4 Tests: `benchmark-v1` validates with ≥ 5 developers and ≥ 30 repositories; baseline regression test recomputes v1 and v2 and fails naming config and metric on any difference

## 7. Verification, docs and release

- [x] 7.1 Backend checks pass: `uv run pytest`, `ruff check`, `ruff format --check`, `mypy`; `npm run api:sync` shows no schema drift
- [x] 7.2 Manual: `npm run manage -- evaluate_ranking --config v1-deterministic --config v2-deterministic`; export a local real developer with `export_benchmark_developer` and confirm the file is anonymized (not committed)
- [x] 7.3 Docs: README section on evaluating a ranking change (commands, improvement rule, updating the baseline); CLAUDE.md §4 layout (`services/evaluation/`, `apps/backend/evaluation/`) and §6 commands
- [x] 7.4 Release housekeeping per CLAUDE.md §8 at archive time (v0.8.0): versions and lockfiles, CHANGELOG (v1 vs v2 benchmark numbers recorded), features.txt (Phase 8b), README status, CLAUDE.md (Phase 8b shipped, deviations, carry-overs)
