## 1. Profile refresh on a finished generation (D1, Y-6)

- [x] 1.1 `features/recommendations/api.ts` (`useRecommendationStatus`): the refresh also
  invalidates `developerProfileKey`, `skillsKey` and `interestsKey` from
  `features/profile/api.ts`, with no `['profile']` prefix invalidation (the status keys live
  under it). Check that `features/profile/api.ts` does not import from recommendations (no
  cycle).
- [x] 1.2 Test (`src/app/app.test.tsx` or the recommendations tests): when the generation status
  turns from RUNNING to COMPLETED (new job), `/profile`, `/profile/skills` and
  `/profile/interests` are fetched once, and `/sync/status` and `/discovery/status` are not
  fetched by that refresh. The "Returning to the dashboard" test still passes unchanged.

## 2. Keyset pagination for saved and hidden lists (D2, Y-7)

- [x] 2.1 `feedback/api.py`:
  - `InvalidCursor(APIException)`: 400, `default_code = "invalid_cursor"`.
  - `KeysetPagination(PageNumberPagination)`, with `time_field`, the same page sizes as
    `FeedbackPagination`, `encode`/`decode` of `"<iso>|<pk>"` (URL-safe base64, unpadded),
    the cursor filter `Q(t__lt) | Q(t=, pk__lt)`, a `page_size + 1` slice for the next page,
    `count` from the unfiltered queryset, `next` with `cursor` (and no `page`), `previous`
    null with a cursor.
  - `get_schema_operation_parameters` adds `cursor`.
  - `SavedListView` (`saved_at`) and `DismissedListView` (`dismissed_at`) use it.
    `FeedbackPagination` goes if nothing else uses it.
- [x] 2.2 Backend tests (`tests/test_feedback.py` or a new `tests/test_feedback_paging.py`):
  - 60 saves at page size 50: following `next` lists all 60 once, in order;
  - unsaving an entry of page 1 before following `next`: neither repeats nor skips;
  - a new save before following `next`: the next page does not start with an entry already
    returned;
  - equal `saved_at` values with different pks page by pk;
  - `?page=2` without a cursor returns the page-number page, with the same `count`;
  - `cursor=garbage`, a bad time and a non-numeric pk each answer 400 `invalid_cursor` in the
    error envelope;
  - the same for `/dismissed` (parametrize);
  - another user's entries never appear.
- [x] 2.3 `npm run api:sync`: the OpenAPI diff is the `cursor` parameter on `saved_list` and
  `dismissed_list` only. Commit `openapi.json` and `schema.d.ts`.
- [x] 2.4 `features/feedback/api.ts` (`usePagedList`):
  - `pageParam: string | null`, `initialPageParam: null`;
  - the path is `${path}?page_size=${LIST_PAGE_SIZE}` plus `&cursor=` when set;
  - `getNextPageParam` reads `cursor` from `new URL(last.next, window.location.origin)`, or
    returns `undefined` when there is no `next`.
  - Update the comment.
- [x] 2.5 Frontend tests (`features/feedback/feedback.test.tsx`):
  - "Show more" requests the cursor taken from `next`;
  - an unsave on page 1 followed by "Show more" shows each entry once (mock responses as the
    server would page);
  - the existing 130-saved and restore tests still pass.

## 3. v2 seed respects a stored v2 (D3, Z-1)

- [x] 3.1 `recommendations/migrations/0003_seed_v2_deterministic.py` (`seed`): return early
  when `v2-deterministic` already exists, with a comment naming both cases (operator
  deactivated it, or it was kept by a rollback because it had recommendations). Update the
  comment at the top of `seed`.
- [x] 3.2 `tests/test_seed_migrations.py`:
  - `test_reverse_and_reapply_keeps_one_active`: with `recommendations_on="v2-deterministic"`,
    `v1-deterministic` is active at the end; otherwise `v2-deterministic` is.
  - New: an operator activates v1 while v2 is stored, then 0003 is unseeded and seeded again,
    and v1 stays the only active configuration.
  - `test_operator_config_stays_active_through_v2_seed` and `test_real_migrations_round_trip`
    pass unchanged. As built: `test_v2_seed_replaces_v1` now deletes the stored v2 first (an
    upgrade is a database without v2; with v2 stored the seed returns early).

## 4. Verification and housekeeping

- [x] 4.1 Backend `ruff check`, `ruff format --check`, `mypy`, `pytest`. Frontend lint,
  format:check, typecheck, test, build, `npm run e2e`. Root `test:scripts`, `lint:scripts`,
  `format:scripts`, `check:version`.
- [ ] 4.2 Manual: with more than 50 saved projects, show page 1, unsave one in a second tab,
  then "Show more" in the first. No duplicate and no gap, and no React key warning in the
  console.
- [x] 4.3 `Bug_Backlog.md`: Y-6, Y-7, Z-1 `fixed (freshness-paging-seed)`. Say what Y-6 still
  leaves (no generation after a failed discovery). Update the "Next" line.
- [x] 4.4 `ideas.md` §14: keyset saved lists shipped, and data versions stay open (narrower
  now). Update the round 4 table.
- [x] 4.5 CLAUDE.md §7: shipped entry (cursor format, `invalid_cursor`, generation refreshes
  the profile keys, v2 seed early return and re-activation through the admin), and the Ideas
  line.
- [x] 4.6 Release housekeeping (CLAUDE.md §8), patch release 0.12.12:
  - `VERSION`, the package files and lockfiles;
  - `CHANGELOG.md` (including the `[Unreleased]` e2e CI fix), `features.txt`, README status
    line.
