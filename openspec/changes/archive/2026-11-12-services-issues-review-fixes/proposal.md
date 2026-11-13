## Why

The review sweep's second low-priority module, `apps/backend/services/issues/` (`Bug_Backlog.md`
batch 57, ISV-1…ISV-10), found that issue analysis misreads common labels and issue text:
- Hyphen-scoped labels (`type-bug`, `E-easy`, `C-bug`) match nothing (ISV-1).
- Priority and severity labels vote on difficulty, so `good first issue` with `Priority: Medium`
  comes out `unknown` (ISV-2).
- Label prefixes become technologies: `C-bug` → C, `spring cleaning` → Spring (ISV-3).
- Template comments leak technologies from the body (ISV-4).
- A configuration can silently disable the intermediate technology vote (ISV-5).
- Pasted logs make a short report "long" (ISV-6).
- A body that starts with long template comments is stored without its text, and the body cap
  can silence the long-description vote (ISV-7).

These feed issue matching (issue fit, difficulty fit), the difficulty and contribution-type
filters and the issue detail page. The security review found nothing.

## What Changes

- ISV-1: a label without a punctuation scope whose first word is a known scope word (`type`,
  `kind`, `area`, `category`, `c`, `e`, `t`, `difficulty`, `level`, `complexity`, …) has that word
  as its scope, so `type-bug` → `bug` and `E-easy` → `easy`.
- ISV-2: a scoped label votes on difficulty only under a difficulty scope (`difficulty`, `level`,
  `complexity`, `effort`, `e`, `exp`, `experience`, `skill`). `Priority: Medium` and
  `severity: trivial` no longer vote.
- ISV-3: in labels, ambiguous catalog words (`C`, `Go`, `React`) count only in the label's value
  after its scope, never as the scope word, so `C-bug` no longer means C. `spring cleaning` and
  `good to go` still match: the catalog marks `react` ambiguous too, so a stricter rule would drop
  React from `React Hooks`.
- ISV-4: the body's HTML comments are removed before technology detection.
- ISV-5: core.E040 requires `several_technologies` < `many_technologies`.
- ISV-6: the description length ignores fenced code blocks.
- ISV-7: the stored issue body drops HTML comments before it is capped. core.E040 requires
  `long_body` < `ISSUE_BODY_MAX_CHARS`.
- ISV-8: an `unknown` contribution type also records the taxonomy version in its evidence.
- ISV-10: one cached label parser (full form, scope, value) serves categories, difficulty votes
  and technologies, replacing the second normalizer in `technologies.py`.
- ISV-9 is accepted, not changed: keywords stay unmatched next to a hyphen, which also keeps
  `test-driven` and `error-prone` out.
- `ISSUE_TAXONOMY_VERSION` 2026.11.1. Stored issues change on their next fetch, which shows in
  rankings through data (issue signals and filters). Benchmarks store issue analysis, so the
  baselines cannot move.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `issue-analysis`: "Label normalization" (hyphen and space scopes), "Difficulty estimate" (only
  difficulty scopes vote; length without fenced code; the technology thresholds must differ),
  "Issue technologies" (ambiguous words in labels never as the scope; body without HTML
  comments).
- `issue-ingestion`: "Issue collection" (the stored body drops HTML comments before the cap).

## Impact

- `services/issues/{labels,classify,technologies,analysis}.py`, `services/profiling/text.py`
  (fence-aware stripping), `services/repositories/analysis.py` (body cap),
  `core/checks.py` (two core.E040 rules), tests.
- No migration, no API change (OpenAPI `1.0.0`), no frontend change, no scoring or configuration
  change. Existing settings with equal technology thresholds, or a body cap at or below
  `long_body`, now fail the startup checks; both defaults pass.
