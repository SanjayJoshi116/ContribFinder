## 1. Activity

- [x] 1.1 MAT-4: `activity_label` checks each count on its own (D2). Tests: unknown commits with 0 merged pull requests, pushed 5 days ago, is moderately active; unknown commits with 9 merged, pushed 5 days ago, is recently active; the both-unknown and both-known cases are unchanged.
- [x] 1.2 MAT-1, MAT-5: add `activity.current(...)` (D1). `load_candidates(profile, *, now=None)` builds `SnapshotData` from it, and generation passes its `now` and stores the loaded label. Tests: a snapshot captured 40 days ago with a push that day loads as 40 days and `moderately_active`, with reason "last push 40 days ago"; a threshold change applies before a refresh; the stored snapshot row is unchanged; `Recommendation.activity_label` equals the scored label.

## 2. Profile and signals

- [x] 2.1 MAT-2: `load_developer` counts only own-repository evidence sources (D3). Tests: 1 owned Django repository plus 2 contributed ones gives a count of 1 and the reason "one of your repositories"; each own-repository collector passes an owned repository.
- [x] 2.2 MAT-3, MAT-8: `skill_match` evidence keeps only `weight * confidence > 0`, and both matchers read confidence once (D4). Tests: with topic weight 0, Kubernetes is not named and the value is unchanged; a language share that rounds to 0 is not named.
- [x] 2.3 MAT-7: a key-list guard test (D5).

## 3. Checks

- [x] 3.1 `test_baseline_metrics_unchanged` passes untouched (evaluation datasets give activity and repository counts directly).
- [x] 3.2 Backend: `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`, `uv run mypy .`, `makemigrations --check --settings config.settings.test`.

## 4. Release

- [x] 4.1 `Bug_Backlog.md` batch 60: MAT rows marked fixed, MAT-6 rejected (by design).
- [x] 4.2 `/simplify`, then `/code-review` on the fix diff; record and fix (or skipped by the owner). Skipped by the owner.
- [x] 4.3 Archive (deltas into `repository-activity`, `recommendation-engine`, `recommendation-explanations`). Release housekeeping per CLAUDE.md §8, next patch version. Commit only when the owner says so.
