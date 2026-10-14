> **Outcome:** D1–D5 were implemented; no candidate qualified in D4, so D6 (bands, seeding) was
> not carried out. See `candidates/RESULTS.md`.

## Context

See proposal.md (Why) and `openspec/changes/archive/2026-10-14-ranking-v3-deterministic/candidates/RESULTS.md`. Current state:

- `score.rank(scored, *, min_score, top_n)` keeps relevant candidates whose `score >= min_score`. `rank_pool(..., min_score, top_n)` passes it through. Generation passes `settings.RECOMMENDATION_MIN_SCORE`; evaluation passes `--min-score`, the setting, or the pinned `baseline.MIN_SCORE` (0.10).
- `score.contributions(signals, weights, params)` already separates relevance contributions (skill, language, framework, interest; never scaled) from offer contributions (scaled under `relevance_scaling`).
- `Report.min_score` / `top_n` are per report; `baselines.json` pins `min_score` 0.10 and `top_n` 50.
- The `ranking-v3-deterministic` design (D5 band recalibration, D7 seeding) was never carried out and is reused here if a candidate qualifies.

## Goals / Non-Goals

**Goals:**
- A configuration fully determines its ranking (with the top N still from settings): same configuration, same ranking, whatever the `.env` minimum.
- v1 and v2 unchanged bit-for-bit; the regression baseline proves it.
- An acceptance holdout nobody has seen results on.

**Non-Goals:**
- Moving `RECOMMENDATIONS_TOP_N` into the configuration (it is a product limit, not a relevance threshold).
- New signals, new weight vectors, or changing judgments of any dataset.
- Retiring `holdout-v1` (kept for reporting; its numbers stay comparable).

## Decisions

### D1. Where the cut happens
`Scored` gains `relevance: float`, the sum of the relevance contributions (computed in `score_candidate` from `contributions`). `rank(scored, *, min_score, top_n, basis="score")` compares `s.score` or `s.relevance` against `min_score`. `rank_pool` resolves the effective values:

```python
min_score = params.get("min_score", default_min_score)
basis = params.get("min_score_basis", "score")
```

so callers keep passing the installation value as the default.
- Why a basis option instead of only a lower number: the relevance part is unaffected by relevance scaling, so a cut on it keeps meaning "relevant enough" whatever the offer signals do. A lower whole-score cut is the simpler alternative; both are in the grid (D4) and the benchmark decides.

### D2. Overrides in evaluation
`evaluate(dataset, spec, *, min_score, top_n, override=False)`: without override, `min_score` is the default (a configuration's own value wins); with `--min-score` on the command line, the override replaces every configuration's value and the report says so. `Report.min_score` becomes the effective value for that configuration, plus `min_score_basis`. `--write-baseline` records each configuration's effective values, so `baselines.json` moves from one pinned `min_score` to per-config entries (format bump: `"format": 2`; the test reads both).

### D3. Validation
`min_score`: number in 0..1. `min_score_basis`: `score` or `relevance`; allowed only together with `min_score` (a basis without its own threshold would silently reinterpret the installation value).

### D4. Predeclared candidates
Base: the eight relevance-scaled candidates of the v3 search, unchanged (`c04–c07` best mode, `c12–c15` weighted mode; weights W2, WR, WB, WI). Each in two variants:

| variant | `min_score` | `min_score_basis` |
|---|---|---|
| S05 | 0.05 | score |
| R10 | 0.10 | relevance |

16 candidates `m01`–`m16`, JSON files under `candidates/` in this change, with `search.py` adapted from the v3 search (acceptance dataset `holdout-v2`; `holdout-v1` reported for the record).

Selection is unchanged: improvement over v1 and v2 on `benchmark-v1`, highest NDCG@10, ties → P@5 → fewer options set → id order. The choice is written to `RESULTS.md` before any holdout run. Acceptance: no metric on `holdout-v2` lower than v2's by more than 0.01. No second try on rejection.

### D5. Holdout `holdout-v2`
Self-contained file, four personas not in either dataset: C#/.NET backend (intermediate), PHP/Laravel beginner, D3/JavaScript data-visualization developer (experienced), Ansible/Python DevOps engineer (intermediate) whose best match is a quiet repository. Each pool deliberately includes weak-but-relevant candidates (thin skill overlap, judged 1) near the 0.10 cut, the pattern under test, plus busy off-topic candidates with open issues (judged 0). Judgments written and its SHA-256 recorded in `RESULTS.md` before any candidate runs.

### D6. If a candidate is accepted
Bands recalibrated to v2's label distribution (as in the v3 design D5: 0.05 grid, minimize summed share difference over all developers' top 10 on `benchmark-v1` and `holdout-v2`). Migration `0005_seed_v3_deterministic` (frozen copy, activate v3, reversible), `V3_*` constants, `baselines.json` regenerated (v1/v2 entries unchanged), and v3's values filled into the `recommendation-engine` delta.

## Risks / Trade-offs

- [`benchmark-v1` has now been used for two searches; selection may fit its six personas] → small predeclared grid; acceptance on an unseen holdout built to contain the failure pattern; all candidates recorded.
- [A lower whole-score cut (S05) shows users more weak matches] → they rank last and carry Partial labels; top N still caps the list.
- [Relevance basis (R10) may cut the weak matches the benchmark judged relevant] → that is a measurable outcome, not a defect; the grid includes S05 for that reason.
- [The holdout is written by the same author who saw the earlier results] → stated in CHANGELOG; judgments come from persona descriptions and are fixed by hash before any run.

## Migration Plan

Without a qualifying candidate: no migration, nothing changes for users. With one: migration 0005 activates v3 and the freshness sweep regenerates; rollback reverses the migration or re-activates v2 in the admin.
