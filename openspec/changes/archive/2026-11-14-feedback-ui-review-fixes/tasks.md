## 1. Optimistic updates

- [x] 1.1 FBK-1: per-item rollback for save/unsave and dismiss (D1). Tests: save A pending, dismiss B succeeds, A fails → B still absent from every cached page, A unsaved; dismiss fails → card back at its index with the count restored; unsave of C unaffected by A's failed save.
- [x] 1.2 FBK-10: `snapshot` cancels with `Promise.all`.

## 2. Undo notice and detail page

- [x] 2.1 FBK-2: `key={dismissed.repositoryId}` on `DismissUndo` (D2). Test: failed undo of A, dismiss B → notice names B, no error, Undo enabled.
- [x] 2.2 FBK-4: notice stays open while a restore is pending; a failure extends it 10 s (D2). Tests (fake timers): Undo at 9 s, resolves at 12 s with an error → notice still shown with "Undo didn't work." at 12 s and gone at 22 s; success at 12 s → closed.
- [x] 2.3 FBK-3: detail page navigates only while mounted (D3). Test: dismiss on the detail page, navigate to `/app/saved` before resolving → location stays `/app/saved`.

## 3. Errors and the saved page

- [x] 3.1 FBK-5: inline errors for save, unsave, dismiss, remove, restore and "Show more", cleared on retry (D4). One test per control: a 500 shows the text and the control is enabled; a retry that succeeds clears it.
- [x] 3.2 FBK-8: `SavedPage` uses `Loaded` for both lists (D5); the existing loading and error tests pass.
- [x] 3.3 FBK-9: export `recommendationsRootKey`; use it in `useRestore` and `useUnsaveRepository`.

## 4. Checks

- [x] 4.1 Frontend: `npm test`, `npm run lint`, `npm run typecheck`, `npm run format:check`, `npm run build`.
- [x] 4.2 `npm run e2e` (dismiss and undo flows change).

## 5. Release

- [x] 5.1 `Bug_Backlog.md` batch 66: FBK rows marked fixed (FBK-6, FBK-7 by `recommendations-view-review-fixes`).
- [x] 5.2 `/simplify`, then `/code-review` on the fix diff; record and fix (or skipped by the owner). Skipped by the owner (2026-11-14).
- [x] 5.3 Archive after `recommendations-view-review-fixes` (ADDED requirements in `recommendation-feedback`). Release housekeeping per CLAUDE.md §8. Commit only when the owner says so.
