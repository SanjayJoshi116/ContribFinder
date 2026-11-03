## Context

See proposal.md for the motivation. The lock order (`services/locks.py`) is: job, then the
developer profile, then dismissals and saves, then recommendations, then issues by pk.

`record` locks only its recommendation row (W-10: views must not wait for a whole persist).
Generation (`ranking/service.py`) takes `select_for_update` on every recommendation row of the
developer before it deletes and re-creates their `RecommendedIssue` rows, and it keeps those row
locks until commit.

## Goals / Non-Goals

**Goals:**

- The `opened_issue` relevance rule is enforced where the rest of the event is decided: in
  `record`, under the recommendation lock.
- Unsave from a card or the detail page never depends on the recommendation still existing.
- One recommendation read per feedback, save or dismiss request.

**Non-Goals:**

- De-duplicating opens (FB-2) and dropping `count` from later cursor pages (FB-6): both accepted.
- Changing `DELETE /recommendations/{id}/save` or any response shape.

## Decisions

### D1: Check relevance in `record` after the recommendation lock (FB-1)

`record(user, recommendation, action, *, issue_id=None)` runs these steps:

1. Lock the recommendation (`_current(lock=True)`). If it is gone: no event, `False`, as today.
2. For `opened_issue`, lock the issue by pk, then read
   `RecommendedIssue(recommendation=current, issue_id=issue_id)`. If the issue is missing or
   not linked, raise `IssueNotRelevant`. An issue a refresh deleted meanwhile took its
   `RecommendedIssue` rows with it (cascade), so it is no longer relevant. This replaces the old
   silent `False`, found while implementing.
3. Store the event.

The view maps `IssueNotRelevant` to the same 400 `{"issue_id": ...}` it raises now.

The recommendation lock is the right guard. A generation holds it while it rewrites the
relevant issues, so after `_current(lock=True)` there are only two cases:

- the generation has committed, and the read sees the new set;
- the generation has not reached this recommendation yet, and it waits for our commit.

Either way, the check and the insert see one consistent set. No new lock is needed, and the lock
order is unchanged: recommendation, then issue.

Alternatives considered:

- *Keep the view check and re-check in the service.* Two copies of one rule.
- *Return `False` (no event, 204) when the issue left.* That would hide an id that was never
  relevant, and the spec requires a 400 for that case. An issue dropped at the same moment *is*
  no longer relevant, so the 400 is consistent with the spec.

### D2: Unsave by repository id from the SPA (FB-3)

The unsave side of `useSaveToggle` takes `{ id, repositoryId }`. It calls
`DELETE /saved/{repositoryId}`, and keeps the optimistic update and rollback keyed by `id`.
The save side keeps `POST /recommendations/{id}/save`: saving needs a live, undismissed
recommendation, and a 404 there is correct.

Callers already have `recommendation.repository_id`. After the call, the mutation invalidates
`savedKey` as it does now.

Alternative considered: make `SaveView.delete` fall back when the recommendation is gone. It
cannot. The pk of a deleted recommendation no longer names a repository, so the server cannot
tell which save to remove.

### D3: Light ownership check in the views (FB-5)

`_own_recommendation` becomes
`get_object_or_404(Recommendation.objects.only("pk", "repository_id"), pk=pk, developer__user=user)`.
The services already re-read what they need:

- `record` and `save` use `_current` (with joins).
- `dismiss` currently reads `recommendation.repository`. It changes to take the repository id,
  then loads the repository once with `_current_recommendation` inside its transaction.

`SaveView.delete` uses only `repository_id`.

The service signatures stay `Recommendation`-typed. Callers pass the light instance, and the
services read nothing beyond pk and `repository_id` before their own re-read. One test guards
this with `django_assert_num_queries`.

## Risks / Trade-offs

- [A deferred field read on the light instance triggers a hidden query] → the query-count tests
  per endpoint fail if a service touches `recommendation.repository` before its re-read.
- [Older SPA builds still call `DELETE /recommendations/{id}/save`] → that endpoint is unchanged,
  and the 404 case is the old behavior.
- [`IssueNotRelevant` raised inside `transaction.atomic`] → raised before any write, so the
  rollback discards nothing.

## Migration Plan

No migration or setting. Patch release 0.12.53. Rollback is a plain revert.
