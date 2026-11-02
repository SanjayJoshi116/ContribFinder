## 1. Admin

- [x] 1.1 DEV-1, DEV-2, DEV-9: `ReadOnlyAdmin` on `NoAddDeleteAdmin`, `list_select_related` per admin, `InterestEvidenceInline` (D1); tests: add, change and delete refused for a superuser on every developer admin, changelist query counts do not grow with rows, the interest change page lists its evidence

## 2. API and ordering

- [x] 2.1 DEV-3: `EVIDENCE_ORDER` (nulls last, then pk) in both prefetches; model `Meta.ordering` and its migration (D2); test: undated evidence comes after dated evidence for skills and interests
- [x] 2.2 DEV-7: `pk` tiebreaker in both list orders (D2); test: two tied rows keep their order across `page_size=1` pages
- [x] 2.3 DEV-8: schema guard in `InterestListView.get_queryset` (D3); `npm run api:sync` shows no drift

## 3. Command

- [x] 3.1 DEV-4, DEV-5: `reanalyze_profiles` skips inactive users and users with an active sync, reports `syncing` (D4); tests: inactive skipped, `--user` on an inactive user errors, a running sync is counted and not queued

## 4. Catalog guard

- [x] 4.1 DEV-6: catalog sizes at most `max_page_size` (D5)

## 5. Backlog

- [x] 5.1 `Bug_Backlog.md` batch 37 "Sweep: `developers/`": DEV-1…DEV-9 with verdicts (DEV-6 accepted with guard); sweep table row ticked

## 6. Checks

- [x] 6.1 Backend `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`, `uv run mypy .`, `makemigrations --check --settings config.settings.test`

## 7. Release

- [x] 7.1 `/simplify`, then `/code-review` on the fix diff; record and fix (skipped by the owner, 2026-11-02)
- [x] 7.2 Archive (`skip_specs`); release housekeeping (CLAUDE.md §8, 0.12.49); commit only when the owner says so
