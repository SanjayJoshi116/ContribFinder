## Why

Review sweep of `apps/frontend/src/components/` and `src/lib/` (`ExternalLink`, `DeadEnd`,
`Fact`, `Loaded`, `format`, `useScrollToHash`). `/code-review` reported 10 findings, each
checked against the code and its callers (CMP-1…CMP-10 in `Bug_Backlog.md`, batch 69). CMP-6
duplicates FBK-8. `/security-review` found nothing:
- `ExternalLink` sets `noopener noreferrer`, and every href is GitHub's own `html_url`.
- The CSP blocks inline script.
- The URL hash is used only for `getElementById`, scroll and focus.
- There are no unsafe sinks, and `cn` does no object merging.

The real gap is that no route has an error screen. Any render error, for example a time the
browser cannot parse in a formatter, replaces the app with the router's default "Unexpected
Application Error" (CMP-1). The rest are accessibility, retry and duplication issues in the
shared pieces.

## What Changes

- **CMP-1** `format*` return "Unknown" for an invalid time. A root `errorElement` (`RouteError`)
  shows "Something went wrong", Reload, and the way back to the dashboard. Partial: the backend
  always sends ISO times, so the format crash is latent, but the missing error screen is real.
- **CMP-2** `ExternalLink` calls `onOpen?.()` on click instead of passing the event. Latent: every
  caller passes an arrow function.
- **CMP-3** `useScrollToHash` records the history keys it has handled in a module-level set, so
  Back to the same entry does not scroll or focus again. Initial loads and reloads (new keys) still
  scroll. Skipping every POP was rejected, because the first page load is a POP too.
- **CMP-4** Accepted, no change: the one caller's target renders synchronously with its data. A
  retry for late targets waits for a caller that needs it.
- **CMP-5** `Loaded` shows `loading` while a failed first load is refetching (`isFetching`).
- **CMP-6** Duplicate of FBK-8 (`feedback-ui-review-fixes`).
- **CMP-7** `DetailLoaded` (in `components/Loaded.tsx`) holds the detail-page gate: data, 404 →
  gone, failed → could not load. The recommendation and issue detail pages use it.
- **CMP-8** `DeadEnd` renders an `h1` (`tabIndex={-1}`, focused on mount) and an optional
  "Try again" (`onRetry`). `DetailLoaded` passes `refetch` for a failed load.
- **CMP-9** `Fact`'s `<dd>` gets `min-w-0 break-words`.
- **CMP-10** `components/Loading.tsx` (`role="status"`) replaces the copied "Loading…" paragraphs,
  and `Loaded` uses it as its default.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `web-client`: ADDED "Render failures and dead ends" (CMP-1, CMP-3, CMP-5, CMP-8, CMP-9).

## Impact

- Code: `components/{ExternalLink,DeadEnd,Fact,Loaded}.tsx`, new `components/{Loading,RouteError}.tsx`;
  `lib/{format,useScrollToHash}.ts`; `routes/routes.tsx` (`errorElement`); the detail pages; the
  pages that copied "Loading…".
- Tests: components and lib tests, the detail pages, and a render-error test. `npm run e2e` runs,
  because the detail-page dead ends and the route error screen are browser flows.
- No backend, API or migration change. Patch release after `pipeline-progress-review-fixes`.
  Apply after `feedback-ui-review-fixes`, which already moves `SavedPage` to `Loaded`.
