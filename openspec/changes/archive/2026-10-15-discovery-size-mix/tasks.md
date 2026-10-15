## 1. Settings and validation (design D1, D5)

- [x] 1.1 `DISCOVERY_STAR_BANDS` (default `[[20, 999], [1000, null]]`), `DISCOVERY_EXCLUDED_TOPICS` (default list from D4), `DISCOVERY_MAX_QUERIES` default 20 in `config/settings/base.py` and `.env.example`
- [x] 1.2 System check: bands non-empty, integer, ascending, non-overlapping, only the last open-ended, first lower bound = `DISCOVERY_MIN_STARS`, budget ≥ number of bands
- [x] 1.3 Tests: valid default passes; each invalid shape fails with a clear message

## 2. Banded query plan (spec: "Search queries from the developer profile"; design D1, D2)

- [x] 2.1 `QueryConfig.bands`; `plan_queries` allocates `budget // len(bands)` cores and expands each into one `PlannedQuery` per band (core and key carry the band; star qualifier per band, `stars:a..b` or `stars:>=a`)
- [x] 2.2 Tests: every core in every band, ascending; budget 20 with two bands gives 10 cores; one band reproduces the old plan shape; determinism; existing query tests updated for the new defaults

## 3. `not_code` rule (spec: "Candidate pre-filtering", "Candidate eligibility"; design D4)

- [x] 3.1 `filters.not_code` and reason `NOT_CODE`; `prefilter` checks it after the repository rules (search results and interactions); `eligibility` loads topics and checks it
- [x] 3.2 Tests: `awesome-*` name, excluded topic, empty primary language each rejected as `not_code`; a normal repository passes; archived keeps precedence; interacted list rejected; analyzed list in an existing pool becomes ineligible with `not_code`

## 4. Pool band counts (spec: "Candidate pool maintenance"; design D3)

- [x] 4.1 `_step_pool` records `pool_bands` (per band label, plus `below`) in job metadata
- [x] 4.2 Tests: pool cap with two bands keeps candidates from both; `pool_bands` counts match; discovery service tests updated for banded plans (resume per request key)
- [x] 4.3 Pool step re-checks `not_code` on stored data: removes those candidates, marks the repository ineligible, records `pool_not_code` (found in 5.2: lists from earlier runs stayed recommended); test

## 5. Verification, docs and release

- [x] 5.1 Backend checks: `uv run pytest`, `ruff check`, `ruff format --check`, `mypy`; schema export has no drift; `baselines.json` unchanged
- [x] 5.2 (you) Refresh with the local pool at 40; I report the job's `pool_bands` and rejections, re-export `real-a` and compare contributor counts with the first export
- [x] 5.3 Docs: README discovery settings (bands, excluded topics), CLAUDE.md (Phase 4 notes, carry-over status)
- [x] 5.4 Release housekeeping per CLAUDE.md §8 at archive time (v0.12.0): versions and lockfiles, CHANGELOG, features.txt, README status, CLAUDE.md roadmap
