## 1. List

- [x] 1.1 REC-1: unknown filter value shown as its own option; "Clear filters" in the form and beside the invalid-filter alert (D1). Tests: `/app?language=ruby` → select shows ruby, Clear filters → URL without filters; `/app?match=foo` → alert with Clear filters.
- [x] 1.2 REC-2: `useDismiss.onSettled` invalidates `recommendationListKey` (D2). Test: page 1 with `next`, dismiss its only card → after settle the refetched page is shown, not the empty message; the existing "last card on page 2" test still passes.
- [x] 1.3 REC-3: emptied page shows "Loading…" while a dismissal is pending (D2). Test: pending dismiss of the only card → no empty-state text.
- [x] 1.4 REC-4: navigation state cleared on mount (D3). Test: render `/app` with `{dismissed}` state → notice shown and history state replaced with null; remount with the same entry → no notice.
- [x] 1.5 REC-5: placeholder results `aria-busy`, dimmed, page buttons disabled (D4). Test: click Next with a delayed page 2 → Next and Previous disabled, results `aria-busy="true"`.

## 2. Detail page

- [x] 2.1 REC-6: card links pass `from`; Back and after-dismiss use `/app${from}` (D5). Tests: open from `?language=rust&page=3` → Back link `href` is `/app?language=rust&page=3`; dismiss → lands there with the Undo notice; no state → `/app`; a `from` not starting with `?` is ignored.
- [x] 2.2 REC-7: language share as text (D6). Test: shares 0.52 / 0.476 / 0.004 → "52%", "48%", "under 1%".

## 3. Messages

- [x] 3.1 REC-8: export `ActivityLabel`, `RepositorySize` from `src/api/types.ts`; type `ACTIVITY_TEXT`, `SIZE_TEXT` with them (D6).
- [x] 3.2 REC-9: `SIZE_OPTIONS` from `SIZE_TEXT` (includes `unknown`). Test: the size select lists four options.
- [x] 3.3 REC-10: `difficultyText` uses `DIFFICULTY_TEXT.unknown`.

## 4. Checks

- [x] 4.1 Frontend: `npm test`, `npm run lint`, `npm run typecheck`, `npm run format:check`, `npm run build`.
- [x] 4.2 `npm run e2e` (dismiss/undo and back flows change); add a spec for Back keeping filters if the dismiss spec does not cover it.

## 5. Release

- [x] 5.1 `Bug_Backlog.md` batch 65: REC rows marked fixed.
- [x] 5.2 `/simplify`, then `/code-review` on the fix diff; record and fix (or skipped by the owner). Owner: marked done without a separate run.
- [x] 5.3 Archive (deltas into `recommendations-view`, `recommendation-feedback`). Release housekeeping per CLAUDE.md §8. Commit only when the owner says so.
