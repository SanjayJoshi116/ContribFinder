## Why

Each detail page (`RecommendationDetailPage`, `IssueDetailPage`) reads `:id` with `useParams`,
parses it with `positiveId`, calls its query hook with `id ?? 0` as a disabled sentinel, and
renders its own "doesn't point to" dead end. The hooks guard `enabled: Number.isInteger(id) && id
> 0` only because of that sentinel. One route wrapper that validates once would hand each page a
plain positive number, and the next detail route (`ideas.md` §14, §18 detail pages) would get the
check for free.

## What Changes

- New `RouteId` route element (`src/routes/RouteId.tsx`): reads `:id`, validates it with
  `positiveId`, renders `DeadEnd` with the route's message for an invalid id, otherwise renders the
  page with `id` as a prop, keyed by the id.
- `RecommendationDetailPage` and `IssueDetailPage` take `{ id: number }`; no `useParams`, no
  `positiveId`, no sentinel, no invalid-id branch.
- `useRecommendation` and `useIssue` drop the `enabled` sentinel guard.
- `routes.tsx` wraps both detail routes.
- No behavior change: same messages, same dead end, no request for an invalid id (existing tests
  in `recommendations.test.tsx` stay as they are and must pass).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The invalid-id behavior is already specified (`recommendations-view` "Repository detail",
`issue-matching` issue detail page) and does not change; this is a refactor (`skip_specs`).

## Impact

- `apps/frontend/src/routes/` (new `RouteId.tsx`, `routes.tsx`),
  `features/recommendations/RecommendationDetailPage.tsx`, `features/recommendations/api.ts`,
  `features/issues/IssueDetailPage.tsx`, `features/issues/api.ts`, their tests.
- No backend, API, OpenAPI, e2e selector or dependency change.
