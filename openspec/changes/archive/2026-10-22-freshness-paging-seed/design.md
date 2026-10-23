## Context

See proposal.md for why. The current state of each part:

- **Y-6.** The SPA's derived queries use a 5-minute `staleTime` (`app/queryClient.ts`). A status
  query refreshes derived data through `fetchStatusAndRefresh` (`app/jobTransitions.ts`) when it
  sees a job finish:
  - sync refreshes all of `['profile']`;
  - discovery refreshes the generation status;
  - generation refreshes the recommendation list, details, issues and the saved list.
  No status query watches a standalone `profile_analysis` job. The backend still chains every
  completed analysis into a discovery (`start_discovery_after`) and every completed discovery
  into a generation (`start_recommendations_after`).
- **Y-7.** `SavedListView` and `DismissedListView` (`feedback/api.py`) use
  `FeedbackPagination(PageNumberPagination)` with page size 20 (at most 100). They order by
  `-saved_at, -pk` and `-dismissed_at, -pk`. The SPA's `usePagedList`
  (`features/feedback/api.ts`) builds `?page=N&page_size=50` itself and uses `next` only to
  know whether more pages exist. `SavedPage.tsx` uses no `count`.
- **Z-1.** `0003_seed_v2_deterministic.seed` looks only at operator configurations outside
  {v1, v2}. `unseed` returns early when v2 is inactive, which keeps the row. When v2 is active
  and has recommendations, `unseed` keeps v2 inactive and re-activates v1. When v2 is active
  with no recommendations, it deletes v2. `tests/test_seed_migrations.py` round-trips the seeds.
  The admin has an "Activate" action.

## Goals / Non-Goals

**Goals:**
- Profile data changed by any analysis shows up when its pipeline ends.
- Saved and hidden lists that are stable across concurrent changes, with no API contract break.
- A re-applied v2 seed that never overrides an activation it did not make.

**Non-Goals:**
- A data-versions endpoint (`ideas.md` §14). It stays an idea.
- Freshness for data no generation follows. For example, when a discovery fails, the profile
  stays cached for up to 5 minutes, as today.
- Cursor paging for `/recommendations`. Its list is replaced by each generation, so a cursor
  would point into a list that no longer exists.
- Server page clamping, route-level ids (`ideas.md` §14).

## Decisions

**D1. A finished generation also refreshes the profile keys (Y-6).**
- `useRecommendationStatus`'s refresh adds `developerProfileKey`, `skillsKey` and
  `interestsKey` (from `features/profile/api.ts`) to its `invalidateQueries` calls.
- *Why generation:* every analysis ends in one (analysis → discovery → generation), whoever
  started it. The generation status is already polled on the dashboard, so no new request or
  endpoint is needed.
- *Not `['profile']` as a whole:* that prefix also holds the discovery and generation status
  keys. Invalidating it from inside the generation status `queryFn` would cancel and restart
  that same fetch (`cancelRefetch`) and refetch the discovery status for nothing.
- *Alternatives:*
  - Watch `profile_analysis` jobs. Rejected: it needs a new status endpoint, plus polling for a
    job type users never start.
  - A shorter `staleTime` for profile data. Rejected: it adds refetches on every mount and
    still lags.
  - Data versions. Rejected for now: a new endpoint and polling, out of scope.
- After a sync, the profile refetches twice (once for the sync, once for the generation that
  follows). These are cheap reads, and the two jobs finish minutes apart.

**D2. Keyset pagination for saved and hidden lists (Y-7).**
- `KeysetPagination(PageNumberPagination)` in `feedback/api.py`, with a class attribute
  `time_field` (`saved_at` or `dismissed_at`). Same page sizes as today.
- Cursor:
  - Encoded as URL-safe base64 of `"<ISO-8601 time with microseconds>|<pk>"`, with padding
    stripped. Microseconds match PostgreSQL `timestamptz` precision, so the comparison is exact.
  - With `cursor`, the page filters `Q(time__lt=t) | Q(time=t, pk__lt=pk)`, slices
    `page_size + 1` to learn whether a next page exists, and ignores `page`.
  - Without `cursor`, the page is the plain page-number page (page 1, or the `page` asked for).
- Response:
  - The same `count`, `next`, `previous`, `results` as today. `count` is the unfiltered total.
  - `next` is the request URL with `cursor` set from the page's last entry (and `page`
    removed), or null when no page follows.
  - `previous` is the page-number link without a cursor, and null with one. The SPA never
    pages backwards.
- An unreadable cursor raises `InvalidCursor(APIException)`: status 400, `default_code`
  `invalid_cursor`, through the error envelope.
- `get_schema_operation_parameters` adds `cursor` to OpenAPI. The response schema is
  unchanged.
- *Alternative:* DRF `CursorPagination`. Rejected:
  - it drops `count` and refuses `page`, which is a contract change;
  - it answers 404 "Invalid cursor";
  - it positions by the first ordering field plus an offset, so equal timestamps shift again
    under concurrent changes.
- *Alternative:* de-duplicate by `repository_id` in the SPA. Rejected as the fix: it hides
  duplicates but still skips entries.
- SPA:
  - `usePagedList` uses `pageParam: string | null` (initially null) and fetches
    `${path}?page_size=50[&cursor=…]`.
  - `getNextPageParam` reads `cursor` from `new URL(last.next, location.origin)`.
  - On invalidation, TanStack v5 refetches the loaded pages one after another from
    `initialPageParam` and recomputes each cursor, so the refetched list is consistent too.

**D3. The v2 seed returns early when v2 already exists (Z-1).**
- `seed` starts with `if ScoringConfig.objects.filter(version="v2-deterministic").exists():
  return`. Otherwise it behaves as today: it creates v2, active unless an operator
  configuration is active.
- A surviving row means one of two things: an operator deactivated v2, or v2 produced
  recommendations before a rollback. Both are decisions the seed must not undo. The second
  case changes the documented outcome, which the spec delta records.
- *Alternative:* store who activated a configuration (`activated_by`). Rejected: a later schema
  migration does not exist yet when 0003 runs or re-runs, and the column would serve only this
  seed.
- *Editing an applied data migration:* Django never re-runs an applied migration, so a
  database that has applied 0003 is unaffected. Only fresh databases and re-applies after a
  rollback run the new code. The fresh-database result is unchanged: v2 is created and active.

## Risks / Trade-offs

- [The operator expects v2 back after rolling back and re-applying] → The changelog and
  CLAUDE.md say that re-activation goes through the admin "Activate" action. The seed test
  covers the case.
- [An old SPA tab still sends `page=N`] → It still works: page-number paging is unchanged
  without a cursor, and the `next` link it ignores now carries a cursor.
- [Cursor time precision] → The ISO string keeps microseconds. A round-trip test with equal
  `saved_at` values and different pks covers the tie-break.
- [Profile refetch after every generation] → Three small GETs, only when a generation finishes
  while the dashboard is open.

## Migration Plan

- No schema migration, and the data migration edit is described in D3.
- Backend and SPA can deploy in either order: the API change is additive.
- Rollback is a code revert. Cursors still in a client become unknown query parameters, which
  are ignored after a revert.
