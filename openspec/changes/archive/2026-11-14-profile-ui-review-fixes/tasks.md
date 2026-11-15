## 1. Skills and interests

- [x] 1.1 PRF-1: key skills and interests by slug (D1). Test: expand Django, rerender with the same skills under new ids → still expanded; same for an interest.
- [x] 1.2 PRF-5, PRF-8, PRF-9: `SkillBar` as `<details>/<summary>`, name with `title` (D3). Tests: clicking the summary shows the evidence list; no `aria-controls`; the name element has the full name as `title`.
- [x] 1.3 PRF-7, PRF-4: `EvidenceItem`, labels in `evidence.ts`; interest rows show the observed date; `evidenceLabel` never empty (D4). Tests: interest evidence with `observed_at` shows the date; summary `{language: 2}` with `repository_count: 0` → "repository languages".
- [x] 1.4 PRF-2: `CATEGORY_ORDER` from `CATEGORY_LABELS` (D2). Test: every category of the generated enum is in the order.

## 2. Languages and names

- [x] 2.1 PRF-6: sort by bytes; fold into "Other" only with 2+ leftovers (D5). Tests: 9 languages → 9 rows, no Other; unsorted input → sorted rows; the existing 8 + 12 scenario still gives Other 4%.
- [x] 2.2 PRF-3: `CATEGORY_LIST_NAMES`; chart named "Languages by code" (D6). Test: `getByRole('list', { name: 'Language skills' })` and `{ name: 'Languages by code' }` without `within()`.
- [x] 2.3 PRF-10: `AREA_KEYS.profile` imports the profile keys (D6); `dataVersions.test.ts` passes.

## 3. Checks

- [x] 3.1 Frontend: `npm test`, `npm run lint`, `npm run typecheck`, `npm run format:check`, `npm run build`. No e2e (no browser flow change; the profile e2e spec, if it matches by list name, is updated and run).

## 4. Release

- [x] 4.1 `Bug_Backlog.md` batch 67: PRF rows marked fixed.
- [x] 4.2 `/simplify`, then `/code-review` on the fix diff; record and fix (or skipped by the owner). Skipped by the owner (2026-11-14).
- [x] 4.3 Archive (delta into `developer-profile`). Release housekeeping per CLAUDE.md §8. Commit only when the owner says so.
