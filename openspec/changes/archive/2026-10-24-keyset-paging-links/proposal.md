## Why

S-7 of `Bug_Backlog.md` (batch 18, from the review of 0.12.13/0.12.14). Since 0.12.12,
`GET /api/v1/saved` and `GET /api/v1/dismissed` page by keyset (design D2 of
`freshness-paging-seed`), but page mode still mixes two schemes:
- `?page=2` returns a cursor `next` and DRF's page-number `previous` (`?page=1`). A client that
  follows `next` and then `previous` mixes keyset and offset positions, so under concurrent
  saves it repeats or skips entries: the bug the keyset fixed for `next`.
- `?cursor=…&page=3` silently ignores `page`. The client gets a different page than it asked
  for and cannot tell.

D2 kept the page `previous` on purpose and the spec says the responses keep `previous`, so the
fix changes specified behavior. The SPA never reads `previous` or sends both parameters, so no
client changes.

Y-6 (data versions, `ideas.md` §14) is not in this change: the backlog says to fix it when it
shows in use, and it needs a polling design of its own.

## What Changes

- `previous` is always null on both lists: they page forward only. The field stays in the
  response, so the response shape is unchanged.
- A request with both `cursor` and `page` is rejected with a 400 error, code
  `cursor_with_page`, through the error envelope. A request with only `page` (and
  `page_size`) works as before, and its `next` still carries a cursor.
- Not breaking for the SPA. A third-party client that relied on the page `previous` or on
  `page` being ignored with a cursor sees the new behavior. OpenAPI stays `1.0.0`: the
  response shape is the same, and the 400 uses the existing error envelope.
- The OpenAPI document lists the 400 response for both list operations. Today it lists only
  401, although `invalid_cursor` has answered 400 since 0.12.12.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `recommendation-feedback`, "Complete saved and hidden lists": `previous` is always null, and
  `cursor` together with `page` is rejected with `cursor_with_page`.

## Impact

- Backend: `feedback/api.py` (`KeysetPagination`: `previous`, the mixed-parameter check, a new
  `CursorWithPage` exception); `tests/test_feedback_paging.py`.
- API: `previous` null in page mode; a new 400 code; the 400 response documented for
  `saved_list` and `dismissed_list` (`npm run api:sync` regenerates the schema and
  `src/api/schema.d.ts`; CI fails on drift).
- Frontend: no code change (`usePagedList` reads only `next`). Tests that stub `previous: null`
  already match.
- Release: patch 0.12.17. Docs: `Bug_Backlog.md` (S-7 fixed, batch 18 row), CHANGELOG,
  features, README, CLAUDE.md §7.
