## Context

See proposal.md for why.
- `feedback.RecommendationFeedback`: `user`, `action` (`FeedbackAction`: viewed, saved, unsaved,
  dismissed, undismissed, opened_repository, opened_issue), snapshot fields `config_version`
  (blank when there was no recommendation), `rank` (null then), `match_label`, and
  `created_at`. Events are append-only; `viewed` is de-duplicated within 30 minutes.
- There is no impression ("shown") event and `Recommendation` keeps no history, so the number of
  recommendations a user was shown under a configuration is unknown. Rates per impression are
  out of reach; shares of outcomes are not.
- Evaluation tooling lives in `services/evaluation/` (pure modules, thin commands in
  `recommendations/management/commands/`), e.g. `evaluate_ranking`.
- Deleting a user's data or account deletes their feedback events (`delete_github_data`), so
  the report only ever covers retained events.

## Goals / Non-Goals

**Goals:**
- One command that answers "under which configuration did users act positively more often, at
  comparable ranks?" from data already stored.

**Non-Goals:**
- Impression logging, click-through rates, per-user or per-repository breakdowns.
- Match-label calibration (`ideas.md` §4, "Label calibration"): the label is in the snapshot,
  but a by-label report is a separate idea.
- Feeding the report into the improvement rule or activation.
- Netting `saved` against a later `unsaved` (events are counted as they happened).

## Decisions

**D1. A pure aggregator over plain rows.**
- `services/evaluation/feedback_report.py`:
  - `Event(user_id, action, config_version, rank)` (a `NamedTuple`);
  - `load(since: datetime | None, versions: Sequence[str]) -> list[Event]`: one
    `values_list("user_id", "action", "config_version", "rank")` query, filtered by
    `created_at__gte` and `config_version__in` when given;
  - `build(events, *, minimum) -> FeedbackReport`: pure.
- `user_id` is used only to count distinct users and never leaves `build`.
- *Alternative:* SQL `GROUP BY` with conditional counts. Rejected: distinct users per group and
  the adjustment are simpler in Python, and the event table is small (one row per action).

**D2. Buckets, shares and adjustment.**
- `BUCKETS = ((1, 5), (6, 10), (11, 20), (21, None))`, labels `1-5`, `6-10`, `11-20`, `21+`.
- `POSITIVE = {saved, opened_repository, opened_issue}`; `DECISIVE = POSITIVE | {dismissed}`.
- Group share = positive / decisive, or `None` when decisive < `minimum`.
- Raw configuration share = all its positive / all its decisive (`None` below the minimum).
- Adjusted share (direct standardization): weight per bucket = decisive actions in that bucket
  over every configuration in the report; for configuration C, over the buckets where C has a
  share, `sum(weight_b * share_Cb) / sum(weight_b)`; `None` when C has no such bucket.
- Events with a blank `config_version` or null `rank` go to an `unattributed` counter per action.
- Shares rounded to 4 places in output (`metrics.PLACES`).

**D3. Command `feedback_report`.**
- Options: `--since DAYS` (positive integer; default all time), `--config VERSION`
  (repeatable), `--minimum N` (default 10, at least 1), `--json OUT` (folder created; write
  error is a `CommandError` naming the path, as in `evaluate_ranking`).
- Output: one table per configuration (rows = buckets, columns = each action, users, share),
  then its raw and adjusted shares; then the unattributed line; then a note that shares are of
  decisive actions, not of recommendations shown, and that `-` means below the minimum.
- Configurations ordered by version name; a version with no events in the window is omitted
  (a `--config` that matches nothing prints "No feedback events").
- JSON: `{"since_days", "minimum", "configs": [{"version", "raw_share", "adjusted_share",
  "buckets": [{"ranks", "counts": {action: n}, "users", "share"}]}], "unattributed": {action:
  n}}`.

## Risks / Trade-offs

- [Shares of outcomes read as success rates] → The output note and README say what the
  denominator is.
- [Few users make shares noisy] → The minimum hides tiny groups; users per group are shown.
  Intervals (as in `evaluate_ranking`) are a later step if the report gets used.
- [Repeated actions by one user dominate a group] → Distinct users are shown next to counts;
  de-duplicating per user is a later option, not the default.

## Migration Plan

- No data change. Rollback: revert the release.
