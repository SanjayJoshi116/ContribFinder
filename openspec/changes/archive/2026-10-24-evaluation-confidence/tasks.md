## 1. Bootstrap (D1)

- [x] 1.1 `services/evaluation/bootstrap.py`: `Interval(diff, low, high, not_better)` with
  `marked`; `paired(baseline, candidate, *, resamples, seed)`; `DEFAULT_RESAMPLES`,
  `DEFAULT_SEED`; `ValueError` for unequal lengths, no developers or `resamples < 1`.
- [x] 1.2 Tests (`tests/test_evaluation_bootstrap.py`), pure:
  - same inputs and seed → same interval; another seed may differ;
  - one better of six, five equal → `low == 0`, not marked, `not_better` near (5/6)^6;
  - all better → `low > 0`, marked, `not_better == 0`; all worse → `high < 0`, marked;
  - identical lists → `diff == low == high == 0`, not marked, `not_better == 1`;
  - one developer → zero-width interval at the difference;
  - adding a metric or configuration elsewhere does not change an interval (one generator per
    call).

## 2. Runner (D2, D3)

- [x] 2.1 `runner.py`: `DeveloperResult.values` (unrounded); `uncertainty(baseline, candidate,
  *, resamples, seed) -> dict[str, Interval]`, pairing by developer id (`ValueError` on a
  mismatch). `compare`, `Report.metrics` and `as_dict` unchanged.
- [x] 2.2 Tests: `uncertainty` on two evaluated reports of `benchmark-v1` (v1, v2) is
  deterministic and its `diff` equals the unrounded mean difference; mismatched developers
  raise; `compare` verdicts and `baselines.json` unchanged (baseline test passes).

## 3. Command (D4)

- [x] 3.1 `evaluate_ranking`: the uncertainty block per candidate and dataset, `*` for marked
  metrics; `--resamples`, `--seed` (positive resamples, else `CommandError`); JSON
  `"comparisons"`.
- [x] 3.2 Tests: the block is printed for `--config v1-deterministic --config v2-deterministic`
  with every metric; a single configuration prints none; `--resamples 0` fails; the JSON report
  has `comparisons` with the documented keys and the same `reports` as before;
  `--require-improvement` behaves as before.

## 4. Verification and housekeeping

- [x] 4.1 Backend `ruff check`, `ruff format --check`, `mypy`, `pytest`; `git diff --exit-code
  apps/backend/evaluation/baselines.json`. No frontend or e2e change.
- [x] 4.2 Run `npm run manage -- evaluate_ranking --config v1-deterministic --config
  v2-deterministic`; record v2's NDCG@10 and Precision@5 intervals in the CHANGELOG entry and
  `ideas.md` §3.
- [x] 4.3 Docs:
  - README "Evaluating a ranking change": the block, what a mark means, that an unmarked
    difference is inconclusive (not zero), `--resamples`/`--seed`;
  - CLAUDE.md §6 `evaluate_ranking` line and §7 shipped entry (K-1 carry-over: intervals ready;
    gating decided with K-1);
  - `ideas.md` §3 significance testing moved to "Shipped" (gating stays open), priorities table.
- [x] 4.4 Release housekeeping (CLAUDE.md §8): patch 0.12.19; `CHANGELOG.md`, `features.txt`,
  README status line.
