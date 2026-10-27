## Context

See proposal.md for why; requirements are in `specs/sync-jobs` and `specs/web-client`.
- Every status query (`useSyncStatus`, `useDiscoveryStatus`, `useRecommendationStatus`) runs
  `fetchStatusAndRefresh` (`src/app/jobTransitions.ts`) in its `queryFn`: it compares with the
  cached previous status and starts a refresh callback once per newly finished job. Today the
  callbacks invalidate `['profile']` (sync, generation), `['jobs']` (sync) and the generation
  status (discovery).
- Derived query keys all live under `['profile', ...]`: `github`, `repositories` (GitHub data);
  `developer`, `skills`, `interests` (profile); `recommendations` (list, details), `issues`,
  `saved`, `dismissed` (recommendations and feedback). Default `staleTime` 5 minutes;
  TanStack's `refetchOnWindowFocus` refetches stale queries on focus.
- Backend times already stored: `SyncJob.completed_at` (`services.jobs.last_completed(user,
  job_type)`), `DeveloperProfile.analyzed_at`, and per repository the six part times
  `staleness.PART_FIELDS` (`synced_at`, `readme_synced_at`, …, `issues_synced_at`).
  `Recommendation.repository` and `SavedRepository.repository` both use related names
  (`recommendations`, `saves`).
- `jobs/urls.py` is mounted at `/api/v1/sync/` (today only `status`).

## Goals / Non-Goals

**Goals:**
- One cheap read that tells the SPA which derived areas changed, built from times already
  stored.
- One place in the SPA that turns a changed area into invalidations.

**Non-Goals:**
- Polling the versions on a timer, server push or WebSockets.
- Per-repository or per-query versions.
- Changing the default stale time or the mutations' own invalidations.
- A version for the discovery pool (not shown outside the discovery status, which polls).

## Decisions

**D1. Versions are derived from existing timestamps; no new column or table.**
- `services/data_versions.py`: `versions(user) -> DataVersions(github, profile,
  recommendations)`. `github` = `last_completed(user, SYNC).completed_at`; `profile` =
  `DeveloperProfile.analyzed_at` (None without a profile); `recommendations` = max of
  `last_completed(user, RECOMMENDATIONS).completed_at` and one `aggregate(Max(field) for field in
  PART_FIELDS.values())` over repositories with `id__in` (the user's recommendation repository
  ids) or `id__in` (their saved repository ids). Two `id__in` subqueries instead of an OR across
  two joins, which would multiply rows.
- *Alternative:* a `data_version` counter bumped by every writer. Rejected: every writer
  (sync, analysis, generation, shared repository refresh) would have to bump the counters of
  every affected user, and repository refreshes are shared across users; a missed bump is a
  silent stale page. Reading the times the writers already set cannot be missed.
- *Alternative:* an ETag on each derived endpoint. Rejected: needs a conditional request per
  query and still a trigger to ask; it does not tell the SPA which query to ask.

**D2. Endpoint `GET /api/v1/sync/versions` in the `jobs` app.**
- `DataVersionsView` next to `SyncStatusView`, serializer `DataVersionsSerializer` (three
  nullable `DateTimeField`s), `error_responses(401)`, operation id `sync_versions`. Additive:
  OpenAPI stays `1.0.0`. Read-only by construction (no service call writes).

**D3. Comparison inside the versions `queryFn`, like `fetchStatusAndRefresh`.**
- `src/app/dataVersions.ts`: `dataVersionsKey = ['versions']`, `AREA_KEYS` (area → query key
  prefixes: `github` → `['profile','github']`, `['profile','repositories']`; `profile` →
  `developer`, `skills`, `interests`; `recommendations` → `['profile','recommendations']`,
  `['profile','issues']`, `['profile','saved']`), `useDataVersions()` and the pure
  `changedAreas(previous, current)`. The `queryFn` reads the cached previous value, fetches, and
  starts (does not await) the invalidations of every changed area. No previous value → nothing
  invalidated, so the first fetch and the first fetch after data deletion refetch nothing. A
  failed fetch throws before comparing. One fetch, one comparison, however many observers.
- "Changed" means *differs*, not *newer*: a dismiss can lower the recommendations time, and one
  refetch then is harmless.
- `['versions']` is outside `['profile']` and `['jobs']`, so no refresh ever invalidates the
  query that triggered it. `dismissed` stays out of every area: it changes only by the user's own
  actions, which invalidate it.
- *Alternative:* keep the last seen versions in a React ref or Zustand. Rejected: the query cache
  already holds the previous value per fetch, and the status queries use the same pattern.

**D4. Triggers.**
- `SignedInLayout` calls `useDataVersions()` (mount; `staleTime: 0`, so a window focus
  refetches it) and, in an effect on `useLocation().key`, refetches it on every route change
  except the first render (the mount fetch covers that).
- The status queries' refresh callbacks become: sync → versions and `['jobs']`; discovery →
  versions and the generation status; generation → versions. `fetchStatusAndRefresh` itself is
  unchanged.
- Delete-data and account deletion also remove `['versions']`, so the next fetch is a first
  fetch again; sign-out already clears the cache on the landing page.

## Risks / Trade-offs

- [A background refresh is seen only on the next focus, route change or job] → Accepted: the
  spec scenarios need no timer, and the 5-minute stale time still bounds how long a page stays
  open on old data.
- [One more request per route change and focus] → One indexed read: three small queries plus
  one aggregate over at most `RECOMMENDATIONS_TOP_N` + saved rows.
- [Times written in one transaction but read in another can arrive just after a versions read]
  → The next trigger sees the new time; the SPA never misses a change, it may only see it one
  trigger late.
- [The generation status no longer refreshes the profile] → The sync and analysis set
  `analyzed_at`, so the `profile` area covers every re-analysis (narrows S-8 as intended).

## Migration Plan

- No migration, no setting. Deploy backend and frontend together (the SPA is served with the
  backend); an older SPA ignores the new endpoint.
- Rollback: revert the release.
