## 1. Locks

- [x] 1.1 GHS-1: `_step_repositories` upserts the selection in GitHub ID order (D1); test: upsert order is by `github_id` while selection keeps push time
- [x] 1.2 GHS-2: `replace_languages` and `replace_dependencies` lock the repository row (D1); test: the lock is taken (captured SQL has `FOR UPDATE`) before the delete

## 2. Client and OAuth

- [x] 2.1 GHS-3, GHS-10: `_api_origin`, `_link(header, rel)`; `_send`, `_next_link`, `_count_from_single_item_page` use them (D2); tests: next link over `http://` and to another port refused, redirect tests unchanged
- [x] 2.2 GHS-4: `_revoke` maps 403/429 rate limits through `_error_for` (D3); tests: 403 with `X-RateLimit-Remaining: 0` and a secondary-limit 403 retry; other 403 still final `revocation_failed`
- [x] 2.3 GHS-7: `_send` maps `httpx.HTTPError` and `InvalidURL` (D5); tests: `DecodingError` is transient, a malformed Link URL is a client error (a malformed Location is httpx's protocol error, transient; design D5)
- [x] 2.4 GHS-8: `GITHUB_ETAG_MAX_BYTES` (default 256 KiB, check `core.E020`); bodies above it not cached (D6); tests: big body not stored, small body stored, check rejects 0
- [x] 2.5 GHS-10: one `_dt`, one `API_VERSION` (D8)

## 3. Sync steps

- [x] 3.1 GHS-5: plan items merged by stored pk (D4); test: the spec scenario (3 PRs under the old name, 2 pushes under the new)
- [x] 3.2 GHS-6: `contrib_skipped`; skipped repositories keep their links (D4); tests: the spec scenario, and a 404 still drops the link
- [x] 3.3 GHS-9: `dependencies_ids` frozen on the first attempt (D7); test: a retry after `pushed_at` changed reads the first set

## 4. Checks

- [x] 4.1 Backend `uv run pytest`, `ruff check`, `ruff format --check`, `mypy`; `.env.example` lists `GITHUB_ETAG_MAX_BYTES`; no frontend or e2e change

## 5. Release (workflow steps 6-8)

- [x] 5.1 `/simplify`, then `/code-review` on the fix diff; record and fix (deferred by the owner, 2026-11-02: run later)
- [x] 5.2 Archive (delta into `github-data-sync`); `Bug_Backlog.md` batch 32 rows marked fixed
- [x] 5.3 Release housekeeping (CLAUDE.md §8); commit only when the owner says so
