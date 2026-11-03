## Why

The review sweep of `apps/backend/feedback/` (`Bug_Backlog.md` batch 42, FB-1…FB-7) found three
defects worth fixing:

- an `opened_issue` event can be stored for an issue a concurrent generation has just dropped;
- a dashboard card's Unsave fails once a background generation has dropped its recommendation;
- every feedback, save and dismiss request reads the recommendation twice.

The code already has to follow the `recommendation-feedback` spec on all three points: an
`opened_issue` event names one of the recommendation's relevant issues, and unsave works whether
or not the project is still recommended. So this is a fix release with no spec change.

## What Changes

- **FB-1**: the relevance check for `opened_issue` moves from the view into
  `services.feedback.record`. It runs after the recommendation row is locked, which is the lock
  a generation holds while it rewrites the recommendation's relevant issues. An issue that is not
  relevant at that point is rejected with the existing 400 (`issue_id`). The view no longer reads
  `RecommendedIssue`.
- **FB-3**: the Save/Saved toggle on cards and the detail page unsaves through
  `DELETE /api/v1/saved/{repository_id}`, the endpoint the saved list already uses. A recommendation
  that has been regenerated away no longer turns Unsave into a 404, and the save is removed.
  `DELETE /recommendations/{id}/save` stays, unchanged, for API compatibility.
- **FB-5**: the ownership check in the feedback views loads only the recommendation's pk and
  repository id. The service's own re-read (`_current`, or `_current_recommendation` in
  `dismiss`) is the only full read. One join query fewer per request.
- Accepted, no code change (decided 2026-11-03):
  - FB-2: only `viewed` is de-duplicated. Two opens are two real opens, and the effect is limited
    to the offline report, which also prints distinct users.
  - FB-6: a full `count` on every cursor page. The rows are per user and on the keyset indexes,
    and the spec requires the total on every page.
- Closed without change:
  - FB-4, false positive: the spec says a restored project "MAY" come back.
  - FB-7, wontfix: one consumer, and a keyset cannot stabilize rank-ordered pages that a
    regeneration renumbers.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The code is brought in line with the existing `recommendation-feedback` requirements
("Recording feedback", "Save a recommendation"), so `skip_specs: true`.

## Impact

- Backend:
  - `apps/backend/services/feedback.py`: `record` takes `issue_id`, raises `IssueNotRelevant`;
    `dismiss` works from the repository id.
  - `apps/backend/feedback/api.py`: `_own_recommendation` becomes a light ownership check;
    `FeedbackView` maps `IssueNotRelevant` to 400.
- Frontend: `apps/frontend/src/features/feedback/api.ts` (the unsave variant of `useSaveToggle`)
  and its callers in `RecommendationActions.tsx`.
- API: no contract change (OpenAPI stays `1.0.0`; the 400 shape for `issue_id` is unchanged).
- Tests: new backend tests for FB-1 (issue dropped between the view and the lock) and FB-5
  (query count); a frontend test for FB-3 (unsave hits `/saved/{repository_id}`).
- No ranking, scoring or migration change.
