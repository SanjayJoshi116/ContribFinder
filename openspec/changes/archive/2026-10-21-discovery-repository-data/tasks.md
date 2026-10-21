## 1. Data model (D12, D11, C-18)

- [x] 1.1 `Repository.lifecycle_changed_at`: `default=timezone.now`, non-null; add `refresh_queued_at = DateTimeField(null=True, blank=True)`
- [x] 1.2 `repositories` migration: `RunPython` backfills null `lifecycle_changed_at` from `synced_at` (reverse no-op), then the field changes, then the new column
- [x] 1.3 Remove the null patches: both `lifecycle_changed_at is None` blocks in `services/discovery/service.py`, the `isnull` branch in the backlog query and in `_needs_analysis`
- [x] 1.4 Tests (`test_models_phase4.py`): a repository created without `lifecycle_changed_at` gets one; the migration backfills a null row from `synced_at` (not testable after the migration: the column is non-null; the `RunPython` step is exercised by the test database migrating)

## 2. Freeing names, metadata by ID (D1, D2, C-2, C-8)

- [x] 2.1 `GitHubClient.get_repository_by_id(github_id)` (`GET /repositories/{id}`, `@_parses_response`), with recorded-fixture tests (200, 404)
- [x] 2.2 `staleness.is_released_name(name)`; `stale_parts()` reports `metadata` stale for a released name
- [x] 2.3 `lifecycle.release_name(full_name, github_id)`: rename any other holder of the name to `"{full_name}~{holder.github_id}"`, nothing else
- [x] 2.4 `upsert_repository(gh, now, *, metadata_fetched=True)`: call `release_name` instead of deleting; with `metadata_fetched=False`, `synced_at` only in `create_defaults`; search (`_store_search_result`) passes `False`; update the module docstring
- [x] 2.5 Analysis `_fetch`: metadata by name, falling back to `get_repository_by_id` when the stored name is released, GitHub answers 404, or the answer's `github_id` differs; later parts use the resolved name
- [x] 2.6 Tests (`test_discovery_service.py`, `test_repository_analysis.py`): a search result taking a stored name keeps the old row with its candidates, recommendations, saves and dismissals; the old row's next analysis resolves its current name by ID; a released name answered 404 by ID ends FAILED `not_found`; a search result for an analyzed repository updates stars but not `synced_at`, and its metadata goes stale on schedule

## 3. Analysis inputs (D4, D11, C-5, C-14, C-15)

- [x] 3.1 `lifecycle.hold`: lock the full row and copy its fields onto `repo` after checking the token; `NameChanged(ClaimLost)` when the name differs from the fetched-under name and metadata was not fetched (the analysis passes the name it fetched under)
- [x] 3.2 `RepositoryAnalysisService.run`: FAILED retry → every part; otherwise stale parts ∩ explicit parts; `metadata` first for a released name
- [x] 3.3 `complete()` and `fail()` clear `refresh_queued_at`
- [x] 3.4 Tests (`test_repository_analysis.py`): a search storing `archived` while an issues refresh runs → the refresh ends ineligible `archived`; a README task for a FAILED repository fetches metadata, and a 404 keeps it FAILED and ineligible; an issues task after another analysis fetched issues makes no issues request; a name released mid-analysis without metadata discards the fetch (SKIPPED, state restored); explicit-part tests use `repo_fixtures.expire_parts` (`test_issue_matching.py` needed no change)

## 4. Backlog service (D11, C-15, C-16)

- [x] 4.1 New `services/repositories/backlog.py`: `mark_stale(now)`, `queued_before(now)`, `queue_batch(now) -> list[tuple[int, Kind]]` (stamps `refresh_queued_at`; the queued window excludes STALE/DISCOVERED/FAILED rows, never abandoned claims)
- [x] 4.2 `repositories/tasks.py`: `mark_stale_repositories` and `process_repository_backlog` call the service and only dispatch by kind
- [x] 4.3 Tests (`test_refresh_pipeline.py` or the backlog tests): a queued STALE repository is not queued again 15 min later; it is queued again after `queued_before`; a completed refresh clears the stamp; an abandoned claim is queued regardless of the stamp; existing backlog tests pass through the service

## 5. Discovery search and provenance (D3, D6, D8, R-5, R-6, C-7, C-13)

- [x] 5.1 `queries.plan_queries`: `core` without the `stars:` qualifier; `key` keeps `@{index}`; update tests in `test_discovery_queries.py`
- [x] 5.2 `filters.not_code(..., *, has_dependencies)` per D6; `stored_not_code(repo)`; `_has_dependencies` reads an annotation first; `_topics` uses `repo.topics.all()`; docstring updated
- [x] 5.3 Settings: keep `list`, `lists`, `books` in the default `DISCOVERY_EXCLUDED_TOPICS` (dropping them made `public-apis` and `free-programming-books` eligible in the manual run; dependency evidence protects tagged libraries)
- [x] 5.4 `_step_search`: store `search_started_at` on first entry (before the empty-plan check); sort surviving results by `github_id` before storing (ranks kept); reject suspected lists whose stored row is `stored_not_code` as `NOT_CODE`
- [x] 5.5 `_step_interactions`: prefetch topics, annotate `has_dependencies`, same stored `not_code` check
- [x] 5.6 Tests (`test_discovery_filters.py`, `test_discovery_service.py`): `awesome-lint` with a language becomes a candidate and is eligible after analysis with dependencies; `awesome-python` without dependencies ends `not_code`, and a later search rejects it without an analysis; a library tagged `list` passes search; a repository crossing bands keeps one record with the new rank and no `stars:` text; `prefilter` over prefetched, annotated rows makes no queries; results are stored in GitHub ID order with their ranks kept (asserted on the store order instead of a two-thread race, which would be timing-dependent)

## 6. Pool step and analysis plan (D5, D7, D9, D10, C-11, C-12, C-17, R-4, R-9, R-12)

- [x] 6.1 New `services/discovery/ordering.py: pool_order(queryset, *leading)`; use it in the pool cap, `_pool_repositories` and `CandidateListView` (`leading=("state",)`)
- [x] 6.2 `lifecycle.recheck_eligibility(repo_ids, *, now) -> int` per D5 (`skip_locked`, `github_id` order, RECOMMENDABLE/INDEXED/STALE only)
- [x] 6.3 `_step_pool`: prune `CandidateDiscovery` with `last_seen_at < search_started_at`; remove `stored_not_code` candidates (no `Repository` writes); `recheck_eligibility`; cap; metadata adds `pool_eligibility_changed`
- [x] 6.4 `STEPS` and `services/jobs.DISCOVERY_STEPS`: `queries, search, interactions, pool, analysis`
- [x] 6.5 `_step_analysis`: plan once into `analysis_plan` / `analysis_total` / `analysis_capped`; resume works on the plan minus `analyzed`
- [x] 6.6 `queries.band_of`; `_band_counts` with `below`, band labels and `other` (only when non-zero)
- [x] 6.7 Tests (`test_discovery_service.py`, `test_discovery_api.py`): cap 10 of 220 → only kept candidates analyzed; resumed analysis with cap 10 after 4 analyzes 6 more and keeps `analysis_total`; a discovery record not seen this run is pruned while the candidate stays; a shorter push window makes a RECOMMENDABLE pool repository INDEXED `inactive`; a FAILED list keeps `repository_unavailable`; a REFRESHING (claimed) repository is unchanged; bands `[[20,99],[200,999]]` count 150 and 5000 under `other`; the API orders a more recently found candidate first on equal rank; the step-order assertion is updated

## 7. Configuration (D13, R-3, R-10)

- [x] 7.1 `base.py`: default `DISCOVERY_STAR_BANDS` derived from `DISCOVERY_MIN_STARS` (`[[m, 999], [1000, None]]`, or `[[m, None]]` when `m >= 1000`); update the comment
- [x] 7.2 `core/checks.py`: `core.W003` when `DISCOVERY_MAX_QUERIES` is not a multiple of the band count, naming the unused requests
- [x] 7.3 Tests (`test_discovery_config.py`): the derived defaults for 50 and 1500 pass the checks; budget 25 with 3 bands warns `core.W003`, budget 20 with 2 bands does not
- [x] 7.4 `.env.example` / README: note that the bands follow `DISCOVERY_MIN_STARS` unless set

## 8. Verification and release

- [x] 8.1 `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`, `uv run mypy .`
- [x] 8.2 `uv run python manage.py evaluate_ranking` matches `baselines.json` (no ranking change)
- [x] 8.3 `npm run api:sync` and confirm the OpenAPI schema and `schema.d.ts` are unchanged in shape (only the candidate list's description changed); frontend `npm test`, `npm run typecheck`
- [x] 8.4 Manual: one local discovery run (`npm start`) completes with steps in the new order, no `stars:` in candidate provenance, and `pool_bands` / `pool_eligibility_changed` in the job metadata (run 2026-10-21: all three hold; it exposed the generic-topic regression fixed in 5.3, confirmed by evaluating `eligibility` on the stored rows: `public-apis` and `free-programming-books` → `not_code`, `prompts.chat` and `django` eligible)
- [x] 8.5 Mark rows C-2, C-5, C-7, C-8, C-11, C-12, C-13, C-14, C-15, C-16, C-17, C-18, R-3, R-4, R-5, R-6, R-9, R-10, R-11 and R-12 `fixed (discovery-repository-data)` in `Bug_Backlog.md`; record K-4 as still open
- [x] 8.6 Release housekeeping per CLAUDE.md §8 as patch `0.12.7`: version files and lockfiles, `npm run check:version`, `CHANGELOG.md`, `features.txt`, `README.md` status line, CLAUDE.md §7 entry (with K-1 still carried over) and the §4 layout (`backlog.py`, `ordering.py`)
