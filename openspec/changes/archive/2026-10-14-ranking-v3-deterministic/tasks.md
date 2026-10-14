## 1. Holdout first (spec: recommendation-evaluation "Holdout benchmark"; design D6)

- [x] 1.1 Write `apps/backend/evaluation/holdout-v1.json`: four personas (Java/Spring backend, Python ML engineer, beginner Python, Vue/Svelte developer whose best match is a quiet Vue library) with judgments, before any candidate is evaluated
- [x] 1.2 Test: `holdout-v1` validates, ≥ 4 developers, includes a beginner, no developer id shared with `benchmark-v1`

## 2. Mechanisms (spec: recommendation-engine "Relevance signals", "Recommendation score and ranking", "Versioned scoring configuration"; design D1–D3)

- [x] 2.1 `match_issues`: `difficulty_fit_mode` (`best` default, `weighted`), evidence gains `mode` and `mean`
- [x] 2.2 `score.py`: `OFFER_SIGNALS`, `contributions(signals, weights, params)` with relevance scaling; `weighted_score` sums it; `explain.reasons` takes contributions; update callers
- [x] 2.3 `config.validate`: accept and check `issues.difficulty_fit_mode` and `relevance_scaling`
- [x] 2.4 Tests: spec scenarios for weighted mode (one weak issue → 0.2; mixed → 0.24) and relevance scaling; absent parameters reproduce v2 exactly; reason weights equal scaled contributions and order follows them; validation rejects `average` and non-boolean scaling; baseline test still passes unchanged (v1, v2 bit-for-bit)

## 3. Candidate search (spec: recommendation-evaluation "Replacing the active configuration"; design D4)

- [x] 3.1 Generate the 15 candidate JSON files in `openspec/changes/ranking-v3-deterministic/candidates/` from the D4 table
- [x] 3.2 Evaluate all candidates on `benchmark-v1` against v1 and v2 (`--json`); apply the selection steps; write the full table and the choice to `candidates/RESULTS.md` before any holdout run
- [x] 3.3 Evaluate the chosen candidate on `holdout-v1` against v2; record accept/reject. If rejected or if no candidate qualified: stop here, record the outcome in RESULTS.md, skip groups 4–5 and report
- [x] 3.4 Evaluate the other candidates on `holdout-v1` for the record; add to RESULTS.md

## 4. Rescope after no candidate qualified (outcome in candidates/RESULTS.md)

- [x] 4.1 Update artifacts: proposal and design record the outcome; recommendation-engine delta no longer seeds v3 (v2 stays active, optional parameters documented, replacement rule referenced); D5 and D7 not carried out

## 5. Verification, docs and release

- [x] 5.1 Backend checks: `uv run pytest`, `ruff check`, `ruff format --check`, `mypy`; schema export has no drift
- [x] 5.2 Manual: `evaluate_ranking --dataset evaluation/holdout-v1.json` runs; a candidate file with both options evaluates through `--config-file`; local recommendations unchanged (still v2)
- [x] 5.3 Docs: README (holdout, optional parameters, replacement rule), CLAUDE.md (holdout in layout, mechanisms, follow-up)
- [x] 5.4 Release housekeeping per CLAUDE.md §8 at archive time (v0.9.0): versions and lockfiles, CHANGELOG (no ranking change; candidates tried and why none qualified), features.txt, README status, CLAUDE.md
