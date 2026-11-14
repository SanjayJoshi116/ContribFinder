## Why

Review sweep of `apps/frontend/src/features/recommendations/` (list, cards, detail, filters,
messages). `/code-review` reported 10 findings, each checked against the code, the backend
filters and the specs (REC-1…REC-10 in `Bug_Backlog.md`, batch 65). `/security-review` found
nothing. All text is rendered by React. The only external link is GitHub's `html_url`, passed
through `ExternalLink`. Detail ids go through `RouteId`, filters are sent as query parameters
under a fixed list of keys, every endpoint is scoped to the user, and CSRF is sent on every
request that changes data.

Two of the findings leave users stuck. A filter from a link that isn't one of the dropdown's
options can't be cleared without editing the URL (REC-1). Dismissing every card on page 1 shows
"No suitable projects yet" while more recommendations exist (REC-2).

## What Changes

- **REC-1** A filter value from the URL that is not one of the options is shown as its own
  selected option, and a "Clear filters" button appears whenever a filter is active. It also
  appears beside the "filters are not valid" message.
- **REC-2** A confirmed dismissal invalidates the recommendation list, so the current page
  refetches. A page 1 emptied by dismissals then shows the following recommendations. The
  page > 1 recovery is unchanged.
- **REC-3** While a dismissal is in flight, an emptied page shows "Loading…" instead of the
  empty-state message.
- **REC-4** The list reads the dismissal from navigation state and clears that state at once,
  not only when the notice closes. A reload or Back no longer brings the Undo notice back.
- **REC-5** While the list shows placeholder data (the previous key's results), the results are
  marked `aria-busy` and dimmed, and Previous/Next are disabled.
- **REC-6** Card links pass the list's search string (`?language=rust&page=3`) as navigation
  state. "Back to recommendations" and the after-dismiss navigation return to it, falling back to
  `/app`.
- **REC-7** Language rows show the share as text ("52%", "under 1%") beside the bar.
- **REC-8** `ACTIVITY_TEXT` and `SIZE_TEXT` are typed with the generated `ActivityLabelEnum` /
  `SizeEnum`, exported from `src/api/types.ts`.
- **REC-9** `SIZE_OPTIONS` is derived from `SIZE_TEXT`, so it includes `unknown`, which the
  backend accepts.
- **REC-10** `difficultyText` uses `DIFFICULTY_TEXT.unknown` instead of repeating the constant.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `recommendations-view`: "Recommendations on the dashboard" (REC-1, REC-2, REC-3, REC-5),
  "Repository detail page" (REC-6, REC-7).
- `recommendation-feedback`: "Save and dismiss in the interface" (REC-4, REC-6 after dismissing).

## Impact

- Code: `features/recommendations/RecommendationList.tsx`, `RecommendationCard.tsx`,
  `RecommendationDetailPage.tsx`, `messages.ts`; `features/feedback/api.ts` (`useDismiss`
  settles by invalidating the list); `src/api/types.ts` (two type aliases).
- Tests: `recommendations.test.tsx`, feedback tests. Playwright: dismiss and back flows change,
  so `npm run e2e` runs (existing dismiss/undo specs, plus one for back with filters).
- No backend, API, OpenAPI or migration change. Patch release after
  `services-evaluation-review-fixes`.
