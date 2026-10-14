> **Outcome (rescoped after the candidate search):** no candidate qualified on `benchmark-v1`;
> every one scored exactly like its relevance-scaled base from the v3 search, so the minimum
> score was not the binding constraint (the repositories lost under scaling have a relevance part
> near 0.008). No `v3-deterministic` is seeded; v2 stays active. Both holdouts favor the
> candidates, which points at `benchmark-v1`'s judgments, a separate follow-up. The change ships
> the configuration minimum score, the evaluation override, baseline format 2 and `holdout-v2`.
> See `candidates/RESULTS.md`.

## Why

The v3 search (`ranking-v3-deterministic`, v0.9.0) found that relevance scaling fixes v2's precision problem (off-topic repositories with open issues in the top 5) but collides with the global `RECOMMENDATION_MIN_SCORE` (0.10). Scaling lowers the scores of weak but relevant repositories, the fixed cut then removes them, and Recall@10 falls (dev-beginner 1.000 → 0.667). The cut is an environment setting, not part of the versioned configuration, so the search could not vary it, and a configuration's ranking even depends on the installation's `.env`. This change makes the minimum score part of the scoring configuration and re-runs the scaled candidates with it.

This hypothesis was formed after seeing the `benchmark-v1` and `holdout-v1` results. `holdout-v1` is no longer unseen: every v3 candidate's numbers on it were recorded. A fresh holdout is needed for an honest acceptance check.

## What Changes

- **Minimum score in the configuration**: a configuration may set `params.min_score` (0..1) and `params.min_score_basis`: `score` (the whole weighted score, today's behavior) or `relevance` (only the contributions of the skill, language, framework and interest signals, which relevance scaling does not change). A configuration that sets neither keeps using `RECOMMENDATION_MIN_SCORE` on the score, so v1 and v2 rank exactly as before. Generation and evaluation read it the same way.
- **Fresh holdout `holdout-v2`**: four new persona developers, judged before any candidate of this change runs. The rule is generalized: a holdout whose results for a change's candidates were looked at cannot be the acceptance set of a later change. `holdout-v1` stays for reporting.
- **Predeclared search**: the 8 relevance-scaled candidates from the v3 search (difficulty fit mode × 4 weight vectors), each with two minimum-score variants: `score` basis at 0.05 and `relevance` basis at 0.10. That is 16 candidates, all recorded. Selection and acceptance follow the existing rule, with `holdout-v2` as the acceptance set.
- **`v3-deterministic`, only if one qualifies**: seeded by migration and made active, with bands recalibrated to v2's label distribution (as designed in `ranking-v3-deterministic`). If none qualifies, nothing is activated and the result is recorded.

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
- `recommendation-engine`: the minimum score and its basis can come from the configuration (no stored configuration sets them).
- `recommendation-evaluation`: evaluation uses the configuration's minimum score; a used holdout cannot accept a later change's configuration; `holdout-v2` becomes the acceptance set.

## Impact

- **Backend**: `services/ranking/score.py` (`rank` cut on score or relevance part), `services/ranking/pipeline.py` and `service.py` (minimum score from the configuration, settings as fallback), `services/ranking/config.py` (validation), `services/evaluation/runner.py` and `evaluate_ranking` (`--min-score` becomes an explicit override; configurations with their own value use it), `apps/backend/evaluation/holdout-v2.json`, `baselines.json` in format 2 (v1/v2 values unchanged).
- **Ranking**: unchanged for users (v2 stays active). No migration, API, model schema or frontend change.
- **Tests**: cut basis and precedence, v1/v2 unchanged (regression baseline), holdout validity, seeding (if any).
