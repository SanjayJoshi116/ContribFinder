## Why

The review sweep's sixth module, the top-level `apps/backend/services/*.py` (`Bug_Backlog.md`
batch 31, SVC-1…SVC-10), found that account deletion never purges the deleted user's cached
GitHub responses (the purge reads `user.pk` after `user.delete()`), that a cancelled sync can
write cache entries after the purge, that a rerun requested during a generation is lost when that
run fails, that saves and dismissals never move the data version other tabs refresh by, and
several locking, robustness and efficiency defects. The security review of the module found
nothing.

## What Changes

- SVC-1: the cache purge captures the user id before the user is deleted; account deletion purges
  `github:etag:<id>:*` like delete-data and disconnect.
- SVC-6: a second purge runs in the background after cancelled workers have had time to notice the
  cancellation, so entries an in-flight request wrote after the first purge go too.
- SVC-5: a generation requested while one is running is followed by another generation whether the
  running one completes or fails.
- SVC-9: the `recommendations` data version also moves when the user saves, unsaves, dismisses or
  restores a repository.
- SVC-2: an `opened_issue` event locks its issue (after the recommendation) and is not stored when
  the issue is gone.
- SVC-3: orphan cleanup locks the candidate repositories in pk order before deciding which are
  orphans.
- SVC-4: ending jobs locks them in pk order.
- SVC-7: event snapshots (rank, match label, config version) come from the row read under the lock.
- SVC-8: `claim_job` returns None when the job was deleted after the claim.
- SVC-10: orphan cleanup counts deleted repositories from the delete itself.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `recommendation-engine`: "Recommendation generation job" (a requested rerun also follows a
  failed run).
- `sync-jobs`: "Data versions endpoint" (`recommendations` includes the user's latest save,
  unsave, dismissal or restore).

## Impact

- `apps/backend/services/{data_deletion,feedback,jobs,data_versions}.py`,
  `recommendations/tasks.py`, a GitHub cache purge task, tests.
- Migration `feedback.0006` (partial index for the latest list change, added after `/simplify`);
  no API shape change (OpenAPI `1.0.0`), no ranking change, no frontend change
  (the SPA already maps saved and dismissed lists to the `recommendations` area).
