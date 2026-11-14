## 1. Query plan

- [x] 1.1 DSC-4: `allocate` gives leftover slots by largest remainder, ties in `STRATEGIES` order, positive shares first (D2). Tests: `allocate(5, {1,1,1,9}, plenty)` gives topic 4 and language 1. The default-share plans and the existing wrap test are unchanged.
- [x] 1.2 DSC-1: `plan_queries` decides covered topics in two passes from the planned skill and interest queries (D1). Tests: a cut skill query no longer hides its recurring own-repository topic. A planned skill query still covers its topic. Plans stay deterministic.

## 2. Search step and filters

- [x] 2.1 DSC-2: `_record` treats `last_seen_at >= search_started_at` as this run, falling back to `self.now` without the key (D3). Test: rank 2 in band 1, a retry (new `now`), then rank 25 in band 2 keeps 2. A rank from an earlier run is still replaced.
- [x] 2.2 DSC-8: add `filters.stored_result_not_code(gh, repo, cfg)` and call it from the search step (D5). Tests: the suspected list with no dependencies is rejected, a list with dependencies is kept, and a non-list reads no dependencies.
- [x] 2.3 DSC-7: `prefilter` reads stored dependencies only when no other rule rejected the repository (D5). Test: an archived, unannotated stored repository makes no dependency query (`django_assert_num_queries`).

## 3. Yield report

- [x] 3.1 DSC-5, DSC-6: `load` reads `query_yield`, the first plan item and `steps.search` through key transforms, with the window on `Coalesce(started_at, created_at)` (D4). `build` counts `runs_without_search` apart from `runs_without_yield`. JSON key and command header follow. Tests: a never-started cancelled run is in the windowed report, a run with an empty plan is without search, a searched run without yield is without yield, and `load` is one query.

## 4. Checks

- [x] 4.1 `test_baseline_metrics_unchanged` passes (benchmarks store candidates).
- [x] 4.2 Backend: `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`, `uv run mypy .`, `makemigrations --check --settings config.settings.test`.

## 5. Release

- [x] 5.1 `Bug_Backlog.md` batch 59: DSC rows marked fixed, DSC-3 false positive.
- [x] 5.2 `/simplify`, then `/code-review` on the fix diff; record and fix (or skipped by the owner). Skipped by the owner.
- [x] 5.3 Archive (delta into `repository-discovery`). Release housekeeping per CLAUDE.md §8, next patch version. Commit only when the owner says so.
