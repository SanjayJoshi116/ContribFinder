# Minimum-score candidate search: results

Recorded in order, as the work happened (design D4).

## 0. Frozen datasets (before any candidate of this change was evaluated)

- `benchmark-v1.json` sha256 `c3ab1fd0f397853eeee0f632ce09b8dfa9d55a00dbcf1882fd9970dd609ace36` (used by the v3 search; unchanged)
- `holdout-v1.json` sha256 `01a56567004746efd4d3faa42b8ef8ca667b0b7080a12f172c1ffd4a65ae443a` (results seen in the v3 search: reporting only)
- `holdout-v2.json` sha256 `6ea6e7d5284a3735fe6f1460a02f22c859761e79b1db0369f115728b78c94dc0` (written 2026-10-14; acceptance set; no configuration evaluated on it yet)

## 1. Selection on benchmark-v1 (design D4)

Default min score 0.10 and top N 50; each candidate's own `min_score` / `min_score_basis` wins.
Deltas against v2. Qualifies = improvement over both v1 and v2. Report: `benchmark-report.json`.

| config | P@5 | P@10 | R@10 | MRR | NDCG@10 | verdict |
|---|---|---|---|---|---|---|
| v1-deterministic | 0.9333 | 0.6333 | 0.9276 | 1.0000 | 0.9459 |
| v2-deterministic | 0.9000 (-0.0333) | 0.6500 (+0.0167) | 0.9554 (+0.0278) | 1.0000 (+0.0000) | 0.9654 (+0.0195) |
| m01-best-scaled-W2-S05 | 0.9333 (+0.0333) | 0.6167 (-0.0333) | 0.8998 (-0.0556) | 1.0000 (+0.0000) | 0.9427 (-0.0227) | fails: vs v1: ndcg@10 0.9427 is not higher than 0.9459; vs v1: precision@10 dropped by 0.0166 (tolerance 0.0100); vs v1: recall@10 dropped by 0.0278 (tolerance 0.0100); vs v2: ndcg@10 0.9427 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0333 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0556 (tolerance 0.0100)
| m02-best-scaled-W2-R10 | 0.9333 (+0.0333) | 0.6167 (-0.0333) | 0.8998 (-0.0556) | 1.0000 (+0.0000) | 0.9427 (-0.0227) | fails: vs v1: ndcg@10 0.9427 is not higher than 0.9459; vs v1: precision@10 dropped by 0.0166 (tolerance 0.0100); vs v1: recall@10 dropped by 0.0278 (tolerance 0.0100); vs v2: ndcg@10 0.9427 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0333 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0556 (tolerance 0.0100)
| m03-best-scaled-WR-S05 | 0.9333 (+0.0333) | 0.6333 (-0.0167) | 0.9206 (-0.0348) | 1.0000 (+0.0000) | 0.9485 (-0.0169) | fails: vs v2: ndcg@10 0.9485 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0167 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0348 (tolerance 0.0100)
| m04-best-scaled-WR-R10 | 0.9333 (+0.0333) | 0.6333 (-0.0167) | 0.9206 (-0.0348) | 1.0000 (+0.0000) | 0.9485 (-0.0169) | fails: vs v2: ndcg@10 0.9485 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0167 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0348 (tolerance 0.0100)
| m05-best-scaled-WB-S05 | 0.9333 (+0.0333) | 0.6167 (-0.0333) | 0.8998 (-0.0556) | 1.0000 (+0.0000) | 0.9427 (-0.0227) | fails: vs v1: ndcg@10 0.9427 is not higher than 0.9459; vs v1: precision@10 dropped by 0.0166 (tolerance 0.0100); vs v1: recall@10 dropped by 0.0278 (tolerance 0.0100); vs v2: ndcg@10 0.9427 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0333 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0556 (tolerance 0.0100)
| m06-best-scaled-WB-R10 | 0.9333 (+0.0333) | 0.6167 (-0.0333) | 0.8998 (-0.0556) | 1.0000 (+0.0000) | 0.9427 (-0.0227) | fails: vs v1: ndcg@10 0.9427 is not higher than 0.9459; vs v1: precision@10 dropped by 0.0166 (tolerance 0.0100); vs v1: recall@10 dropped by 0.0278 (tolerance 0.0100); vs v2: ndcg@10 0.9427 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0333 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0556 (tolerance 0.0100)
| m07-best-scaled-WI-S05 | 0.9333 (+0.0333) | 0.6167 (-0.0333) | 0.8998 (-0.0556) | 1.0000 (+0.0000) | 0.9576 (-0.0078) | fails: vs v1: precision@10 dropped by 0.0166 (tolerance 0.0100); vs v1: recall@10 dropped by 0.0278 (tolerance 0.0100); vs v2: ndcg@10 0.9576 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0333 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0556 (tolerance 0.0100)
| m08-best-scaled-WI-R10 | 0.9333 (+0.0333) | 0.6167 (-0.0333) | 0.8998 (-0.0556) | 1.0000 (+0.0000) | 0.9576 (-0.0078) | fails: vs v1: precision@10 dropped by 0.0166 (tolerance 0.0100); vs v1: recall@10 dropped by 0.0278 (tolerance 0.0100); vs v2: ndcg@10 0.9576 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0333 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0556 (tolerance 0.0100)
| m09-weighted-scaled-W2-S05 | 0.9333 (+0.0333) | 0.6167 (-0.0333) | 0.8998 (-0.0556) | 1.0000 (+0.0000) | 0.9397 (-0.0257) | fails: vs v1: ndcg@10 0.9397 is not higher than 0.9459; vs v1: precision@10 dropped by 0.0166 (tolerance 0.0100); vs v1: recall@10 dropped by 0.0278 (tolerance 0.0100); vs v2: ndcg@10 0.9397 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0333 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0556 (tolerance 0.0100)
| m10-weighted-scaled-W2-R10 | 0.9333 (+0.0333) | 0.6167 (-0.0333) | 0.8998 (-0.0556) | 1.0000 (+0.0000) | 0.9397 (-0.0257) | fails: vs v1: ndcg@10 0.9397 is not higher than 0.9459; vs v1: precision@10 dropped by 0.0166 (tolerance 0.0100); vs v1: recall@10 dropped by 0.0278 (tolerance 0.0100); vs v2: ndcg@10 0.9397 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0333 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0556 (tolerance 0.0100)
| m11-weighted-scaled-WR-S05 | 0.9333 (+0.0333) | 0.6333 (-0.0167) | 0.9206 (-0.0348) | 1.0000 (+0.0000) | 0.9485 (-0.0169) | fails: vs v2: ndcg@10 0.9485 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0167 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0348 (tolerance 0.0100)
| m12-weighted-scaled-WR-R10 | 0.9333 (+0.0333) | 0.6333 (-0.0167) | 0.9206 (-0.0348) | 1.0000 (+0.0000) | 0.9485 (-0.0169) | fails: vs v2: ndcg@10 0.9485 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0167 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0348 (tolerance 0.0100)
| m13-weighted-scaled-WB-S05 | 0.9333 (+0.0333) | 0.6167 (-0.0333) | 0.8998 (-0.0556) | 1.0000 (+0.0000) | 0.9397 (-0.0257) | fails: vs v1: ndcg@10 0.9397 is not higher than 0.9459; vs v1: precision@10 dropped by 0.0166 (tolerance 0.0100); vs v1: recall@10 dropped by 0.0278 (tolerance 0.0100); vs v2: ndcg@10 0.9397 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0333 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0556 (tolerance 0.0100)
| m14-weighted-scaled-WB-R10 | 0.9333 (+0.0333) | 0.6167 (-0.0333) | 0.8998 (-0.0556) | 1.0000 (+0.0000) | 0.9397 (-0.0257) | fails: vs v1: ndcg@10 0.9397 is not higher than 0.9459; vs v1: precision@10 dropped by 0.0166 (tolerance 0.0100); vs v1: recall@10 dropped by 0.0278 (tolerance 0.0100); vs v2: ndcg@10 0.9397 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0333 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0556 (tolerance 0.0100)
| m15-weighted-scaled-WI-S05 | 0.9333 (+0.0333) | 0.6167 (-0.0333) | 0.8998 (-0.0556) | 1.0000 (+0.0000) | 0.9397 (-0.0257) | fails: vs v1: ndcg@10 0.9397 is not higher than 0.9459; vs v1: precision@10 dropped by 0.0166 (tolerance 0.0100); vs v1: recall@10 dropped by 0.0278 (tolerance 0.0100); vs v2: ndcg@10 0.9397 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0333 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0556 (tolerance 0.0100)
| m16-weighted-scaled-WI-R10 | 0.9333 (+0.0333) | 0.6167 (-0.0333) | 0.8998 (-0.0556) | 1.0000 (+0.0000) | 0.9397 (-0.0257) | fails: vs v1: ndcg@10 0.9397 is not higher than 0.9459; vs v1: precision@10 dropped by 0.0166 (tolerance 0.0100); vs v1: recall@10 dropped by 0.0278 (tolerance 0.0100); vs v2: ndcg@10 0.9397 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0333 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0556 (tolerance 0.0100)

**Choice: none.** Recorded before any holdout run. No v3 is seeded; v2 stays active.

### Why: the hypothesis is falsified

Every `m` candidate has exactly the metrics of its relevance-scaled base from the v3 search
(`m01`/`m02` = `c04`, `m03`/`m04` = `c05`, ..., `m15`/`m16` = `c15`). The minimum score was not the
binding constraint. Diagnostic (m01 with no cut at all, dev-beginner):

| repository | score | relevance part | judgment |
|---|---|---|---|
| bench/unity-platformer | 0.0574 | 0.0450 | 0 |
| bench/next-blog-starter | 0.0097 | 0.0083 | 1 |
| bench/tailwind-ui-blocks | 0.0081 | 0.0070 | 1 |

The two relevant repositories lost under scaling have a relevance part near 0.008, below any
sensible cut. Under v2 they reached the list only because activity, openness and issue signals
lifted them over 0.10. v2's Recall@10 advantage on `benchmark-v1` therefore comes from offer
signals promoting repositories with almost no relevance signal that happen to be judged 1 —
exactly the behavior relevance scaling is designed to remove. (S05 does admit
`unity-platformer` [0] at rank 7 for dev-beginner; no metric changes.)

### Follow-up suggested (not part of this change)

Tuning cannot resolve this; the data question comes first. Review whether those judgments
reflect what a beginner would want (they were written from a persona description), preferably
by adding real, hand-judged developers through `export_benchmark_developer`, and only then
revisit relevance scaling. Changing `benchmark-v1` judgments must be its own change, not part
of a search.

## 2. Holdouts, for the record only (task 4.4)

Run after section 1 was written; they did not and cannot change the choice.

### holdout-v2 (fresh; first evaluation on it)

| config | P@5 | P@10 | R@10 | MRR | NDCG@10 | vs v2 (tolerance 0.01) |
|---|---|---|---|---|---|---|
| v2-deterministic | 0.7000 | 0.4000 | 1.0000 | 1.0000 | 0.9745 |
| m01-best-scaled-W2-S05 | 0.8000 (+0.1000) | 0.4000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.9919 (+0.0174) | ok
| m02-best-scaled-W2-R10 | 0.8000 (+0.1000) | 0.4000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.9919 (+0.0174) | ok
| m03-best-scaled-WR-S05 | 0.8000 (+0.1000) | 0.4000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.9938 (+0.0193) | ok
| m04-best-scaled-WR-R10 | 0.8000 (+0.1000) | 0.4000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.9938 (+0.0193) | ok
| m05-best-scaled-WB-S05 | 0.8000 (+0.1000) | 0.4000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.9900 (+0.0155) | ok
| m06-best-scaled-WB-R10 | 0.8000 (+0.1000) | 0.4000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.9900 (+0.0155) | ok
| m07-best-scaled-WI-S05 | 0.8000 (+0.1000) | 0.4000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.9847 (+0.0102) | ok
| m08-best-scaled-WI-R10 | 0.8000 (+0.1000) | 0.4000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.9847 (+0.0102) | ok
| m09-weighted-scaled-W2-S05 | 0.8000 (+0.1000) | 0.4000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.9919 (+0.0174) | ok
| m10-weighted-scaled-W2-R10 | 0.8000 (+0.1000) | 0.4000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.9919 (+0.0174) | ok
| m11-weighted-scaled-WR-S05 | 0.8000 (+0.1000) | 0.4000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.9938 (+0.0193) | ok
| m12-weighted-scaled-WR-R10 | 0.8000 (+0.1000) | 0.4000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.9938 (+0.0193) | ok
| m13-weighted-scaled-WB-S05 | 0.8000 (+0.1000) | 0.4000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.9938 (+0.0193) | ok
| m14-weighted-scaled-WB-R10 | 0.8000 (+0.1000) | 0.4000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.9938 (+0.0193) | ok
| m15-weighted-scaled-WI-S05 | 0.8000 (+0.1000) | 0.4000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.9919 (+0.0174) | ok
| m16-weighted-scaled-WI-R10 | 0.8000 (+0.1000) | 0.4000 (+0.0000) | 1.0000 (+0.0000) | 1.0000 (+0.0000) | 0.9919 (+0.0174) | ok

### holdout-v1 (already seen in the v3 search)

| config | P@5 | P@10 | R@10 | MRR | NDCG@10 | vs v2 (tolerance 0.01) |
|---|---|---|---|---|---|---|
| v2-deterministic | 0.8000 | 0.4750 | 0.9500 | 1.0000 | 0.9342 |
| m01-best-scaled-W2-S05 | 0.8500 (+0.0500) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9701 (+0.0359) | ok
| m02-best-scaled-W2-R10 | 0.8500 (+0.0500) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9701 (+0.0359) | ok
| m03-best-scaled-WR-S05 | 0.8000 (+0.0000) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9371 (+0.0029) | ok
| m04-best-scaled-WR-R10 | 0.8000 (+0.0000) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9371 (+0.0029) | ok
| m05-best-scaled-WB-S05 | 0.8000 (+0.0000) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9361 (+0.0019) | ok
| m06-best-scaled-WB-R10 | 0.8000 (+0.0000) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9361 (+0.0019) | ok
| m07-best-scaled-WI-S05 | 0.8000 (+0.0000) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9688 (+0.0346) | ok
| m08-best-scaled-WI-R10 | 0.8000 (+0.0000) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9688 (+0.0346) | ok
| m09-weighted-scaled-W2-S05 | 0.8500 (+0.0500) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9701 (+0.0359) | ok
| m10-weighted-scaled-W2-R10 | 0.8500 (+0.0500) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9701 (+0.0359) | ok
| m11-weighted-scaled-WR-S05 | 0.8000 (+0.0000) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9371 (+0.0029) | ok
| m12-weighted-scaled-WR-R10 | 0.8000 (+0.0000) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9371 (+0.0029) | ok
| m13-weighted-scaled-WB-S05 | 0.8000 (+0.0000) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9361 (+0.0019) | ok
| m14-weighted-scaled-WB-R10 | 0.8000 (+0.0000) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9361 (+0.0019) | ok
| m15-weighted-scaled-WI-S05 | 0.8500 (+0.0500) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9701 (+0.0359) | ok
| m16-weighted-scaled-WI-R10 | 0.8500 (+0.0500) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9701 (+0.0359) | ok

**Reading.** On the fresh holdout every candidate beats v2 (P@5 +0.10, NDCG@10 up to +0.0193,
no recall loss), and holdout-v1 agrees. Both holdouts favor relevance scaling; only
`benchmark-v1` disagrees, for the reason in section 1. The protocol still holds: the holdout
accepts or rejects a candidate chosen on the benchmark and never overrides it, so nothing is
activated. This is the strongest argument yet for the data follow-up in section 1.

## 3. Outcome

No `v3-deterministic` is seeded; `v2-deterministic` stays active. The change ships the
configuration minimum score (`min_score`, `min_score_basis`), the evaluation override, baseline
format 2 and `holdout-v2`. `holdout-v2`'s results for these candidates are now recorded, so it
cannot accept a later change's candidate (spec "Holdout benchmark").
