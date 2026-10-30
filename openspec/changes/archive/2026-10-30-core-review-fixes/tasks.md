## 1. Startup gate and checks

- [x] 1.1 CORE-1, CORE-5: `run_startup_checks` drops silenced messages and runs deployment checks (warnings logged)
- [x] 1.2 CORE-2: `NUM_PROXIES` in `NON_NEGATIVE_INT_SETTINGS`
- [x] 1.3 CORE-4: `DISCOVERY_QUERY_SHARES` positive total (`core.E022`)
- [x] 1.4 CORE-6: CSP values without control characters (`core.E060`)
- [x] 1.5 CORE-8: `REPO_STALE_AFTER` values positive (`core.E023`)
- [x] 1.6 CORE-7: numeric comparisons only after the type test passed
- [x] 1.7 CORE-10: strategies and stale parts from `queries.STRATEGIES` / `staleness.PARTS` (lazy import)

## 2. Logging and reports

- [x] 2.1 CORE-3: redaction matches prefixed key names; adds `secret`, `password`, `sessionid`, `csrftoken`, `encryption_keys`
- [x] 2.2 CORE-9: `write_json` serializes first, writes a temporary file, `os.replace`s it

## 3. Tests and checks

- [x] 3.1 Tests per row: silenced error starts; negative `NUM_PROXIES`; zero shares; CSP newline; zero stale-after; wrongly typed override reported; prefixed and cookie redaction; failed write keeps the old file
- [x] 3.2 `uv run pytest`, `ruff check`, `ruff format --check`, `mypy`

## 4. Release (workflow steps 6-8)

- [x] 4.1 `/simplify`, then `/code-review` on the fix diff; record and fix (skipped on the owner's decision, 2026-10-30)
- [x] 4.2 Archive (delta into `api-platform`); `Bug_Backlog.md` batch 27 rows marked fixed
- [x] 4.3 Release housekeeping (CLAUDE.md §8)
