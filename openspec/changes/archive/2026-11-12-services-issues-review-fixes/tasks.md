## 1. Labels

- [x] 1.1 ISV-1, ISV-10: `labels.parts(name)` (cached; punctuated scope, else a first word in `SCOPE_WORDS`); `forms` and `category` read it (D1); tests: `type-bug`, `C-feature-request`, `kind-documentation` map to `bug`, `enhancement`, `documentation`; `good first issue`, `help wanted`, `bug fix`, `test coverage` unchanged; no `ALIASES` or `DIFFICULTY_LABELS` key starts with a scope word
- [x] 1.2 ISV-2: difficulty votes from unscoped labels or `DIFFICULTY_SCOPES` only (D2); tests: `good first issue` + `Priority: Medium` (short body, one technology) is beginner; `severity: trivial` casts no vote; `E-easy` and `difficulty: hard` vote; `type: good first issue` still votes beginner

## 2. Technologies and text

- [x] 2.1 ISV-3: labels match ambiguous words in their value only, unambiguous phrases anywhere (D3); tests: `C-bug`, `C-feature-request` give no C; `lang: go`, `React Hooks`, `C` give Go, React, C; `python: crash` gives Python
- [x] 2.2 ISV-4: body technologies after `strip_html_comments` (D4); tests: `<!-- e.g. Python >= 3.10, Node.js 20 -->` adds neither; an unterminated comment hides the rest
- [x] 2.3 ISV-6: `text.FENCE`, `closes_fence`, `strip_code_fences`; `readme.tech_sections` uses them; difficulty length without fenced code (D4); tests: a sentence plus a 4,500-character fenced traceback votes short; an unclosed fence runs to the end; the existing README fence tests pass
- [x] 2.4 ISV-7: stored body drops HTML comments before the cap (D4); test: 12,000 characters of comments then a three-line report stores the report

## 3. Checks and evidence

- [x] 3.1 ISV-5, ISV-7: core.E040 requires `several_technologies < many_technologies` and `long_body < ISSUE_BODY_MAX_CHARS` (D5); tests: equal technology thresholds and a cap at `long_body` are errors; defaults pass
- [x] 3.2 ISV-8: unknown contribution type records the taxonomy version; `ISSUE_TAXONOMY_VERSION` 2026.11.1 (D6); test: unknown evidence is `{"taxonomy": "2026.11.1"}`

## 4. Checks

- [x] 4.1 `test_baseline_metrics_unchanged` passes (issue analysis is stored in the benchmarks); `test_issue_signal_wording` passes (no new difficulty signal)
- [x] 4.2 Backend `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`, `uv run mypy .`, `makemigrations --check --settings config.settings.test`

## 5. Release

- [x] 5.1 `Bug_Backlog.md` batch 57: ISV rows marked fixed (ISV-9 accepted)
- [x] 5.2 `/simplify`, then `/code-review` on the fix diff; record and fix (skipped by the owner, 2026-11-12)
- [x] 5.3 Archive (deltas into `issue-analysis`, `issue-ingestion`); release housekeeping (CLAUDE.md §8, next patch version); commit only when the owner says so
