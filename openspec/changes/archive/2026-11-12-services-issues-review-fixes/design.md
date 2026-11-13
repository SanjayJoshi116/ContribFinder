## Context

See proposal.md (Why). Issue analysis (`services/issues/`) is pure: `analysis.analyze` runs
`labels.normalize_labels` → `classify.contribution_type` → `technologies.detect` →
`classify.difficulty` on every issue fetch (`services/repositories/analysis._store_issues`, which
caps the body first). `labels.forms(name)` returns the normalized label and its scope-stripped
form; `classify._label_votes` and `labels.category` each call it, and the repository
entry-label flags call `category` again (0.12.62). Technologies use the skill catalog's two
matchers: `PLAIN_MATCHER` (unambiguous phrases) and `ALL_MATCHER` (adds ambiguous ones such as
`c`, `go`, `react`, `spring`).

## Goals / Non-Goals

**Goals:** a label is read the same way, once, by categories, difficulty votes and technologies;
issue text that is not the report (template comments, pasted logs) neither sets the difficulty nor
adds technologies; impossible difficulty configurations are refused at startup.

**Non-Goals:**
- ISV-9 (accepted): keywords next to a hyphen.
- A stop-phrase list for ambiguous words inside a label value (`spring cleaning`, `good to go`).
  Rare, and every entry would be a guess.
- Unfenced pasted logs: no reliable boundary without fences.

## Decisions

### D1. One label parser (ISV-1, ISV-10)

`labels.parts(name) -> LabelParts(full, scope, value)`, cached with `functools.lru_cache`
(maxsize 4096; it's pure, and labels repeat across issues and repositories):
- `full = normalize(name)` as today.
- Punctuated scope first (`_SCOPE`: `type:`, `kind/`, `[type]`): `scope` is the text before the
  punctuation, `value` is the rest.
- Otherwise, when `full` has two or more words and its first word is in `SCOPE_WORDS`, the first
  word is the scope and the rest is the value. `SCOPE_WORDS = {"type", "kind", "area",
  "category", "cat", "c", "e", "t", "a", "difficulty", "level", "complexity", "effort", "exp",
  "lang"}`. Every entry is a word that no alias starts with, so `good first issue`, `help wanted`,
  `bug fix` and `test coverage` are unaffected; a test checks that no `ALIASES` key or
  `DIFFICULTY_LABELS` key starts with a scope word.
- Otherwise `scope = ""` and `value = full`.

`forms(name)` becomes `(full, value)` when they differ, else `(full,)`, which keeps today's
callers working. `category` reads `parts`.

Alternative: treat any first word before a hyphen as a scope. Rejected: `good-first-issue` would
become `first issue`.

### D2. Difficulty votes only from difficulty scopes (ISV-2)

`DIFFICULTY_SCOPES = {"difficulty", "level", "complexity", "effort", "e", "exp", "experience",
"skill"}`. `_label_votes` looks up `DIFFICULTY_LABELS` by `full` when there is no scope, and by
`value` when the scope is in `DIFFICULTY_SCOPES`. Any other scope casts no difficulty vote. The
good-first-issue category still votes beginner under any scope (`type: good first issue`), as
before.

### D3. Technologies from labels (ISV-3)

For each label: `ALL_MATCHER.find(parts.value)` (ambiguous words allowed, scope excluded), then
`PLAIN_MATCHER.find(parts.full)` (unambiguous phrases anywhere, including a scope such as
`python: crash`), in that order, through the existing `found.setdefault`. The `replace("-", " ")`
copy is removed (ISV-10). `normalize` lower-cases and drops edge symbols, and the matcher
compares case-folded, so `React-Native` and `C++` match as before.

### D4. Issue text that is not the report (ISV-4, ISV-6, ISV-7)

- Technologies: `PLAIN_MATCHER.find(plain_text(strip_html_comments(body)))`.
- `services/profiling/text.py` gets the one CommonMark fence rule: `FENCE` (moved from
  `readme.py`), `closes_fence(marker, fence)`, and `strip_code_fences(text)`. That function drops
  fenced blocks, fences included; an unclosed fence runs to the end, as CommonMark renders it.
  `readme.tech_sections` uses `FENCE`/`closes_fence` (no behavior change).
- Difficulty length: `len(strip_code_fences(strip_html_comments(body)).strip())`.
- Stored body: `_store_issues` stores `strip_html_comments(data.body)[:limit]`. Analysis runs on
  that stored text, as before. Classification still strips comments itself, which is idempotent
  and keeps the pure function correct for any input.

### D5. Startup checks (ISV-5, ISV-7)

In `core/checks.py` (core.E040): `2 <= several_technologies < many_technologies`, and
`long_body < ISSUE_BODY_MAX_CHARS`. The messages name both settings. `LEVEL_VOTERS` and core.W004
stay correct, because the technology count can now always vote intermediate.

### D6. Evidence and version (ISV-8)

`contribution_type_evidence` is `{**evidence, "taxonomy": ...}` also when `evidence` is empty.
The SPA reads `by` and treats its absence as "no evidence" (`features/issues/evidence.ts`), so the
detail page doesn't change. `ISSUE_TAXONOMY_VERSION = "2026.11.1"`.

## Risks / Trade-offs

- [A project whose real label starts with a scope word, such as `e2e tests` or `area51`] → a scope
  needs a separate first word (`e2e` and `area51` are single words). A test lists the common
  alias forms and checks they keep their category.
- [Dropping HTML comments from the stored body changes what the issue page shows] → it shows the
  report without template instructions, which reads better. Raw GitHub text is one click away.
- [Stored issues keep the old analysis until their next fetch (6 h)] → the taxonomy version
  marks which analysis produced each row.
- [Rankings move through issue data] → the benchmark stores issue analysis, so baselines cannot
  move (checked by `test_baseline_metrics_unchanged`). Live recommendations regenerate through
  freshness.
