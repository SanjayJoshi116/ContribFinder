## 1. Fixes

- [x] 1.1 E2EC-1: `sessionId(user, testInfo)` refuses `repeatEachIndex > 0` for data-changing
  users and explains a missing retry copy (D1); comment above `RETRIES`; README line.
- [x] 1.2 E2EC-3: one `SERVE` with `--host localhost` for both server branches (D2).
- [x] 1.3 E2EC-4: fixture comment (D3).
- [x] 1.4 E2EC-6: `configDefaults.exclude` plus `e2e/**`, `dist-e2e/**` (D4); the now-redundant
  `/// <reference types="vitest/config" />` removed (lint: the import provides the types).
- [x] 1.5 E2EC-7: canary checks every taken entry (D5).

## 2. Backlog

- [x] 2.1 `Bug_Backlog.md` batch 47: E2EC-1, E2EC-3, E2EC-4, E2EC-6, E2EC-7 fixed (0.12.58);
  E2EC-2, E2EC-5 stay accepted; sweep text updated.

## 3. Checks

- [x] 3.1 `npm run e2e` (all specs pass, canary included); `npx playwright test --repeat-each 2
  e2e/data.spec.ts` fails with the D1 message.
- [x] 3.2 Frontend: `npm test`, `npm run lint`, `npm run typecheck`, `npm run format:check`,
  `npm run build`.
- [x] 3.3 `openspec validate e2e-config-review-fixes --strict`.

## 4. Release

- [x] 4.1 `/simplify`, then `/code-review` on the fix diff; record and fix (or the owner skips
  this step) — skipped by the owner (2026-11-03).
- [x] 4.2 Archive; release housekeeping (CLAUDE.md §8, 0.12.58); commit only when the owner says
  so.
