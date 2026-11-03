## 1. Admin

- [x] 1.1 ISS-1, ISS-2, ISS-8: `IssueAdmin` and `RecommendedIssueAdmin` on `core.admin.ViewOnlyAdmin`, `readonly_fields` removed, no import of `recommendations.admin.ReadOnlyAdmin` (D1); tests in `tests/test_issues_review_fixes.py`: `shared_fixtures.assert_view_only` for `Issue` and `RecommendedIssue` (add, change and delete refused for a superuser)
- [x] 1.2 ISS-5: `IssueAdmin.list_select_related = ("repository",)` (D1); test: `changelist_queries` for both changelists does not grow from 1 to 3 rows

## 2. Serializer

- [x] 2.1 ISS-7: technology `source` choices from `technologies.TITLE`, `LABEL`, `BODY` (D2); test: the field's choices equal the constants; `npm run api:sync` shows no drift

## 3. Backlog

- [x] 3.1 `Bug_Backlog.md` batch 40 "Sweep: `issues/`": ISS-1…ISS-8 with verdicts (ISS-3, ISS-4, ISS-6 accepted, D3); SIM-8 row notes `issues/` done, `feedback/` and `recommendations/` left; sweep table row for `apps/backend/issues/` ticked (review and security review)

## 4. Checks

- [x] 4.1 Backend `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`, `uv run mypy .`, `makemigrations --check --settings config.settings.test`

## 5. Release

- [x] 5.1 `/simplify`, then `/code-review` on the fix diff; record and fix (or skipped by the owner) — skipped by the owner (2026-11-03)
- [x] 5.2 Archive (`skip_specs`); release housekeeping (CLAUDE.md §8, 0.12.51); commit only when the owner says so
