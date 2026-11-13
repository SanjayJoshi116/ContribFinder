## 1. Storable GitHub text

- [x] 1.1 RS-2: `storable(text)` and `_storable_json(value)` in `services/github/client.py`; `_Response.json()` cleans the parsed body; `_Response.content` for raw files, read by `get_readme`, `get_profile_readme` and `get_file` (D1); tests: NUL removed from raw text, `\u0000` and an unpaired `\ud800` in JSON strings (values, keys, nested lists) cleaned, valid astral characters and emoji unchanged, a cached (304) body is cleaned too
- [x] 1.2 RS-2 end to end: tests: an analysis with a NUL README and an issue body with `\ud800` completes and stores cleaned text; a discovery search whose result description holds `\u0000` stores its results; a profile sync with a NUL in the profile README completes and stores the cleaned README

## 2. Repository analysis

- [x] 2.1 RS-1: identity check by name before a refresh without metadata; on another GitHub ID or a 404, metadata by ID first and the other parts under the current name; `fetched_name` decided after the fetch (D2); tests: issues-only refresh with the name taken by another ID stores the renamed repository and its own issues, never the other ID's; same ID fetches only the issues (plus the check); README-only refresh with 404 by name and by ID ends FAILED `not_found`
- [x] 2.2 RS-7: `lifecycle.fail` returns whether it updated a row; `run` returns SKIPPED when it did not (D6); test: a reclaimed analysis that hits a 404 returns SKIPPED and leaves the other analysis's state
- [x] 2.3 RS-8: entry-label flags from `labels.category`; remove `normalize_label`, `GOOD_FIRST_ISSUE`, `HELP_WANTED` from `analysis.py` and `__all__` (D7); tests: `type: good first issue` and `contributions welcome` set both flags; an unrelated label sets neither

## 3. Lifecycle and backlog

- [x] 3.1 RS-6: `release_name` matches `full_name__iexact`; migration `repositories.0010` adds the `Upper("full_name")` index (D5); tests: a holder differing only in case is released and queued; the same GitHub ID stored with a case change releases nothing; the index is declared in `Repository.Meta.indexes`
- [x] 3.2 RS-10: `release_name` locks holders with `select_for_update().order_by("github_id")` before updating (D6); test: two holders are released (behavior unchanged), and the lock query orders by GitHub ID (captured SQL)
- [x] 3.3 RS-3: `queue_released` sends with `on_commit(..., robust=True)`, tries every pk, logs refusals and `unmark_queued`s them (D3); tests: the broker refuses the first of two sends, the caller's transaction stays committed with no exception, the second is sent, only the first is unmarked; the `NameChanged` path with a refusing broker returns SKIPPED
- [x] 3.4 RS-5: `recheck_eligibility` stamps `lifecycle_changed_at` with the wall clock, keeps `now` for the rules (D4); test: with `now` an hour ago, the stamp is the current time and freshness makes a developer whose generation started after `now` due
- [x] 3.5 RS-9: `mark_stale` loads only the fields `stale_parts` reads and updates per (lifecycle, parts) group (D8); tests: the existing staleness tests pass; query count does not grow with the number of stale rows in one group

## 4. Checks

- [x] 4.1 `npm run manage -- evaluate_ranking` (no `--write-baseline`) reports the numbers in `baselines.json` for every dataset (RS-8 is data-only)
- [x] 4.2 Backend `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`, `uv run mypy .`, `makemigrations --check --settings config.settings.test`

## 5. Release

- [x] 5.1 `Bug_Backlog.md` batch 56: RS rows marked fixed (RS-4 false positive)
- [x] 5.2 `/simplify`, then `/code-review` on the fix diff; record and fix (skipped by the owner, 2026-11-12)
- [x] 5.3 Archive (deltas into `github-data-sync`, `repository-analysis`, `repository-discovery`); release housekeeping (CLAUDE.md §8, next patch version); commit only when the owner says so
