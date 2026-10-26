## Context

See proposal.md for why.
- `services/evaluation/feedback_report.py` (0.12.20): `Event(user_id, action, config_version,
  rank)` from one `values_list` query; `build(events, *, minimum, since_days)` groups by
  configuration and rank bucket into `BucketRow(bucket, counts, users, share)`, with raw and
  position-adjusted shares per configuration and an `unattributed` counter. `as_dict()` is the
  JSON shape. The command prints one table per configuration.
- `RecommendationFeedback.match_label` is the snapshot label (`MatchLabel`: strong, good,
  partial), blank when there was no recommendation.

## Goals / Non-Goals

**Goals:**
- One more table and one verdict per configuration, from the same events and definitions.

**Non-Goals:**
- Changing the bands, or position-adjusting the label shares (labels and ranks move together;
  the raw share is what users experience).
- Intervals or significance on the label shares.

## Decisions

**D1. `Event` gains `match_label`.**
- `load` adds `match_label` to the `values_list`; `Event(user_id, action, config_version, rank,
  match_label="")` keeps a default so the pure tests build events without it.

**D2. Label rows reuse the bucket row logic.**
- A shared helper turns a `Counter` of actions plus a user set into a row's counts, users and
  share, used for buckets and labels alike. `LabelRow(label, counts, users, share)`.
- `LABELS = ("strong", "good", "partial")`, best first, from `MatchLabel`.
- An event counts in the label rows only when it is attributed (version and rank) and has a
  label; the bucket rows and shares are unchanged.

**D3. Calibration verdict.**
- Over the labels with a share, in `LABELS` order, check every (higher, lower) pair in order
  (strong–good, strong–partial, good–partial); the first pair with `share(higher) <
  share(lower)` gives `not ordered: <higher> below <lower>`. Fewer than two shares →
  `not enough data`; otherwise `ordered`. Ties count as ordered ("at least as high").
- `Calibration(verdict: str, higher: str | None, lower: str | None)`; JSON
  `{"verdict": "ordered" | "not ordered" | "not enough data", "higher", "lower"}`.

**D4. Output.**
- After a configuration's bucket table and shares: a `match label` table (same columns, rows
  strong/good/partial when present), then `calibration: ordered` (or the other verdicts).
- The closing note adds: label shares are not adjusted for rank.
- JSON per configuration: `"labels": [{"label", "counts", "users", "share"}]`,
  `"calibration": {...}`.

## Risks / Trade-offs

- [`not ordered` read as "the bands are wrong"] → With few users a single heavy user can flip
  it; users per row are shown. The README says to read it with the user counts and to change
  bands only through a ranking change evaluated as such.

## Migration Plan

- No data change. Rollback: revert the release.
