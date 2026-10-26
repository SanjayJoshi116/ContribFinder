## Why

The benchmark has 6 persona developers (`benchmark-v1`), and `benchmark-v2` will add a few real
ones after K-1. With so few developers, a metric difference such as v2's NDCG@10 +0.0195 over
v1 can be noise: one developer's ranking moving decides it. The improvement rule
(`recommendation-evaluation`) compares rounded means only, so a ranking search can "win" on
noise and nobody can tell from the report.

`ideas.md` §3 ("Significance testing") asks for a paired bootstrap per developer and confidence
intervals in the `evaluate_ranking` report, landing before or with K-1 so the next ranking search
is read with its uncertainty. It changes no ranking, so it can ship now.

## What Changes

- `evaluate_ranking` reports, for every configuration after the baseline and every metric, the
  paired difference from the baseline with a 95% bootstrap confidence interval over developers,
  and the share of resamples in which the candidate is not better. It marks a difference whose
  interval excludes 0.
- The interval is reproducible: a fixed number of resamples (10,000) and a fixed seed, so the
  same dataset and configurations always print the same numbers. Both can be set on the
  command.
- The JSON report carries the same figures per comparison.
- The improvement rule, `--require-improvement`, activation and `baselines.json` are unchanged:
  the figures are information for the operator. Whether a ranking change must also be
  significant is decided with K-1, when there are real developers to measure it on.
- No API, UI or ranking change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `recommendation-evaluation`:
  - "Evaluation command": the printed comparison and the JSON report include the paired
    difference, its 95% bootstrap interval and the share of resamples not better, per metric.
  - New requirement "Uncertainty of a comparison": how the bootstrap is computed (paired over
    developers, percentile interval, fixed seed and resample count) and that it never changes
    the improvement verdict.

## Impact

- Backend:
  - `services/evaluation/metrics.py` or a new `services/evaluation/bootstrap.py` (pure);
  - `services/evaluation/runner.py` (unrounded per-developer values on the report, a
    comparison result with the intervals);
  - `evaluate_ranking` (printing, `--resamples`, `--seed`, JSON);
  - tests.
- Docs: README "Evaluating a ranking change", `ideas.md` §3 (shipped part), CLAUDE.md §6
  (`evaluate_ranking` line) and §7, CHANGELOG, features.
- No new dependency: the standard library's `random` with a seeded generator is enough for
  10,000 resamples of a handful of developers.
- Release: patch 0.12.19 (after `activation-command-only`, 0.12.18).
