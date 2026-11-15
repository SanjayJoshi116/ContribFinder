## Why

Review sweep of `apps/frontend/src/features/feedback/` (`api.ts`, `RecommendationActions.tsx`,
`SavedPage.tsx`, `messages.ts`). `/code-review` reported 10 findings, each checked against the
code (FBK-1…FBK-10 in `Bug_Backlog.md`, batch 66). Two duplicate rows already planned in
`recommendations-view-review-fixes` (FBK-6 = REC-2, FBK-7 = REC-4). `/security-review` found
nothing: every save, unsave, dismiss, restore and list endpoint is scoped to the user, CSRF is
enforced, and the dismiss body accepts only a reason from a fixed list.

The main problems: a failed action restores a whole-list snapshot and brings back other cards'
confirmed dismissals (FBK-1); every failure except a failed undo is silent (FBK-5); and the undo
notice can carry one project's result to the next, or close before a slow undo reports
(FBK-2, FBK-4).

## What Changes

- **FBK-1** Rollback reverts only the recommendation the failed mutation touched: the saved flag
  for save/unsave, and re-insertion at its old position for dismiss (when not already present).
  The detail entry is reverted as before.
- **FBK-2** `DismissUndo` is keyed by the dismissed repository, so each dismissal gets fresh
  mutation state.
- **FBK-3** The detail page navigates after a confirmed dismissal only while it is still mounted.
- **FBK-4** The undo window does not close while a restore is pending. A failed restore keeps the
  notice, with its error, for 10 seconds from the failure.
- **FBK-5** Inline error text for failed save, unsave, dismiss (card and detail), remove,
  restore and "Show more". It is cleared on retry.
- **FBK-6, FBK-7** Duplicates of REC-2 and REC-4, fixed by `recommendations-view-review-fixes`.
- **FBK-8** `SavedPage` gates both lists with `Loaded`.
- **FBK-9** `recommendationsRootKey` is exported from `features/recommendations/api.ts` and used in
  `useRestore` and `useUnsaveRepository`.
- **FBK-10** `snapshot` cancels both queries with `Promise.all`.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `recommendation-feedback`: ADDED "Failed feedback actions" (FBK-1, FBK-5) and "Undo notice
  lifecycle" (FBK-2, FBK-3, FBK-4). These are added rather than modified, so this delta does not
  collide with the pending `recommendations-view-review-fixes` change to "Save and dismiss in the
  interface".

## Impact

- Code: `features/feedback/api.ts`, `RecommendationActions.tsx`, `SavedPage.tsx`;
  `features/recommendations/RecommendationList.tsx` (key), `RecommendationDetailPage.tsx`
  (mounted guard), `api.ts` (exported root key).
- Tests: `feedback.test.tsx`, `recommendations.test.tsx`. `npm run e2e` runs, because the
  dismiss and undo browser flows change.
- No backend, API, OpenAPI or migration change. Apply after `recommendations-view-review-fixes`,
  which edits the same `useDismiss`, undo state and detail-page dismissal. Patch release.
