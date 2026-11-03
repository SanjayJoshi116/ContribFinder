## 1. Issue analysis wording

- [x] 1.1 FI-1: `contributionBasis` names the label's category (D1).
  - Test: `{by: "label", value: "documentation"}` → "From a documentation label".
  - Test: keyword basis unchanged.
- [x] 1.2 FI-2, FI-4: `difficultyBasis` uses `SIGNAL_TEXT`, drops unknown signals, guards a
  non-array (D2).
  - Test: an unknown signal is skipped; `signals: {}` gives `[]`.
  - Backend test `tests/test_issue_signal_wording.py`: the signals `classify.difficulty` writes
    equal the `SIGNAL_TEXT` keys in `evidence.ts` (moved from Vitest, see design D2).
- [x] 1.3 FI-7: "No technologies mentioned" when the list is empty (D5).
  - Test: issue page with no technologies shows it.

## 2. Issue page refetch

- [x] 2.1 FI-3: dead end only for a 404 or without data (D3).
  - Test: refetch failing with 503 keeps the issue shown.
  - Test: refetch answering 404 shows the "no longer among your relevant issues" message.

## 3. Shared components

- [x] 3.1 FI-6: `ExternalLink` with `onOpen` on click and middle-button `auxclick` (D4); used by
  the issue detail page, the recommendation card and the recommendation detail page.
  - Test: middle click on the issue link posts one `opened_issue`.
  - Unit test `ExternalLink.test.tsx`: click and middle click call `onOpen`, right click does
    not (covers the card and the recommendation detail page, which use it).
  - Existing click tests pass.
- [x] 3.2 FI-10: `src/components/Fact.tsx`, `src/lib/format.ts` `formatDate`; local copies
  removed from both detail pages, `SavedPage` and `SkillGroups` (D6).
  - Existing page tests pass unchanged.

## 4. Backlog

- [x] 4.1 `Bug_Backlog.md` batch 46: FI-1…FI-4, FI-6, FI-7, FI-10 fixed (0.12.57; FI-4 guard with
  FI-2); FI-5, FI-8, FI-9 stay false positives; sweep text updated.

## 5. Checks

- [x] 5.1 Frontend (`apps/frontend`): `npm test`, `npm run lint`, `npm run typecheck`,
  `npm run format:check`, `npm run build`; backend `pytest`, `ruff`, `mypy` (the new backend
  test). No API change; e2e not required.
- [x] 5.2 `openspec validate issue-detail-review-fixes --strict`.

## 6. Release

- [x] 6.1 `/simplify`, then `/code-review` on the fix diff; record and fix (or the owner skips
  this step) — skipped by the owner (2026-11-03).
- [x] 6.2 Archive (syncs the three deltas); release housekeeping (CLAUDE.md §8, 0.12.57); commit
  only when the owner says so.
