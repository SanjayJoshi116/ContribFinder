## Context

See proposal.md for why.
- `feedback.api.KeysetPagination(PageNumberPagination)` pages `/saved` and `/dismissed`
  (`SavedPagination`, `DismissedPagination`; design D2 of `freshness-paging-seed`).
  - Without `cursor`: DRF's page-number page. `get_paginated_response` keeps DRF's body and
    overwrites only `next` with a cursor link, so `previous` is DRF's `?page=N-1` link (or the
    base URL for page 2).
  - With `cursor`: keyset filter, `count` from `queryset.count()`, `previous` null. A `page`
    in the same request is never read.
- `InvalidCursor(APIException)`: 400, `invalid_cursor`, raised from `decode`.
- Both list views document `error_responses(401)` only.
- The SPA (`src/features/feedback/api.ts`) builds the first request with `page_size` and later
  ones with `page_size` and the `cursor` from `next`; it never reads `previous` and never sends
  `page`. Its test stubs already return `previous: null`.

## Goals / Non-Goals

**Goals:**
- One positioning scheme per response: every link the API hands out is a cursor link, or null.

**Non-Goals:**
- Backward paging. If a client ever needs it, a `before` cursor is a later change.
- Changing `/recommendations` paging (plain page numbers, ideas.md §14 server clamping).
- Y-6 (proposal.md).

## Decisions

**D1. `previous` is always null.**
- `get_paginated_response` sets `previous` to None in page mode, as cursor mode already does.
- *Why not a cursor `previous`:* it needs a reverse keyset query (ascending order, then
  reversed) for a link no client follows. The spec only requires the field to stay.
- *Why not drop the field:* removing a response field is a schema change for generated
  clients; null keeps the shape.

**D2. `cursor` with `page` is a 400, `cursor_with_page`.**
- `CursorWithPage(APIException)` next to `InvalidCursor`: status 400, `default_code`
  `cursor_with_page`, message "Send either a cursor or a page number, not both."
- Checked first in `paginate_queryset`, before decoding the cursor: the presence of the `page`
  query parameter with any value, including `page=1`, and of `cursor` with any value.
- *Why not keep ignoring `page`:* the client asked for a page it does not get, with no signal.
- *Why not reuse `invalid_cursor`:* the cursor may be valid; a distinct code tells the client
  which parameter to drop.
- `page_size` stays allowed in both modes.

**D3. OpenAPI documents the 400.**
- Both list operations use `error_responses(400, 401)`. The `cursor` parameter description
  says it cannot be combined with `page`.
- `npm run api:sync` regenerates `src/api/openapi.json` and `src/api/schema.d.ts`; both are
  committed. The operation ids and response body schema do not change, so no frontend code changes.

## Risks / Trade-offs

- [A third-party client used the page `previous`] → It gets null and can follow `next` from
  page 1 instead. No known client; the SPA never read it. Recorded in the CHANGELOG.
- [A client sends `page=1` with every cursor request] → It now gets 400 instead of a silently
  correct page. The error code names the fix; the SPA does not do this.

## Migration Plan

- No data migration. Deploy backend and the regenerated schema together.
- Rollback: revert the release.
