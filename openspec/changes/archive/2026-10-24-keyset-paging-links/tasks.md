## 1. Paging links (D1, D2, S-7)

- [x] 1.1 `feedback/api.py`:
  - `CursorWithPage(APIException)`: 400, `default_code` `cursor_with_page`;
  - `KeysetPagination.paginate_queryset` raises it when both `cursor` and `page` are in the
    query, before decoding the cursor;
  - `get_paginated_response` returns `previous: None` in page mode too;
  - update the class docstring (forward only, the mixed-parameter rule).
- [x] 1.2 Tests (`tests/test_feedback_paging.py`), for `/saved` and `/dismissed`:
  - `test_page_numbers_still_work_without_a_cursor`: `previous` is null, `next` still continues
    after page 2;
  - `cursor` with `page=3`, and with `page=1`, is 400 `cursor_with_page`, with a valid cursor;
  - an unreadable cursor with `page` is 400 `cursor_with_page` (checked before decoding);
  - `page_size` with a cursor still works.

## 2. OpenAPI (D3)

- [x] 2.1 `saved_list` and `dismissed_list` document `error_responses(400, 401)`; the `cursor`
  parameter description says it cannot be combined with `page`.
- [x] 2.2 `npm run api:sync` in `apps/frontend`; commit `src/api/openapi.json` and
  `src/api/schema.d.ts`. No frontend code change expected; confirm `usePagedList` and the
  feedback tests do not read `previous`.

## 3. Verification and housekeeping

- [x] 3.1 Backend `ruff check`, `ruff format --check`, `mypy`, `pytest`; frontend lint,
  format:check, typecheck, test; root `check:version`. No `npm run e2e` (no browser flow
  changes).
- [x] 3.2 `Bug_Backlog.md`:
  - S-7 marked `fixed (keyset-paging-links)`, removed from Open items;
  - the batch 18 row and the "Next" line updated;
  - the 0.12.17 row in "Fixed by release", total fixed count.
- [x] 3.3 CLAUDE.md §7: shipped entry (K-1 carry-over unchanged); the 0.12.12 entry's
  `previous null with a cursor` note points to the new rule.
- [x] 3.4 Release housekeeping (CLAUDE.md §8), patch 0.12.17: `VERSION`, package files and
  lockfiles, `CHANGELOG.md` (API: `previous` always null, `cursor_with_page`), `features.txt`,
  README status line.
