## Context

Findings and verdicts are in `Bug_Backlog.md` (batch 67, PRF-1…PRF-10). Relevant facts:

- `analysis.py` deletes `profile.skills` and `profile.interests`, then `bulk_create`s them, on
  every analysis, so the row ids change. The `profile` data version refetches `['profile','skills']`
  and `['profile','interests']`.
- `CategoryEnum` has 7 values, and `CATEGORY_ORDER` lists the same 7.
- `SkillEvidence.repository` is `SET_NULL`, but no app code deletes `Repository` rows (lifecycle
  releases names instead). `repository_count` counts only evidence with a repository.
- `aggregate_languages` sorts by bytes descending, then name.
- `InterestEvidence` has `observed_at` in the API. `InterestList` does not render it.
- `LanguageChart`'s list and the language skill list are both named "Languages".

## Goals / Non-Goals

**Goals:** the behavior in the spec delta; one evidence row component; no backend change.

**Non-Goals:** keeping row ids stable in the backend (delete-and-recreate is the analysis's
design); an expand-all control.

## Decisions

### D1. Keys by slug (PRF-1)

`key={skill.skill.slug}` and `key={interest.slug}`. Slugs are unique per profile (one row per
skill or interest). `<details>` keeps its `open` attribute across re-renders of the same element.
With D3, React state no longer holds the open state for skills either.

### D2. Category order from labels (PRF-2)

`export const CATEGORY_ORDER = Object.keys(CATEGORY_LABELS) as SkillCategory[]`. Display order is
the object's key order, which is unchanged. A test asserts every enum value in the schema fixture
appears.

### D3. Native disclosure for skills (PRF-5, PRF-8, PRF-9)

```tsx
<li><details><summary className="grid ...">chevron · name(title) · bar · label</summary>
  <SkillEvidenceList .../></details></li>
```

The chevron rotates with `group-open:rotate-90` (Tailwind `group` on `details`). This removes
`useState`, `useId` and `aria-controls`. The evidence list is always rendered inside
`<details>`, which hides it natively while closed. Evidence counts per skill are small.

### D4. Shared evidence row (PRF-7, PRF-4)

`evidence.ts` exports `SKILL_SOURCE_LABELS` and `INTEREST_SOURCE_LABELS`. `EvidenceItem({ label,
repository, detail, observedAt })` lives in `features/profile/EvidenceItem.tsx`, and both lists
map to it. `evidenceLabel` returns `"repository languages"` when the parts are empty and
`by_source.language > 0`, otherwise `"evidence recorded"` (never empty).

### D5. Language rows (PRF-6)

Sort a copy by `bytes` descending, then name. If `languages.length <= MAX_ROWS + 1`, return all of
them, otherwise the top `MAX_ROWS` plus "Other".

### D6. Names and keys (PRF-3, PRF-10)

`aria-label={`${CATEGORY_LABELS[category]} skills`}` would read "Languages skills", so a separate
`CATEGORY_LIST_NAMES` record holds "Language skills", "Framework skills" and so on (a `Record`, so
it is complete by type). The chart is `aria-label="Languages by code"`. In `dataVersions.ts`,
`profile: [developerProfileKey, skillsKey, interestsKey]`.
