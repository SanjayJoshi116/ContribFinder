## Why

The SPA refreshes derived data only when it sees a sync, discovery or generation job finish, and
otherwise keeps it for 5 minutes (`DERIVED_STALE_TIME_MS`). Data that changes with no generation
after it (a profile analysis whose discovery fails) or with no job the client watches (a
backend repository refresh changing a recommendation's activity, README or issues) stays stale
until then: `Bug_Backlog.md` Y-6, open in part since 0.12.12. The workaround from 0.12.12 makes
every finished generation (beat sweeps included) refetch the profile, skills and interests even
when nothing changed (S-8, accepted). `ideas.md` §14 "Data versions" is first in the "can ship
now" order. No ranking change.

## What Changes

- New endpoint `GET /api/v1/sync/versions`: for the signed-in user, when each data area last
  changed: `github` (synced GitHub data), `profile` (developer profile, skills, interests) and
  `recommendations` (recommendations, matched issues and saved entries, including the stored
  data of the repositories they show). Each value is a timestamp or null. Additive: OpenAPI
  stays `1.0.0`.
- The SPA keeps one data-versions query. It is fetched when the signed-in layout mounts, on
  window focus, on every route change, and right after a status fetch sees a newly finished
  job. When an area's time differs from the one it last fetched, the SPA refetches exactly that
  area's queries, once.
- Job status queries no longer refetch derived data directly: a newly finished job refetches
  the versions (and, as today, the job statuses that follow it). A finished generation no longer
  refetches the profile, skills and interests unless the profile changed (narrows S-8).
- The 5-minute stale time and the mutations' own invalidations stay as they are.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `sync-jobs`: new requirement "Data versions endpoint".
- `web-client`: "Refresh derived data on job transitions" now refreshes the data versions
  instead of the derived data; new requirement "Refresh derived data by data versions".

## Impact

- Backend: `services/data_versions.py` (new, one function per area, read-only),
  `jobs/api.py` (`DataVersionsView`), `jobs/serializers.py`, `jobs/urls.py`; tests. No
  migration, no new setting.
- Frontend: `src/app/dataVersions.ts` (query, area → query keys, comparison),
  `src/app/jobTransitions.ts` callers in `features/sync`, `features/discovery`,
  `features/recommendations`; `routes/SignedInLayout.tsx`; `src/api/openapi.json` and
  `schema.d.ts` regenerated; tests.
- `Bug_Backlog.md` Y-6 fixed, S-8 narrowed; `ideas.md` §14 item to "Shipped".
- Release: patch 0.12.27. Docs: CLAUDE.md §7 shipped entry and §6 client note, CHANGELOG,
  features, README status line.
