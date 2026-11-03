## 1. Text matching

- [x] 1.1 PROF-1: `PhraseMatcher` keyed and looked up by `casefold()`; a match missing from the
  map is skipped (D1).
  - Tests: `PLAIN_MATCHER.find("Kotlın developer")`, `SYNONYM_MATCHER.find("Machıne learning")`,
    `ſ` and Kelvin sign `K` never raise.
  - A repository description and an issue body containing `ı` go through
    `matching/signals.py` and `issues/technologies.py` without error.

## 2. README

- [x] 2.1 PROF-3: drop `<!-- … -->` from the README before section, badge and free-text
  extraction (D2).
  - Test: a commented-out "## Tech stack" section gives no evidence.
  - Test: a badge inside a comment gives none.
- [x] 2.2 PROF-2: `tech_sections` ignores headings inside ```` ``` ```` / `~~~` fences (D2).
  - Test: the `# install tools` fence makes no section.
  - Test: `## Skills` with a `# setup` fence keeps Go.
  - Test: a technology listed inside a fence in a skills section still counts.
- [x] 2.3 PROF-7: `_ATX` keeps a trailing `#` without a preceding space.
  - Test: `## Languages: C#` gives the evidence detail `"Languages C#" section`.
  - Test: `## Skills ##` still gives "Skills".

## 3. Manifests

- [x] 3.1 PROF-4: `parse_pyproject` reads only lists of specs and tables of groups (D3).
  - Test: `optional-dependencies={dev="pytest"}` → `[]`.
  - Test: `dependencies = "x"` → `[]`.
  - Test: valid groups unchanged.
- [x] 3.2 PROF-5: `parse_requirements` keeps `name @ URL` (with extras) before the URL skip.
  - Test: `django @ https://…` + `flask` → both.
  - Test: a bare URL and `-e git+…` stay skipped.
- [x] 3.3 PROF-6: `parse_pom` strips `<!-- … -->`; `parse_gradle` strips `/* … */` and `//`
  comments that follow a line start or whitespace (D3).
  - Tests: commented-out coordinates give nothing.
  - Test: a string containing `https://` next to a real coordinate keeps the coordinate.

## 4. Contributions

- [x] 4.1 PROF-8: `ProfileInput.contributed_work` (non-fork contributions);
  `contribution_skills` and contribution interests use it (D4).
  - Test: pushes and merged PRs to a forked repository give no skill or interest evidence.
  - Test: a non-fork contribution is unchanged.
  - Test: `experience` counts unchanged.

## 5. Catalog

- [x] 5.1 PROF-9: `_upsert_catalog_skills`/`_interests` insert missing rows
  (`ignore_conflicts`), then `bulk_update` only rows whose name or category differs, sorted by
  slug (D5).
  - Test: a second analysis with an unchanged taxonomy issues no UPDATE on
    `developers_skill`/`developers_interest` (query capture).
  - Test: a renamed catalog entry is updated once.
- [x] 5.2 Bump `TAXONOMY_VERSION` (D6).
  - Test: the stored `analysis_config` carries the new version.

## 6. Backlog

- [x] 6.1 `Bug_Backlog.md` batch 43:
  - PROF-1…PROF-9 marked fixed (0.12.54).
  - PROF-8 decided by the owner (forks never count, 2026-11-03).
  - Note the open question on `experience.py`.

## 7. Checks

- [x] 7.1 Backend checks:
  - `uv run pytest`, including the baseline test, with baselines unchanged;
  - `uv run ruff check . && uv run ruff format --check .`;
  - `uv run mypy .`;
  - `makemigrations --check --settings config.settings.test`.
- [x] 7.2 `openspec validate profiling-review-fixes`. No frontend, API or e2e change.

## 8. Release

- [x] 8.1 `/simplify`, then `/code-review` on the fix diff; record and fix (or the owner skips
  this step) — skipped by the owner (2026-11-03).
- [x] 8.2 Archive (syncs the `skill-detection` delta); release housekeeping (CLAUDE.md §8,
  0.12.54); commit only when the owner says so.
