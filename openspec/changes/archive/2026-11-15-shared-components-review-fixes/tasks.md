## 1. Failures

- [x] 1.1 CMP-1: formatters return "Unknown" for an invalid time; root `errorElement` `RouteError` (D1). Tests: `formatDate('nope')` → "Unknown"; a route whose component throws renders "Something went wrong" with Reload and the dashboard link.
- [x] 1.2 CMP-5: `Loaded` shows loading while a failed first load refetches (D3). Test: error then `isFetching` → "Loading…".
- [x] 1.3 CMP-7, CMP-8: `DetailLoaded`; `DeadEnd` with a focused heading and optional Try again; both detail pages use it (D3). Tests: 404 during a visit → heading focused; failed first load → Try again refetches and shows the page; existing detail tests keep passing (alert queries moved to the heading).

## 2. Links and layout

- [x] 2.1 CMP-3: module-level handled keys in `useScrollToHash` (D2). Tests: same key remounted → no second scroll; a new key → scroll.
- [x] 2.2 CMP-2: `ExternalLink` calls `onOpen()` without arguments (D4). Test: `onOpen` receives no arguments on click.
- [x] 2.3 CMP-9: `Fact` value wraps (D4).
- [x] 2.4 CMP-10: `Loading` component; replace the copied paragraphs; `Loaded` default uses it (D3).

## 3. Checks

- [x] 3.1 Frontend: `npm test`, `npm run lint`, `npm run typecheck`, `npm run format:check`, `npm run build`; `npm run e2e` (dead ends and the error screen). As run: 253 unit tests; e2e 11/11 with a new dead-end spec (`dashboard.spec.ts`, missing recommendation → focused heading).

## 4. Release

- [x] 4.1 `Bug_Backlog.md` batch 69: CMP rows marked fixed (CMP-4 accepted, CMP-6 by `feedback-ui-review-fixes`).
- [x] 4.2 `/simplify`, then `/code-review` on the fix diff: skipped by the owner.
- [x] 4.3 Archive (ADDED requirement in `web-client`). Release housekeeping per CLAUDE.md §8. Commit only when the owner says so.
