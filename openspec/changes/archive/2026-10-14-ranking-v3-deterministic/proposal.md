> **Outcome (rescoped after the candidate search):** no candidate qualified, so no
> `v3-deterministic` is seeded and `v2-deterministic` stays active. The change ships the two
> mechanisms as optional parameters (off in every stored configuration), the holdout benchmark
> and the replacement rule. The search showed that relevance scaling collides with the global
> `RECOMMENDATION_MIN_SCORE`; see `candidates/RESULTS.md`. The bullets below describe the plan as
> proposed; the one about `v3-deterministic` did not happen.

## Why

On `benchmark-v1`, the active configuration `v2-deterministic` is not an improvement over `v1-deterministic` (NDCG@10 +0.0195, Precision@5 −0.0333). Per-signal diagnosis shows two mechanisms that lift weakly matching repositories into the top 5:

- **Difficulty fit is all-or-nothing.** It takes the best table value among a repository's relevant issues, so one fitting issue scores 1.0 regardless of how many or how relevant the issues are. `airflow-providers-x` for the Django developer (issue fit 0.21, difficulty fit 1.00) and `eslint-plugin-a11y` and `unity-platformer` for the beginner rise this way. Repositories without issues (`flask-auth-kit`, `portfolio-template`) lose up to 0.10 against them.
- **What a repository offers outweighs how well it fits.** Activity, openness and the two issue signals add the same amount to a weak match as to a strong one, and v2 moved weight from skill and language (0.60 → 0.50) to the issue signals. A busy, welcoming repository with a thin skill overlap outranks a quieter, clearly relevant one.

A weight-only probe that restored v1's relevance weights recovered Precision@5 but lost Recall@10 and NDCG@10, so the fix needs changed signal mechanics, not just new numbers. `recommendation-evaluation` now lets us change ranking on evidence: a new configuration `v3-deterministic` replaces v2 only if it wins.

## What Changes

- **Graded difficulty fit (opt-in per configuration)**: a new issue parameter selects how difficulty fit is computed. `best` (v2's behavior, the default when the parameter is absent) keeps the best table value. `weighted` averages the table values of the relevant issues with known difficulty, weighted by issue score, and scales the result by issue fit, so one weak issue no longer counts like several good ones.
- **Relevance-scaled offer signals (opt-in per configuration)**: a new parameter makes activity, contribution openness, issue fit and difficulty fit count in proportion to the candidate's relevance strength (the weighted mean of its skill, language, framework and interest signals). What a repository offers still orders relevant candidates but can no longer lift a weak match past a strong one. Stored signal values and reason texts are unchanged; the score and each reason's weight (its contribution, which orders the reasons) use the scaled contributions.
- **Holdout benchmark `holdout-v1`**: four new persona developers (with some new fictional repositories), judged before any v3 candidate is evaluated and never used to choose between candidates. v3 must not regress on it, which guards against tuning to `benchmark-v1`.
- **Bounded, recorded search**: a small, predeclared set of candidate configurations (mechanisms on/off × at most four weight vectors). Every candidate's metrics on both datasets are recorded in the change, including the ones that lost.
- **`v3-deterministic`**: the winning candidate, seeded by migration and made active only if it is an improvement over both v2 and v1 on `benchmark-v1` under the improvement rule, and does not regress on `holdout-v1` against v2 beyond the tolerance. Its match-label bands are recalibrated so that the share of Strong, Good and Partial labels on the benchmarks stays close to v2's. If no candidate qualifies, nothing is activated and the change records why.
- `v1-deterministic` and `v2-deterministic` stay stored and score exactly as before: the regression baseline proves it.

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
- `recommendation-engine`: difficulty fit gains the `weighted` mode; the score can scale offer signals by relevance strength; configurations may set both (no stored one does); a configuration replaces the active one only under the evaluation rule.
- `recommendation-evaluation`: a holdout benchmark that guards tuning, and the rule a new configuration must meet to replace the active one.

## Impact

- **Backend**: `services/matching/issues.py` (difficulty fit modes), `services/ranking/score.py` and `explain.py` (relevance-scaled contributions), `services/ranking/config.py` (new optional parameters with validation), `apps/backend/evaluation/holdout-v1.json`. `baselines.json` is unchanged.
- **Ranking**: unchanged for users (v2 stays active, scoring bit-for-bit as before). No migration, API, model schema or frontend change.
- **Tests**: unit tests for both mechanisms (including that their absence reproduces v2), config validation, the seed migration, holdout validity and the baseline.
