## Why

Ranks start at 1 everywhere they are written (`enumerate(..., start=1)` in
`services/ranking/service.py`), but the columns are `PositiveIntegerField` /
`PositiveSmallIntegerField`, which PostgreSQL lets hold 0. Only the feedback report knows that a
rank of 0 means "no rank" (it counts such events as unattributed); every other reader would
treat 0 as a real position above 1. `Bug_Backlog.md` T-12 (batch 19, the 0.12.23 review's skip),
first in "Next". No rank 0 is written today, so the database should refuse one rather than rely
on every future writer. No ranking change.

## What Changes

- Database check constraints: `Recommendation.rank >= 1`, `RecommendedIssue.rank >= 1`, and
  `RecommendationFeedback.rank` null or `>= 1`.
- One migration per app adds them. Before adding a constraint, stored rows that would violate it
  are repaired, never deleted: a feedback event with rank 0 gets rank null (what the report
  already reads it as); a developer's recommendations, or a recommendation's matched issues, that
  include a rank 0 are shifted up by one, which keeps their order.
- Tests: each constraint refuses 0, the event accepts null, the repair keeps order, generation
  and feedback still write valid ranks.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `recommendation-engine`: new requirement "Stored ranks start at 1" (recommendations and their
  matched issues).
- `recommendation-feedback`: new requirement "Feedback rank snapshot" (null or at least 1).

## Impact

- Backend: `recommendations/models.py`, `issues/models.py`, `feedback/models.py` (`Meta.constraints`);
  migrations `recommendations.0005`, `issues.0002`, `feedback.0005`; tests. No API, setting or
  interface change; the OpenAPI schema does not change (constraints are not exposed).
- `Bug_Backlog.md` T-12 fixed; CLAUDE.md §7 shipped entry, CHANGELOG, `features.txt`, README
  status line. Release: patch 0.12.29.
