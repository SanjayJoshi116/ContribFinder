## 1. Backend (D1, D2)

- [x] 1.1 `services/data_versions.py`: `DataVersions(github, profile, recommendations)` and
  `versions(user)` from `last_completed` (SYNC, RECOMMENDATIONS), `DeveloperProfile.analyzed_at`
  and one `Max` aggregate per `staleness.PART_FIELDS` field over the user's recommended or saved
  repositories (two `id__in` subqueries).
- [x] 1.2 `jobs/serializers.py` `DataVersionsSerializer`; `jobs/api.py` `DataVersionsView`
  (`operation_id="sync_versions"`, `error_responses(401)`); `jobs/urls.py` `versions`.
- [x] 1.3 Tests: the six `sync-jobs` scenarios (synced user, repository refreshed after the
  generation, analysis without a generation, never synced, another user's data, read only:
  no job started, no row changed); a saved-only repository counts; FAILED jobs do not count;
  401 when signed out; query count bounded.
- [x] 1.4 `npm run api:sync` (from `apps/frontend`); commit `openapi.json` and `schema.d.ts`;
  OpenAPI version stays `1.0.0`.

## 2. Frontend (D3, D4)

- [x] 2.1 `src/app/dataVersions.ts`: `dataVersionsKey = ['versions']`, `AREA_KEYS`, pure
  `changedAreas(previous, current)`, `useDataVersions()` (`staleTime: 0`; compares in its
  `queryFn` and starts, not awaits, the invalidations; no previous value → none). `DataVersions`
  type exported from `src/api/types`.
- [x] 2.2 `routes/SignedInLayout.tsx`: call `useDataVersions()`; refetch it on route change
  (`useLocation().key`), skipping the first render.
- [x] 2.3 Refresh callbacks: `useSyncStatus` → versions and `['jobs']`; `useDiscoveryStatus` →
  versions and the generation status; `useRecommendationStatus` → versions only. Update their
  doc comments and the `['profile']` key comments in `features/*/api.ts`.
- [x] 2.4 Delete-data and account deletion (`features/auth/api.ts`) also remove
  `dataVersionsKey`.
- [x] 2.5 Tests: `changedAreas` table; the `web-client` scenarios (returning to the dashboard,
  sync finishes, short generation between polls, two components show the generation status,
  generation without a profile change, repository refreshed in the background, analysis whose
  discovery fails, nothing changed, first fetch); a failed versions fetch refetches nothing;
  the first fetch after delete-data refetches nothing. Adjust existing job-transition tests that
  expect `['profile']` to be invalidated directly.

## 3. Verification and housekeeping

- [x] 3.1 Backend `ruff check`, `ruff format --check`, `mypy`, `pytest`; `git diff --exit-code
  apps/backend/evaluation/baselines.json`. Frontend `lint`, `format:check`, `typecheck`, `test`,
  `build`. `npm run e2e` (the signed-in layout and refresh flows change).
- [x] 3.2 Manual: with `npm start`, open a recommendation, run `npm run manage --
  reanalyze_profiles` and refocus the window: skills refetch once; switching pages with nothing
  changed sends only the versions request.
- [x] 3.3 Docs: `Bug_Backlog.md` Y-6 fixed and S-8 narrowed; `ideas.md` §14 to "Shipped";
  CLAUDE.md §6 client note (versions query) and §7 shipped entry (K-1 carry-over unchanged);
  `features.txt`.
- [x] 3.4 Release housekeeping (CLAUDE.md §8): patch 0.12.27; `CHANGELOG.md`, README status
  line, `check:version`, lockfiles.
