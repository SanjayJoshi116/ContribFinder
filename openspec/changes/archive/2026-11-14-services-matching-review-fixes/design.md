## Context

Findings and verdicts are in `Bug_Backlog.md` batch 60, each checked by reading the code against
the specs. Matching reads the database only in `features.py`. Signals are pure, and evaluation
builds `RepoData`/`SnapshotData` straight from dataset files (`services/evaluation/dataset.py`),
bypassing `load_candidates`. Generation stores `Recommendation.activity_label` from the snapshot
it loaded (`services/ranking/service.py`). `Repository.pushed_at` is updated by every metadata
fetch and search upsert, so it is at least as fresh as the snapshot's push time.

## Goals / Non-Goals

**Goals:** behavior as the spec deltas say, with the change confined to loading and pure helpers
so that evaluation datasets and baselines do not move.

**Non-Goals:** ageing the 90-day counts (they stay as captured), changing the detail page's
snapshot section (it already shows the capture time), or changing any scoring configuration.
MAT-6 is not changed.

## Decisions

### D1. Current activity at load time (MAT-1, MAT-5)

`activity.current(snapshot_days, captured_at, pushed_at, commits, merged, now, thresholds) ->
(days, label)`:
- The days come from `pushed_at` (the repository row) when set. Without it they come from the
  snapshot's days plus the whole days since capture.
- The label is `activity_label(days, commits, merged, thresholds)` under the current
  `ACTIVITY_THRESHOLDS`.

`load_candidates(profile, *, now=None)` calls it once per candidate and builds `SnapshotData`
with the result. Its shape is unchanged, so signals, explanations and evaluation code are
untouched. `now` defaults to `timezone.now()`. The generation service passes its own `now` so a
run uses one clock. The latest snapshot prefetch also needs `captured_at`, which `latest_snapshot`
already loads.

Generation stores `activity_label` from `RepoData.snapshot.activity_label`, not from the
snapshot row. One label then serves the score, the reason and the filter.

Alternative: relabel stored snapshots when the thresholds version differs (MAT-5 alone).
Rejected: it fixes the threshold drift but not the ageing, and it writes shared rows from a
read path.

Export (`export_benchmark_developer`) goes through `load_candidates`, so new exports carry the
current label. Existing datasets are unchanged.

### D2. One unknown count (MAT-4)

`activity_label` checks each count on its own: `meets(n, threshold)` is `n is not None and
n >= threshold`.
- `recently_active` needs a recent push and `meets(commits, ...) or meets(merged, ...)`.
- `moderately_active` needs a moderate push and either an unknown count or one of the two
  `meets(...)`.

Both-unknown and both-known behave as before. The existing tests pin those cases.

### D3. Repository count from own-repository sources (MAT-2)

`load_developer` annotates `Count("evidence__repository", distinct=True,
filter=Q(evidence__source__in=OWN_REPOSITORY_SOURCES))`, with `OWN_REPOSITORY_SOURCES =
(language, topic, dependency)` from `developers.models.SkillSource`. These are the collectors
that read the developer's own repositories. The implementation checks that each collector passes
an owned repository and adds a test that fails otherwise. README evidence has no repository.

### D4. Evidence filter and single lookup (MAT-3, MAT-8)

`skill_match` and `language_match` build `matched` with `(c := dev.confidence(t.slug)) > 0`.
`skill_match`'s evidence also keeps only `t.weight * c > 0`. The value sum is unchanged, since a
zero product adds nothing. `language_match` already requires a share above 0. `framework_match`
is unchanged: its value is the noisy-OR of confidences, so every listed framework contributes.

### D5. Key lists guarded by a test (MAT-7)

A test asserts:
- `{k for k, _ in OPENNESS_FLAGS} == set(config.OPENNESS_KEYS)`;
- `set(ActivityLabel.values) == set(config.ACTIVITY_KEYS)`;
- `{DEPENDENCY_SOURCE, TOPIC_SOURCE} == set(config.TECH_SOURCE_KEYS)`.

Importing matching into `services/ranking/config.py` was rejected. `config` is imported by the
`ScoringConfig` model's validation, and matching imports models, so the import would risk a cycle
for a guard a test already gives.

## Risks / Trade-offs

- [Activity values change for stale or long-unrefreshed repositories after release] → That is
  the fix. The next freshness sweep regenerates them. Generation tests pin an aged case.
- [`Repository.pushed_at` newer than the snapshot pairs a fresh push with older counts] → The
  counts stay labelled "in 90 days" and the detail page shows their capture time. A fresh push
  with old low counts can only raise the label to moderate, never to recent without counts.
- [Baselines] → Evaluation datasets give activity directly, so `test_baseline_metrics_unchanged`
  must pass untouched.

## Migration Plan

None: no model, setting or API change. Existing recommendations change on their next
generation.
