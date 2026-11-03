## 1. Admin

- [x] 1.1 REC-1, REC-6: remove `ReadOnlyAdmin`; `RecommendationAdmin` and the feedback admins on `core.admin.ViewOnlyAdmin`, `ReasonInline.can_delete = False`, `readonly_fields` removed, `list_select_related` per changelist (D1); tests in `tests/test_recommendations_review_fixes.py`: `assert_view_only` for `Recommendation`, `RecommendationFeedback`, `SavedRepository`, `DismissedRepository`; `changelist_queries` for the four changelists does not grow with rows
- [x] 1.2 REC-2: `ScoringConfigAdmin` on `core.admin.NoAddDeleteAdmin` (D1); test: add and delete refused, change of `description` allowed, the active configuration cannot be deleted

## 2. Models and commands

- [x] 2.1 REC-4: `ScoringConfig.save` raises `ImmutableConfig` for a non-adding save whose row is gone (D2); test: delete the row, save the held instance with other weights → refused, nothing inserted
- [x] 2.2 REC-3: `evaluate_ranking --top-n` below 1 refused, `is not None` (D3); tests for 0 and -5
- [x] 2.3 REC-7: `SheetError` for a non-object export and for candidates without a repository; `benchmark_sheet` counts rows before writing (D4); tests: both commands with a JSON list and a candidate without `repository` end in `CommandError`, no file written by `benchmark_sheet`

## 3. API

- [x] 3.1 REC-8, REC-10: `readme_excerpt` keeps a word ending at the limit, keeps `my_package`, unescapes entities (D5); unit tests
- [x] 3.2 REC-9: status view takes the last time from the latest row, no separate `Max` (D6); test: query count, response unchanged; `npm run api:sync` shows no drift

## 4. Backlog

- [x] 4.1 `Bug_Backlog.md` batch 41 "Sweep: `recommendations/`": REC-1…REC-10 with verdicts (REC-5 false positive); SIM-8 closed; sweep table row for `apps/backend/recommendations/` ticked (review and security review)

## 5. Checks

- [x] 5.1 Backend `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`, `uv run mypy .`, `makemigrations --check --settings config.settings.test`; baselines test passes unchanged

## 6. Release

- [x] 6.1 `/simplify`, then `/code-review` on the fix diff; record and fix (or skipped by the owner) — skipped by the owner (2026-11-03)
- [x] 6.2 Archive (`skip_specs`); release housekeeping (CLAUDE.md §8, 0.12.52); commit only when the owner says so
