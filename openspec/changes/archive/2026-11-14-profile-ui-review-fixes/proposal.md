## Why

Review sweep of `apps/frontend/src/features/profile/` (profile page, skills, interests, languages
chart, hooks). `/code-review` reported 10 findings, each checked against the code and the backend
analysis (PRF-1…PRF-10 in `Bug_Backlog.md`, batch 67). `/security-review` found nothing: the
three endpoints take no id and filter by the user, the serializers list their fields
explicitly, the feature only reads, and links are GitHub's `html_url` through `ExternalLink`.

The one visible bug: every re-analysis deletes and recreates the skill and interest rows
(`services/profiling/analysis.py`), so their ids change and every expanded skill or interest
collapses (PRF-1). The rest are accessibility issues, latent display gaps and duplicate code.

## What Changes

- **PRF-1** Skills and interests are keyed by catalog slug, not row id.
- **PRF-2** `CATEGORY_ORDER` is derived from `CATEGORY_LABELS`, which is a `Record` over the
  generated enum, so it is complete by type. Latent: it lists all 7 categories today.
- **PRF-3** List names: skill groups are named "<Category> skills" (e.g. "Language skills") and
  the chart "Languages by code".
- **PRF-4** `evidenceLabel` falls back to "repository languages" when no other part applies.
  Latent: repository rows are never deleted by the app, so language evidence keeps its
  repository. Only an admin delete leaves the label blank.
- **PRF-5, PRF-8** `SkillBar` becomes `<details>/<summary>` like `InterestList`. That removes
  `aria-controls` to an absent element, along with the hand-built disclosure state.
- **PRF-6** `languageRows` sorts by bytes (defensive: the backend already sorts) and folds into
  "Other" only when at least two languages are left over.
- **PRF-7** One shared `EvidenceItem` (source label, repository link, detail, observed date) is
  used by skills and interests. `SOURCE_LABELS` for both move to `evidence.ts`. Interest rows now
  show the observed date.
- **PRF-9** The skill name gets `title={name}`, and the expanded evidence list is labelled with it
  (already: "Evidence for …").
- **PRF-10** `AREA_KEYS.profile` imports the three keys from `features/profile/api.ts`.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `developer-profile`: "Profile page" (interest evidence dates, every category shown, readable
  names, expanded state kept, distinct list names, language ordering and a single leftover
  language).

## Impact

- Code: `features/profile/SkillGroups.tsx`, `InterestList.tsx`, `LanguageChart.tsx`,
  `evidence.ts`, `languages.ts`; `src/app/dataVersions.ts`.
- Tests: `profile.test.tsx` (the `within()` workaround for the duplicate "Languages" name goes),
  `dataVersions.test.ts`.
- No backend, API, OpenAPI or migration change, and no browser flow change, so no e2e run is
  needed. Patch release after `feedback-ui-review-fixes`.
