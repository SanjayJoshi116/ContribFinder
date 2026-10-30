## Context

`positiveId(param)` (`src/lib/utils.ts`) accepts only `^[1-9]\d*$` within the safe integer range.
Both detail pages call their query hook before the invalid-id return (hooks cannot be
conditional), hence the `id ?? 0` sentinel and the hook-side `enabled` guard.
`RecommendationDetailPage` also keeps a `viewed` ref keyed by the loaded id so one visit records
one `viewed` event, including when the route moves from one id to another.

## Goals / Non-Goals

**Goals:** validate `:id` in one place; pages and hooks take a valid number; identical behavior
and messages.

**Non-Goals:** route loaders or a data router migration; changing the dead-end text or layout
(that is §18); validating other params.

## Decisions

### D1. A route element, not a higher-order component

```tsx
// routes.tsx
{ path: '/app/recommendations/:id',
  element: <RouteId invalid="This link doesn't point to a recommendation.">
             {(id) => <RecommendationDetailPage id={id} />}
           </RouteId> }
```

`RouteId({ invalid, children: (id: number) => ReactNode })` calls `useParams()`, then
`positiveId(params.id)`; `null` → `<DeadEnd message={invalid} />`, else
`<Fragment key={id}>{children(id)}</Fragment>`. A render prop keeps the page's prop type checked
by TypeScript and keeps the message next to the route. Alternative `withRouteId(Page, message)`:
rejected, it hides the page's props and reads worse in `routes.tsx`.

### D2. Remount per id

Keying by id gives each id a fresh page instance, as a full navigation would. The `viewed` ref
logic stays (it also guards React StrictMode double effects), but no longer has to cope with a
changing id inside one instance. The query cache is unaffected (keys include the id).

### D3. Hooks trust their argument

`useRecommendation(id)` and `useIssue(id)` drop `enabled`; their only callers now pass a validated
id. Keeping a guard "just in case" would hide a caller bug as a page that loads forever.

## Risks / Trade-offs

- A future caller of the hooks with an unchecked number would send a request: acceptable, the
  backend answers 404 and the page shows its dead end. Typed `id: number` plus review covers it.
- The remount resets scroll-to-hash and local state on id change; that is the intended behavior
  for a different recommendation.

## Migration Plan

None. Frontend-only refactor; rollback is a revert.
