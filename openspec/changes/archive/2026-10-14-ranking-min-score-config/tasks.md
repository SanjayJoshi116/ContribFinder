## 1. Fresh holdout first (spec: recommendation-evaluation "Holdout benchmark"; design D5)

- [x] 1.1 Write `apps/backend/evaluation/holdout-v2.json` (C#/.NET intermediate, PHP/Laravel beginner, D3 data-viz experienced, Ansible DevOps intermediate with a quiet best match; weak-but-relevant candidates near the cut and busy off-topic ones), judged from persona descriptions; record its SHA-256 in `candidates/RESULTS.md` before any candidate runs
- [x] 1.2 Test: `holdout-v2` validates, ≥ 4 developers, includes a beginner, no id shared with `benchmark-v1` or `holdout-v1`

## 2. Minimum score in the configuration (spec: recommendation-engine "Recommendation score and ranking", "Versioned scoring configuration"; design D1, D3)

- [x] 2.1 `Scored.relevance` from `contributions`; `rank(..., basis)` cuts on score or relevance; `rank_pool` resolves `min_score` / `min_score_basis` from params with the passed value as default
- [x] 2.2 `config.validate`: `min_score` in 0..1; `min_score_basis` in {score, relevance} and only with `min_score`
- [x] 2.3 Tests: spec scenarios (configuration minimum wins; relevance basis keeps/drops; no configuration minimum = installation value on score); validation errors; generation uses the configuration's minimum; regression baseline unchanged for v1/v2

## 3. Evaluation (spec: recommendation-evaluation "Evaluation ranks as generation does"; design D2)

- [x] 3.1 `evaluate(..., override=False)`; `Report` carries effective `min_score` and `min_score_basis`; `evaluate_ranking --min-score` sets the override and the output says so
- [x] 3.2 `baselines.json` format 2 (per-config effective values); `--write-baseline` writes it; baseline test reads format 1 and 2; regenerate (values for v1/v2 unchanged)
- [x] 3.3 Tests: a configuration's own minimum is used by default; override replaces it for every configuration and is reported; report JSON shape

## 4. Candidate search (spec: recommendation-evaluation "Replacing the active configuration"; design D4)

- [x] 4.1 Generate `m01`–`m16` in `openspec/changes/ranking-min-score-config/candidates/` from the eight scaled v3 candidates × {S05, R10}; adapt `search.py` (acceptance `holdout-v2`, `holdout-v1` for the record)
- [x] 4.2 Evaluate on `benchmark-v1` against v1 and v2; apply selection; write the table and the choice to `RESULTS.md` before any holdout run
- [x] 4.3 Evaluate the chosen candidate on `holdout-v2` against v2; record accept/reject. If rejected or none qualified: record, skip group 5, rescope artifacts (no v3), continue with group 6
- [x] 4.4 Evaluate all candidates on `holdout-v2` and `holdout-v1` for the record; add to `RESULTS.md`

## 5. Rescope after no candidate qualified (outcome in candidates/RESULTS.md)

- [x] 5.1 Update artifacts: proposal and design record the outcome; recommendation-engine delta no longer seeds v3; recommendation-evaluation names `holdout-v3` for the next search; D6 not carried out

## 6. Verification, docs and release

- [x] 6.1 Backend checks: `uv run pytest`, `ruff check`, `ruff format --check`, `mypy`; schema export has no drift
- [x] 6.2 Manual: `evaluate_ranking` on all three datasets; a candidate with its own `min_score` and `--min-score` override both reported; local recommendations unchanged (v2)
- [x] 6.3 Docs: README (minimum score in configuration, `--min-score` as override, holdout-v2, next holdout), CLAUDE.md (layout, holdout rule)
- [x] 6.4 Release housekeeping per CLAUDE.md §8 at archive time (v0.10.0): versions and lockfiles, CHANGELOG (no ranking change; outcome, diagnosis and all candidates), features.txt, README status, CLAUDE.md
