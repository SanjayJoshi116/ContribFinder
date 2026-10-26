## Why

The match label (Strong, Good, Partial) is what users see in place of a score; it is the product's
promise about each recommendation. The score bands behind it (`params.bands`, 0.55 and 0.35)
were set by hand and have never been checked against what users do. `ideas.md` §4 ("Label
calibration"): check that Strong beats Good beats Partial on real outcomes.

Every feedback event already snapshots the label, and since 0.12.20 `feedback_report` turns the
events into positive shares per configuration. A by-label view is a small extension of the same
command and the same data.

## What Changes

- `feedback_report` adds, per configuration, one row per match label (Strong, Good, Partial) with
  each action's count, distinct users and the positive share, using the same definitions and
  minimum as the rank buckets.
- Per configuration, a **calibration** line: `ordered` when every label with a share has a share
  at least as high as every lower label's, `not ordered` naming the first pair that is out of
  order, or `not enough data` when fewer than two labels have a share.
- Events without a label (no recommendation at the time) stay unattributed, as today.
- The JSON report gains `labels` and `calibration` per configuration; existing keys unchanged.
- Labels follow rank (Strong recommendations sit higher), so the label view is raw, not
  position-adjusted: it measures the promise as users meet it. The output note says so.
- No API, UI, ranking or stored-data change; the bands themselves are not changed here.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `recommendation-evaluation`, "Feedback report": per-label rows and the calibration verdict.

## Impact

- Backend: `services/evaluation/feedback_report.py` (`Event` gains `match_label`, label rows,
  calibration), `feedback_report` command output, tests.
- Docs: README "Feedback report", CLAUDE.md §7, `ideas.md` §4 (label calibration shipped as a
  report; changing the bands stays a ranking change for K-1), CHANGELOG, features.
- Release: patch 0.12.21.
