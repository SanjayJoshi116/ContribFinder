## Why

The review sweep's fourth low-priority module, `apps/backend/services/matching/`
(`Bug_Backlog.md` batch 60, MAT-1…MAT-8), found reasons that state things the evidence does not
support, and an activity label that drifts from the data:
- The activity signal and its reason use the push age stored when the activity data was
  captured. A repository whose refresh keeps failing stays scorable (stale) and still reads
  "pushed today" weeks later, at the recently-active value (MAT-1). For the same reason, a
  threshold change reaches ranking only as each repository's activity is fetched again, so one
  list mixes labels from old and new thresholds (MAT-5).
- With one activity count unknown, the label treats it as 0: a project pushed 5 days ago with an
  unknown commit count and no merged pull requests is `low_activity`. With both counts unknown it
  would be `moderately_active` (MAT-4).
- "Appears in N of your repositories" counts repositories the developer only contributed to
  (MAT-2).
- The skill reason names technologies that added nothing to the score (weight 0), against "only
  evidence that signal actually used" (MAT-3).

MAT-7 (key lists duplicated with nothing to keep them in step) and MAT-8 (a repeated lookup) are
cleanup. MAT-6 was rejected: search ranks restart per star band on purpose, so the pool keeps a
size mix (`discovery-size-mix`), and the score tie-break shares that order. The security review
found nothing.

## What Changes

- MAT-1, MAT-5: generation measures the push age at generation time, from the repository's last
  known push. It labels activity from that age and the snapshot's counts under the current
  thresholds. The activity signal, its reason and the recommendation's activity filter value all
  use that label. Stored snapshots are unchanged, and the detail page still shows them with their
  capture time.
- MAT-4: an unknown count never counts as 0. `recently_active` needs a known count that meets its
  threshold, and `moderately_active` accepts an unknown count as it does when both are unknown.
- MAT-2: the framework reason counts only the developer's own repositories (language, topic or
  dependency evidence). Contributions are not counted as "your repositories".
- MAT-3: the skill signal's evidence lists only technologies whose weight and confidence are both
  above 0. The value is unchanged.
- MAT-7: a test fails when the openness flags, activity labels or technology sources used by
  matching differ from the keys configuration validation requires.
- MAT-8: the developer's confidence is read once per technology.
- No scoring configuration change. MAT-1, MAT-4 and MAT-5 can change activity values, and so
  scores and order, for recommendations generated after the release. The benchmarks store
  activity labels and evidence counts, so baselines cannot move.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repository-activity`: "Activity label" (one unknown count; the label used for ranking is
  computed at generation).
- `recommendation-engine`: "Relevance signals" (activity signal from the push age at generation).
- `recommendation-explanations`: "Reasons from scoring evidence" (own repositories only;
  zero-contribution technologies left out).

## Impact

- Code: `services/matching/activity.py` (`activity_label`, a function giving the current push age
  and label), `features.py` (`load_developer` repository count, `load_candidates` current
  activity), `signals.py` (`skill_match`, `language_match` lookups), `services/ranking/service.py`
  (the stored `activity_label` comes from the loaded data).
- Tests: `test_matching_activity.py`, `test_matching_features.py`, `test_matching_signals.py`, a
  key-list guard test, and generation tests that read the activity label.
- No API, model, migration, setting or OpenAPI change. Evaluation datasets are unchanged: they
  give activity directly, not through the database loader.
