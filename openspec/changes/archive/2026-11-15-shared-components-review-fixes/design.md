## Context

Findings and verdicts are in `Bug_Backlog.md` (batch 69, CMP-1…CMP-10). Relevant facts:

- `createBrowserRouter(routes)` in `main.tsx`; no route has an `errorElement`, and the app has no
  error boundary.
- `format*` call `Intl.DateTimeFormat.format(new Date(time))`, which throws `RangeError` for an
  invalid date. DRF serializes times as ISO 8601.
- `ExternalLink` sets `onClick={onOpen}`. All 3 callers pass `() => recordFeedback(...)`.
- `useScrollToHash` keeps `done` in a `useRef`, so a remount (Back) starts empty. React
  Router's first navigation is a POP too.
- `Loaded` falls back to `failed` whenever `isError` is set, also while a refetch runs.
- `RecommendationDetailPage` and `IssueDetailPage` each hand-code pending → (no data or 404) →
  `DeadEnd` (gone or could not load) → data.
- "Loading…" paragraphs appear in 11 places.

## Goals / Non-Goals

**Goals:** the behavior in the spec delta; one detail gate; one loading element.

**Non-Goals:** error reporting to a service (Sentry is post-MVP); retrying a hash target that
renders late (CMP-4 accepted).

## Decisions

### D1. Route error screen and safe formatting (CMP-1)

`RouteError` never shows the error's text (it could carry internals). It renders
an `h1` "Something went wrong", a Reload button (`location.reload()`), and a link to `/app`. It is
set as `errorElement` on the root route, so it covers every signed-in and public route. In
`format.ts`, a helper `parse(time)` returns null for `Number.isNaN(date.getTime())`, and each
formatter returns `'Unknown'` then.

### D2. Handled hash keys (CMP-3)

A module-level `const handled = new Set<string>()` replaces `done`. The effect skips when
`handled.has(key)` and adds the key once it has scrolled. A reload starts a new module (empty
set) and still scrolls. Back to an entry handled in this page session skips.

### D3. Loaded, DetailLoaded, DeadEnd, Loading (CMP-5, CMP-7, CMP-8, CMP-10)

- `Loaded` takes `query: { data, isError, isFetching? }`. With no data, `isError &&
  !isFetching` → `failed`, else `loading`.
- `DetailLoaded({ query, gone, failed, children })`: a 404 error → `<DeadEnd message={gone} />`
  (also over existing data, as today), data → children, `isError && !isFetching` →
  `<DeadEnd message={failed} onRetry={query.refetch} />`, else `<Loading />`.
- `DeadEnd({ message, onRetry })`: an `h1` holding the message, with `tabIndex={-1}` and
  focused in an effect on mount; "Try again" when `onRetry`; the dashboard link. Remove
  `role="alert"`, because the focus announces it. The detail-page tests that query
  `getByRole('alert')` move to the heading.
- `Loading({ className })`: `<p role="status" className="text-muted-foreground text-sm">Loading…</p>`.

### D4. Small fixes (CMP-2, CMP-9)

`onClick={() => onOpen?.()}`; `<dd className="min-w-0 break-words text-right">`.
