## Why

The full review sweep of `apps/frontend/src/features/issues/` (batch 46 of `Bug_Backlog.md`,
FI-1…FI-10) found that the issue detail page explains a contribution type with a label the issue
does not carry, replaces the issue being read with a dead end when a background refetch fails,
misses middle-click opens in the feedback report, and words "no technologies" as missing
evidence. It also found two pieces of display code copied across pages.

## What Changes

- **FI-1**: the contribution type basis names the category of the label that decided it
  ("From a documentation label"), not a label name the issue may not have. Frontend only; the
  stored evidence keeps the canonical label.
- **FI-2, FI-4**: the difficulty basis skips signals it does not know and reads the signals only
  when they are a list; a test pins the known signals to the backend classifier's.
- **FI-3**: a failed refetch of an issue keeps the page; the dead end shows only without data, or
  for a 404 (the issue is no longer relevant).
- **FI-6**: opening an issue or a repository on GitHub with the middle mouse button records the
  same `opened_issue` / `opened_repository` event as a click, through one shared external link
  component. "Open link in new tab" from the context menu stays unrecorded (the browser sends no
  event).
- **FI-7**: an issue that mentions no technology says "No technologies mentioned".
- **FI-10**: one `Fact` component (optional note) in `src/components` and one medium-date
  formatter in `src/lib`, used by the issue and recommendation detail pages, the saved list and
  the skill evidence.
- No change: **FI-5, FI-8, FI-9** (false positives, reasons in `Bug_Backlog.md`).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `issue-matching`: "Issue detail page" (contribution type basis wording; no technologies).
- `recommendation-feedback`: "Feedback events" (a middle-click open counts as following the link).
- `web-client`: "Failed refresh keeps the page" (also the issue detail page).

## Impact

- `apps/frontend/src/features/issues/` (`evidence.ts`, `IssueDetailPage.tsx`, tests),
  `features/recommendations/RecommendationCard.tsx` and `RecommendationDetailPage.tsx` (shared
  link and `Fact`), `features/feedback/SavedPage.tsx`, `features/profile/SkillGroups.tsx` (date
  formatter), new `src/components/ExternalLink.tsx`, `src/components/Fact.tsx`,
  `src/lib/format.ts`.
- No backend, API or OpenAPI change; no ranking change. Feedback reports may count more
  `opened_*` events from now on. E2E not required (unit tests cover each fix).
