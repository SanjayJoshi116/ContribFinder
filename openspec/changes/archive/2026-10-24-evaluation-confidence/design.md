## Context

See proposal.md for why.
- `services/evaluation/runner.evaluate(dataset, spec, ...) -> Report` ranks every developer
  through `rank_pool` and computes `metrics.developer_metrics` (unrounded values per developer).
  The `Report` keeps only rounded values: `DeveloperResult.metrics` per developer (4 places) and
  `metrics` (rounded means).
- `runner.compare(baseline, candidates, tolerance) -> list[Verdict]` applies the improvement
  rule to the rounded means. `services/ranking/activation.benchmark_judge` and
  `evaluate_ranking --require-improvement` use it.
- `evaluate_ranking` prints a table of means with deltas, subset means (persona/real), then each
  developer's metrics and top 10; `--json` writes `{"reports": [Report.as_dict()]}`.
- `baselines.json` holds means only (`baseline.write`); the baseline test recomputes them.
- Every report in one run is for the same dataset, so developers line up by position and id.

## Goals / Non-Goals

**Goals:**
- Show, next to each delta, how much of it could be one developer's ranking.
- Deterministic output: reruns and CI logs match.

**Non-Goals:**
- Gating the improvement rule, activation or `--require-improvement` on significance (proposal:
  decided with K-1).
- Intervals on single configurations' means, per-subset (persona/real) intervals, multiple
  comparison corrections, permutation tests.
- Writing intervals into `baselines.json`.

## Decisions

**D1. A pure `services/evaluation/bootstrap.py`.**
- `paired(baseline: Sequence[float], candidate: Sequence[float], *, resamples, seed) ->
  Interval(diff, low, high, not_better)`; `Interval.marked` is `low > 0 or high < 0`.
- One `random.Random(seed)` per call, so each metric's figures depend only on its own inputs,
  not on how many metrics or configurations came before: adding a metric or a configuration
  never changes another's interval.
- Resample: `rng.choices(range(n), k=n)`, mean of the differences at those indexes. Percentiles
  by sorting the resampled means and taking indexes `floor(0.025 * (R - 1))` and
  `ceil(0.975 * (R - 1))` (conservative nearest rank, no interpolation).
- `not_better` = share of resampled means `<= 0`.
- One developer: every resample is that developer, so `low == high == diff`, `not_better` is 1
  or 0. No special case needed beyond `n >= 1`; `n == 0` raises `ValueError` (a dataset always
  has developers: dataset validation).
- Cost: 10,000 resamples × 5 metrics × n developers; for n = 10 that is 500,000 additions per
  comparison, well under a second in pure Python. No numpy.
- *Alternative:* a randomization (sign-flip) test. Rejected for now: the bootstrap gives an
  interval in the metric's units, which reads next to the delta; a p-value alone does not.
- *Alternative:* BCa intervals. Rejected: more code for a handful of developers, where no
  interval method is accurate; the percentile interval is the documented, simple choice.

**D2. Unrounded per-developer values on `Report`.**
- `DeveloperResult` gains `values: dict[str, float]` (unrounded, from `DeveloperMetrics`);
  `metrics` stays rounded for printing and JSON. `as_dict` does not add `values` (the JSON
  report stays rounded per developer).
- Pairing by developer id: `uncertainty(baseline, candidate, ...)` checks that both reports list
  the same ids in the same order and raises `ValueError` otherwise (a programming error: every
  run evaluates one dataset per report pair).

**D3. `runner.uncertainty(baseline, candidate, *, resamples, seed) -> dict[str, Interval]`.**
- Separate from `compare`, which keeps its signature and verdicts, so activation and the
  baseline test are untouched.
- Defaults `DEFAULT_RESAMPLES = 10_000`, `DEFAULT_SEED = 20261024` in `bootstrap.py`.

**D4. Command output.**
- After the means table and the improvement verdicts of a dataset, one block per candidate
  (layout only; the numbers are illustrative):

  ```
  v2-deterministic vs v1-deterministic (paired bootstrap, 10000 resamples, seed 20261024)
    precision@5    -0.0333  [-0.1000, +0.0000]  not better 100.0%
    ndcg@10        +0.0195  [-0.0028, +0.0478]  not better   8.1%
    ...                                                        * interval excludes 0
  ```

  A marked metric ends with `*`. Rounded to 4 places (differences) and 1 place (percent).
- `--resamples N` (positive integer) and `--seed N`; `--resamples` below 1 is a command error.
- JSON: the top-level object gains `"comparisons": [{"dataset", "baseline", "config",
  "resamples", "seed", "metrics": {name: {"diff", "low", "high", "not_better", "marked"}}}]`,
  rounded like the means. `"reports"` is unchanged.
- `--write-baseline` runs print the block too; nothing about it is written to
  `baselines.json`.

## Risks / Trade-offs

- [Operators read "not marked" as "no effect"] → README says an unmarked difference is
  inconclusive at this sample size, not zero.
- [Percentile intervals are too narrow with very few developers] → Stated in README; the figures
  are a floor on uncertainty, not a guarantee. K-1 adds developers.
- [Output gets longer] → One block per candidate per dataset, five lines; the per-developer
  detail stays as it is.

## Migration Plan

- No data change. Rollback: revert the release.
