## Why

Every save, dismissal and GitHub click is stored as a `RecommendationFeedback` event with a
snapshot of the recommendation's scoring configuration version, rank and match label (Phase 8a),
"for evaluating recommendation quality" (privacy page). Nothing reads them. The benchmark judges
rankings offline on a handful of developers; the events are the only signal from real use, and
they already say which configuration produced what users acted on.

`ideas.md` §4 ("Online report per config"): report save, dismiss and open rates by configuration
version and rank position, corrected for position bias. It changes no ranking, needs no new
data, and gives K-1-era ranking decisions a second, independent signal.

## What Changes

- New management command `feedback_report` (read-only, offline) that groups feedback events by
  configuration version and rank bucket (1–5, 6–10, 11–20, 21+), and reports per group:
  - the count of each action and the number of distinct users;
  - the **positive share**: positive actions (saved, opened repository, opened issue) out of
    decisive actions (those plus dismissed). There is no "shown" event, so this is a share of
    outcomes, not a click-through rate;
  - per configuration, a **position-adjusted** positive share: the bucket shares weighted by one
    common bucket mix (all configurations' decisive actions together), so a configuration whose
    recommendations were acted on at higher ranks does not look better for that alone.
- Groups with fewer decisive actions than a minimum (default 10) show counts but no share.
- Options: a time window (`--since` days), configuration versions to include, the minimum, and a
  JSON output file. Events without a configuration version or rank (no recommendation at the
  time) are counted separately and left out of the shares.
- The report holds aggregates only: no user, repository or recommendation identifiers.
- No API, UI, ranking or stored-data change; `viewed`, `unsaved` and `undismissed` are counted
  but are neither positive nor decisive.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `recommendation-evaluation`: new requirement "Feedback report" (what is grouped, the positive
  share, the position adjustment, the minimum, aggregates only, read-only).

## Impact

- Backend: `services/evaluation/feedback_report.py` (aggregation on plain rows, pure, plus one
  query); `recommendations/management/commands/feedback_report.py`; tests.
- No migration: the existing snapshot fields are enough. One `values_list` query over the events
  in the window.
- Docs: README (new "Feedback report" paragraph under evaluation), CLAUDE.md §6 and §7,
  `ideas.md` §4 (shipped part; label calibration and dismiss reasons stay open), CHANGELOG,
  features.
- Release: patch 0.12.20.
