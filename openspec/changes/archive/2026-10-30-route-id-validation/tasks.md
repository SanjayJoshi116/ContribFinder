## 1. Route wrapper

- [x] 1.1 `src/routes/RouteId.tsx`: `RouteId({ invalid, children })` validates `:id` with `positiveId`, renders `DeadEnd` for an invalid id, else `children(id)` keyed by the id
- [x] 1.2 `routes.tsx`: wrap `/app/recommendations/:id` and `/app/issues/:id` with their current dead-end messages

## 2. Pages and hooks

- [x] 2.1 `RecommendationDetailPage({ id })`: drop `useParams`, `positiveId`, the `id ?? 0` sentinel and the invalid-id branch
- [x] 2.2 `IssueDetailPage({ id })`: same
- [x] 2.3 `useRecommendation`, `useIssue`: drop the `enabled` sentinel guard
- [x] 2.4 Check no other caller of the two hooks or of `positiveId` remains outside `RouteId`

## 3. Tests

- [x] 3.1 Existing invalid-id table in `recommendations.test.tsx` passes unchanged (dead end, back link, no request)
- [x] 3.2 `RouteId` unit test: valid id renders the child with a number; invalid ids (`abc`, `0`, `1.5`, `0x1f`, ` 7`, unsafe integer) render the dead end
- [x] 3.3 Moving from `/app/recommendations/1` to `/app/recommendations/2` records one `viewed` per id
- [x] 3.4 `npm test`, `npm run lint`, `npm run typecheck`, `npm run format:check`, `npm run build` (e2e not needed: no browser flow or selector changes)

## 4. Release

- [x] 4.1 Archive (skip_specs); `ideas.md` moves the §14 route-level ids item to Shipped
- [x] 4.2 Release housekeeping (CLAUDE.md §8): patch bump, CHANGELOG, features.txt, README, CLAUDE.md entry
