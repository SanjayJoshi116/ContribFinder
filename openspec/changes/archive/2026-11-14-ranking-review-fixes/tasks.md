## 1. Freshness

- [x] 1.1 RNK-1: `failed_recently` reads the latest finished generation (D1). Tests: a failure 30 min ago followed by a completed generation 20 min ago and a re-analysis 10 min ago is due; a latest failure 10 min ago is not due; after the delay it is.
- [x] 1.2 RNK-2: due when the last completed generation's `config_version` differs from the active version (D2). Tests: 0 recommendations under v2, v3 activated → due; same version and nothing changed → not due; a job without `config_version` does not make the developer due by itself.
- [x] 1.3 RNK-6: `start_due_generations` continues past a failing start and logs it (D3). Test: two due developers, the first send raises → the second job is started and the count is 1.

## 2. Activation

- [x] 2.1 RNK-5: re-check the candidate exists under the lock (D4). Test: delete the candidate inside a judge stub → `ActivationError`, the previous config stays the only active one, no audit event.

## 3. Scoring and explanations

- [x] 3.1 RNK-8, RNK-10: `Scored.parts`; `explain.reasons(signals, parts)`; remove `weighted_score`; `service.py` passes `s.parts`; tests move to the new signatures (D5).
- [x] 3.2 RNK-7: a reason needs its rounded contribution above 0. Test: relevance scaling with a tiny strength gives no `openness` reason.
- [x] 3.3 RNK-3: `framework_match` skips weight-0 technologies. Test: topic weight 0 and a topic-only `django` → framework 0, no evidence, no `framework` reason.
- [x] 3.4 RNK-4: openness evidence lists only flags with points above 0; value unchanged. Test: issue templates 0 points → reason names the contributing guide only.
- [x] 3.5 RNK-9: `rank_pool` skips issue loading when both issue weights are 0 (D6). Test: such a config never calls `issues_for` and gives `NO_MATCH`.

## 4. Checks

- [x] 4.1 `test_baseline_metrics_unchanged` passes untouched; `evaluate_ranking` shows no movement for v1/v2.
- [x] 4.2 Backend: `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`, `uv run mypy .`, `makemigrations --check --settings config.settings.test`.

## 5. Release

- [x] 5.1 `Bug_Backlog.md` ranking sweep batch: RNK rows marked fixed.
- [x] 5.2 `/simplify`, then `/code-review` on the fix diff; record and fix (or skipped by the owner). Owner: marked done without a separate run.
- [x] 5.3 Archive (deltas into `recommendation-engine`, `recommendation-explanations`, `recommendation-evaluation`). Release housekeeping per CLAUDE.md §8 (0.12.66; history entry in `CLAUDE_HISTORY.md`). Commit only when the owner says so.
