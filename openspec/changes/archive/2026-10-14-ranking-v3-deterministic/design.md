> **Outcome:** D1–D4 and D6 were implemented. No candidate qualified in D4, so D5 (band
> recalibration) and D7 (seeding v3) were not carried out; see `candidates/RESULTS.md`.

## Context

See proposal.md (Why). Current state that shapes the approach:

- `match_issues` (`services/matching/issues.py`) returns `issue_fit` (sum of kept issue scores / `saturation`, capped at 1) and `difficulty_fit` (best `difficulty_fit` table value among kept issues with known difficulty). Its parameters are the configuration's `params.issues` block.
- `weighted_score(signals, weights)` (`services/ranking/score.py`) is a plain weighted sum; `explain.reasons(signals, weights)` sets each reason's weight to `weights[name] * value` and orders reasons by it. Both are called from `score_candidate` / `RecommendationService._persist`.
- `config.validate(weights, params, stored=...)` checks a fixed key set per block; unknown extra keys are currently ignored.
- `freshness` already regenerates when the active configuration changes. v2 was activated by data migration `0003_seed_v2_deterministic` with a frozen copy of its values.
- `evaluate_ranking --config-file` evaluates unsaved configurations; `baselines.json` pins v1 and v2 on `benchmark-v1` and a test recomputes them.
- Per-signal diagnosis on `benchmark-v1` (scratch run, recorded in proposal.md) identified the two mechanisms this change addresses.

## Goals / Non-Goals

**Goals:**
- Both mechanisms are configuration parameters, so v1 and v2 score bit-for-bit as before (the baseline test proves it) and the choice is made by evaluation, not by code.
- The search is small, predeclared and fully recorded, with a holdout that is never used to choose.

**Non-Goals:**
- Changing issue scoring, relevance gate, technology detection or any signal other than difficulty fit.
- Per-user or feedback-based weights.
- Changing `benchmark-v1` judgments. Mistakes found in it are reported, not fixed here: fixing them while tuning would move the goalposts.
- Optimizing weights numerically (grid search over continuous weights). Four hand-chosen vectors keep overfitting risk low on six developers.

## Decisions

### D1. Difficulty fit mode
`params.issues.difficulty_fit_mode ∈ {"best", "weighted"}`, absent = `"best"`. In `weighted`:

```
known = kept issues with difficulty ≠ unknown
value = (Σ table[d_i] · score_i / Σ score_i) · issue_fit.value      (0 when known is empty)
```

Evidence keeps v2's shape (`best`, `count`, `by_difficulty`) plus `mode` and `mean`, so the difficulty reason text ("Some issues look beginner-level (estimated)") is unchanged: it names the best-fitting level, which is still true.
- Why multiply by issue fit: difficulty fit then measures "fitting issues available", not "a fitting issue exists". Alternative: saturate on the count of fitting issues. Rejected: a second saturation parameter, and issue fit already encodes count and quality.

### D2. Relevance scaling
`params.relevance_scaling: bool`, absent = `false`. New pure function in `score.py`:

```python
OFFER_SIGNALS = ("activity", "openness", "issue_fit", "difficulty_fit")

def contributions(signals, weights, params) -> dict[str, float]:
    plain = {name: weights.get(name, 0.0) * s.value for name, s in signals.items()}
    if not params.get("relevance_scaling"):
        return plain
    rel_w = sum(weights.get(n, 0.0) for n in RELEVANCE_SIGNALS)
    strength = sum(plain[n] for n in RELEVANCE_SIGNALS) / rel_w if rel_w else 0.0
    return {n: v * strength if n in OFFER_SIGNALS else v for n, v in plain.items()}
```

`weighted_score` sums `contributions`; `explain.reasons` takes the contributions instead of recomputing `weights * value`, so reason weights and order always match the score. `score_candidate` already receives `params`.
- Why multiplicative rather than a gate threshold: no new cut-off to tune, and it degrades smoothly.
- Score range stays within 0..1 (strength ≤ 1), but scores are lower on average, which is why bands are recalibrated (D5).

### D3. Validation
`validate` accepts the two optional keys and rejects unknown values (`difficulty_fit_mode` not in the set, `relevance_scaling` not a boolean). Stored v1/v2 rows lack them and stay valid.

### D4. Predeclared candidates and selection
Weight vectors (each sums to 1):

| id | skill | language | interest | framework | activity | openness | issue_fit | difficulty_fit |
|---|---|---|---|---|---|---|---|---|
| W2 (v2) | .35 | .15 | .15 | .10 | .10 | .05 | .05 | .05 |
| WR (relevance-first) | .40 | .20 | .15 | .10 | .05 | .00 | .05 | .05 |
| WB (balanced) | .35 | .20 | .15 | .10 | .05 | .05 | .05 | .05 |
| WI (issue-heavy) | .30 | .15 | .15 | .10 | .10 | .05 | .10 | .05 |

Candidates: {difficulty mode best, weighted} × {scaling off, on} × {W2, WR, WB, WI}, minus the combination equal to v2: 15 configurations, written as JSON files under `openspec/changes/ranking-v3-deterministic/candidates/` (archived with the change) with v2's other params and bands.

Selection, in this order, all on `benchmark-v1`:
1. Keep candidates that are an improvement over v1 **and** v2 (`evaluate_ranking --require-improvement` semantics).
2. Choose the highest NDCG@10; ties → higher Precision@5 → fewer mechanisms enabled → table order.
3. Only then evaluate the chosen one on `holdout-v1` against v2. If it regresses beyond the tolerance, stop: no v3 is seeded and the change records the result. The next-best candidate is **not** tried, because that would use the holdout to choose.

The choice (step 2) is written to `candidates/RESULTS.md` before any holdout run. After that, all 15 candidates are evaluated on `holdout-v1` too, for the record only, and their numbers are added to RESULTS.md, so the holdout cannot influence the choice. Numbers come from `evaluate_ranking --json` runs.

### D5. Band recalibration
Bands only change labels, never order or metrics. For the chosen candidate, pick `strong`/`good` from a 0.05-step grid (`good < strong`) minimizing the summed absolute difference between its and v2's Strong/Good/Partial shares across all developers' top 10 on both datasets. Tie → keep v2's bands if among the best, else the higher pair. A small script in the change folder does this from the JSON reports; the result is recorded in RESULTS.md.

### D6. Holdout `holdout-v1`
`apps/backend/evaluation/holdout-v1.json`, self-contained (own `repositories` block; may reuse benchmark repository entries verbatim plus about 12 new `bench/` repositories). Four personas: Java/Spring backend (intermediate), Python ML engineer (experienced), beginner Python scripter, and a Vue/Svelte frontend developer whose best match is a quiet, low-activity Vue library. Judgments are written and committed (task order) before any candidate runs. A test checks that it validates and has no identifier shared with `benchmark-v1`.

### D7. Seeding v3
Migration `0005_seed_v3_deterministic`: frozen copy of the chosen values; creates the row, deactivates the current active row and activates v3 (same pattern as 0003); reverse re-activates v2 and deletes v3 if unused. `V3_*` constants in `config.py` mirror it. `baselines.json` is regenerated with `--write-baseline`; its diff must show only v3 added.

## Risks / Trade-offs

- [Tuning on six synthetic personas] → small predeclared grid, holdout acceptance, all candidates recorded; the holdout is still written by the same author, which the CHANGELOG states.
- [Relevance scaling lowers scores, so fewer Strong labels] → D5 recalibrates bands against v2's label distribution.
- [The weighted mode lowers difficulty fit for repositories with a single good issue that really suits a beginner] → that is the intent: such repositories still get issue fit and the difficulty reason, just less score.
- [No candidate qualifies] → stated outcome: nothing activated, results recorded, follow-up change. The two mechanisms still ship as options.
- [Recommendations regenerate for every user when v3 activates] → same as the v2 rollout; the freshness sweep spreads it over its normal cycle.

## Migration Plan

Deploy runs migration 0005, which activates v3; the freshness sweep regenerates recommendations. Rollback: reverse the migration (v2 active again; the sweep regenerates under v2), or set v2 active in the admin.
