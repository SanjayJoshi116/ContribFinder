# v3 candidate search: results

Recorded in order, as the work happened (design D4).

## 0. Frozen datasets (before any candidate was evaluated)

- `benchmark-v1.json` sha256 `c3ab1fd0f397853eeee0f632ce09b8dfa9d55a00dbcf1882fd9970dd609ace36`
- `holdout-v1.json` sha256 `01a56567004746efd4d3faa42b8ef8ca667b0b7080a12f172c1ffd4a65ae443a` (written 2026-10-14; no configuration had been evaluated on it)

## 1. Selection on benchmark-v1 (design D4 steps 1–2)

Pinned min score 0.10, top N 50. Deltas are against v2. A candidate qualifies only when it is an
improvement over **both** v1 and v2 (NDCG@10 strictly higher, no other metric lower by more than
0.01). Full per-developer reports: `benchmark-report.json`.

| config | P@5 | P@10 | R@10 | MRR | NDCG@10 | verdict |
|---|---|---|---|---|---|---|
| v1-deterministic | 0.9333 | 0.6333 | 0.9276 | 1.0000 | 0.9459 |
| v2-deterministic | 0.9000 (-0.0333) | 0.6500 (+0.0167) | 0.9554 (+0.0278) | 1.0000 (+0.0000) | 0.9654 (+0.0195) |
| c01-best-plain-WR | 0.9333 (+0.0333) | 0.6167 (-0.0333) | 0.8998 (-0.0556) | 1.0000 (+0.0000) | 0.9425 (-0.0229) | fails: vs v1: ndcg@10 0.9425 is not higher than 0.9459; vs v1: precision@10 dropped by 0.0166 (tolerance 0.0100); vs v1: recall@10 dropped by 0.0278 (tolerance 0.0100); vs v2: ndcg@10 0.9425 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0333 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0556 (tolerance 0.0100)
| c02-best-plain-WB | 0.9000 (+0.0000) | 0.6333 (-0.0167) | 0.9276 (-0.0278) | 1.0000 (+0.0000) | 0.9587 (-0.0067) | fails: vs v1: precision@5 dropped by 0.0333 (tolerance 0.0100); vs v2: ndcg@10 0.9587 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0167 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0278 (tolerance 0.0100)
| c03-best-plain-WI | 0.8333 (-0.0667) | 0.6500 (+0.0000) | 0.9554 (+0.0000) | 1.0000 (+0.0000) | 0.9560 (-0.0094) | fails: vs v1: precision@5 dropped by 0.1000 (tolerance 0.0100); vs v2: ndcg@10 0.9560 is not higher than 0.9654; vs v2: precision@5 dropped by 0.0667 (tolerance 0.0100)
| c04-best-scaled-W2 | 0.9333 (+0.0333) | 0.6167 (-0.0333) | 0.8998 (-0.0556) | 1.0000 (+0.0000) | 0.9427 (-0.0227) | fails: vs v1: ndcg@10 0.9427 is not higher than 0.9459; vs v1: precision@10 dropped by 0.0166 (tolerance 0.0100); vs v1: recall@10 dropped by 0.0278 (tolerance 0.0100); vs v2: ndcg@10 0.9427 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0333 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0556 (tolerance 0.0100)
| c05-best-scaled-WR | 0.9333 (+0.0333) | 0.6333 (-0.0167) | 0.9206 (-0.0348) | 1.0000 (+0.0000) | 0.9485 (-0.0169) | fails: vs v2: ndcg@10 0.9485 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0167 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0348 (tolerance 0.0100)
| c06-best-scaled-WB | 0.9333 (+0.0333) | 0.6167 (-0.0333) | 0.8998 (-0.0556) | 1.0000 (+0.0000) | 0.9427 (-0.0227) | fails: vs v1: ndcg@10 0.9427 is not higher than 0.9459; vs v1: precision@10 dropped by 0.0166 (tolerance 0.0100); vs v1: recall@10 dropped by 0.0278 (tolerance 0.0100); vs v2: ndcg@10 0.9427 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0333 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0556 (tolerance 0.0100)
| c07-best-scaled-WI | 0.9333 (+0.0333) | 0.6167 (-0.0333) | 0.8998 (-0.0556) | 1.0000 (+0.0000) | 0.9576 (-0.0078) | fails: vs v1: precision@10 dropped by 0.0166 (tolerance 0.0100); vs v1: recall@10 dropped by 0.0278 (tolerance 0.0100); vs v2: ndcg@10 0.9576 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0333 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0556 (tolerance 0.0100)
| c08-weighted-plain-W2 | 0.9000 (+0.0000) | 0.6333 (-0.0167) | 0.9276 (-0.0278) | 1.0000 (+0.0000) | 0.9582 (-0.0072) | fails: vs v1: precision@5 dropped by 0.0333 (tolerance 0.0100); vs v2: ndcg@10 0.9582 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0167 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0278 (tolerance 0.0100)
| c09-weighted-plain-WR | 0.9333 (+0.0333) | 0.6167 (-0.0333) | 0.8998 (-0.0556) | 1.0000 (+0.0000) | 0.9400 (-0.0254) | fails: vs v1: ndcg@10 0.9400 is not higher than 0.9459; vs v1: precision@10 dropped by 0.0166 (tolerance 0.0100); vs v1: recall@10 dropped by 0.0278 (tolerance 0.0100); vs v2: ndcg@10 0.9400 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0333 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0556 (tolerance 0.0100)
| c10-weighted-plain-WB | 0.9333 (+0.0333) | 0.6167 (-0.0333) | 0.8998 (-0.0556) | 1.0000 (+0.0000) | 0.9542 (-0.0112) | fails: vs v1: precision@10 dropped by 0.0166 (tolerance 0.0100); vs v1: recall@10 dropped by 0.0278 (tolerance 0.0100); vs v2: ndcg@10 0.9542 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0333 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0556 (tolerance 0.0100)
| c11-weighted-plain-WI | 0.9000 (+0.0000) | 0.6500 (+0.0000) | 0.9554 (+0.0000) | 1.0000 (+0.0000) | 0.9645 (-0.0009) | fails: vs v1: precision@5 dropped by 0.0333 (tolerance 0.0100); vs v2: ndcg@10 0.9645 is not higher than 0.9654
| c12-weighted-scaled-W2 | 0.9333 (+0.0333) | 0.6167 (-0.0333) | 0.8998 (-0.0556) | 1.0000 (+0.0000) | 0.9397 (-0.0257) | fails: vs v1: ndcg@10 0.9397 is not higher than 0.9459; vs v1: precision@10 dropped by 0.0166 (tolerance 0.0100); vs v1: recall@10 dropped by 0.0278 (tolerance 0.0100); vs v2: ndcg@10 0.9397 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0333 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0556 (tolerance 0.0100)
| c13-weighted-scaled-WR | 0.9333 (+0.0333) | 0.6333 (-0.0167) | 0.9206 (-0.0348) | 1.0000 (+0.0000) | 0.9485 (-0.0169) | fails: vs v2: ndcg@10 0.9485 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0167 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0348 (tolerance 0.0100)
| c14-weighted-scaled-WB | 0.9333 (+0.0333) | 0.6167 (-0.0333) | 0.8998 (-0.0556) | 1.0000 (+0.0000) | 0.9397 (-0.0257) | fails: vs v1: ndcg@10 0.9397 is not higher than 0.9459; vs v1: precision@10 dropped by 0.0166 (tolerance 0.0100); vs v1: recall@10 dropped by 0.0278 (tolerance 0.0100); vs v2: ndcg@10 0.9397 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0333 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0556 (tolerance 0.0100)
| c15-weighted-scaled-WI | 0.9333 (+0.0333) | 0.6167 (-0.0333) | 0.8998 (-0.0556) | 1.0000 (+0.0000) | 0.9397 (-0.0257) | fails: vs v1: ndcg@10 0.9397 is not higher than 0.9459; vs v1: precision@10 dropped by 0.0166 (tolerance 0.0100); vs v1: recall@10 dropped by 0.0278 (tolerance 0.0100); vs v2: ndcg@10 0.9397 is not higher than 0.9654; vs v2: precision@10 dropped by 0.0333 (tolerance 0.0100); vs v2: recall@10 dropped by 0.0556 (tolerance 0.0100)

Chosen: none qualifies

**Choice: none.** No candidate qualifies. The choice is recorded here before any holdout run;
per design D4 no v3 is seeded and v2 stays active.

### Why (per-developer reports)

- **Relevance scaling works on the targeted failure.** With scaling, the off-topic repositories
  leave dev-django's top 5 (`airflow-providers-x` [0] out, `flask-auth-kit` [1] in: P@5 0.80 →
  1.00), and every scaled candidate reaches P@5 0.9333.
- **But it collides with the global minimum score.** Scaling lowers the scores of weak
  candidates, and `RECOMMENDATION_MIN_SCORE` (0.10, a setting outside the configuration) then cuts
  them. dev-beginner's list shrinks from 9 to 6 results and loses `next-blog-starter` [1] and
  `tailwind-ui-blocks` [1] (R@10 1.000 → 0.667); dev-rust and dev-go-infra lists shrink too.
  This is the source of every scaled candidate's Recall@10 and P@10 loss.
- **Weighted difficulty fit alone changes little.** `c08` (v2 weights) and `c11` (issue-heavy)
  keep v2's lists almost unchanged; `c11` ties v2 on every metric but NDCG@10 (−0.0009).
- **dev-beginner's `eslint-plugin-a11y` [0] stays in the top 5 under every candidate.** It is a
  JavaScript relevance match, not an issue-signal effect, so no mechanism in this grid addresses it.

### Follow-up suggested (not part of this change)

Make the minimum score part of the scoring configuration (or apply it before offer signals, to
the relevance part only), then re-run the scaled candidates. That is a new hypothesis, so it
belongs in a new change with its own predeclared grid; trying it here would be tuning after
seeing the results.

## 2. Holdout-v1, for the record only (task 3.4)

Run after section 1 was written. It did not and cannot change the choice. Report:
`holdout-all-report.json`.

| config | P@5 | P@10 | R@10 | MRR | NDCG@10 | vs v2 (tolerance 0.01) |
|---|---|---|---|---|---|---|
| v2-deterministic | 0.8000 | 0.4750 | 0.9500 | 1.0000 | 0.9342 |
| c01-best-plain-WR | 0.8000 (+0.0000) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9678 (+0.0336) | ok
| c02-best-plain-WB | 0.8000 (+0.0000) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9509 (+0.0167) | ok
| c03-best-plain-WI | 0.8000 (+0.0000) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9342 (+0.0000) | ok
| c04-best-scaled-W2 | 0.8500 (+0.0500) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9701 (+0.0359) | ok
| c05-best-scaled-WR | 0.8000 (+0.0000) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9371 (+0.0029) | ok
| c06-best-scaled-WB | 0.8000 (+0.0000) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9361 (+0.0019) | ok
| c07-best-scaled-WI | 0.8000 (+0.0000) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9688 (+0.0346) | ok
| c08-weighted-plain-W2 | 0.8000 (+0.0000) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9420 (+0.0078) | ok
| c09-weighted-plain-WR | 0.8000 (+0.0000) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9678 (+0.0336) | ok
| c10-weighted-plain-WB | 0.8000 (+0.0000) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9581 (+0.0239) | ok
| c11-weighted-plain-WI | 0.8000 (+0.0000) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9420 (+0.0078) | ok
| c12-weighted-scaled-W2 | 0.8500 (+0.0500) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9701 (+0.0359) | ok
| c13-weighted-scaled-WR | 0.8000 (+0.0000) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9371 (+0.0029) | ok
| c14-weighted-scaled-WB | 0.8000 (+0.0000) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9361 (+0.0019) | ok
| c15-weighted-scaled-WI | 0.8500 (+0.0500) | 0.4750 (+0.0000) | 0.9500 (+0.0000) | 1.0000 (+0.0000) | 0.9701 (+0.0359) | ok

No candidate regresses against v2 on the holdout, and the scaled ones gain up to +0.0359
NDCG@10. The datasets disagree because the holdout has few weak-but-relevant candidates near the
0.10 minimum score, the pattern that costs the scaled candidates recall on `benchmark-v1`. This
supports the follow-up in section 1. It is not grounds for activating any candidate, because the
holdout is not a selection set.

## 3. Outcome

No `v3-deterministic` is seeded; `v2-deterministic` stays active. Both mechanisms ship as
optional configuration parameters (`issues.difficulty_fit_mode`, `relevance_scaling`), off for
every stored configuration, with v1 and v2 unchanged bit-for-bit (regression baseline).
