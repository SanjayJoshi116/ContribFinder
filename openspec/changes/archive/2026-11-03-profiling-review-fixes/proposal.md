## Why

The review sweep of `apps/backend/services/profiling/` (`Bug_Backlog.md` batch 43, PROF-1…PROF-9)
found one crash and several cases of wrong skill evidence:

- **PROF-1:** `PhraseMatcher.find` raises `KeyError` on Unicode case-fold characters. One profile
  README, repository description or issue text containing `ı` or `ſ` fails analysis or
  generation for every user whose pool holds that repository.
- **README and manifest parsing:** text the developer never meant as evidence counts as
  evidence. This covers code comments and commented-out sections, a pyproject string read as a
  list, and commented-out dependencies.
- **Direct references:** a dependency named through a direct reference is lost.
- **Forks:** contributions to forks give evidence, against the module's own rule.

PROF-1…PROF-8 were reproduced except PROF-6. The owner decided PROF-8 on 2026-11-03: forks
never count.

## What Changes

- **PROF-1:** phrase matching folds case with `casefold()` on both sides, so any text the
  pattern matches maps to its catalog phrase. Nothing raises on unknown case variants.
- **PROF-2, PROF-3:** README extraction ignores fenced code blocks (```` ``` ````, `~~~`) when
  finding headings, and drops HTML comments (`<!-- … -->`) before any extraction.
- **PROF-7:** an ATX heading keeps a trailing `#` that has no space before it (`## C#`).
- **PROF-4:** `pyproject.toml` dependency lists are read only when they are lists (and groups
  only when they are tables); anything else gives no dependencies.
- **PROF-5:** `requirements.txt` keeps the name of a PEP 508 direct reference
  (`name @ https://…`); bare URLs and option lines stay skipped.
- **PROF-6:** `pom.xml` and Gradle files are read without their comments.
- **PROF-8:** contributions to forked repositories give no skill or interest evidence.
- **PROF-9:** the shared `Skill`/`Interest` catalog rows are inserted when missing and updated
  only when their name or category differs. Every row is no longer rewritten on every analysis.
- Stored profiles change on their next analysis. `reanalyze_profiles` can apply this at once.
  Benchmarks store profiles, so baselines do not move.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `skill-detection`:
  - **"README skill evidence":** code blocks and HTML comments provide no evidence.
  - **"Dependency evidence":** commented-out dependencies provide none; direct references count.
  - **"Contribution evidence":** forked repositories provide none.

`interest-detection` already says forked repositories provide no evidence, so the code is fixed
to match it. The crash fix (PROF-1) and the catalog write (PROF-9) follow existing requirements
("Phrases SHALL match … case-insensitively"; analysis must not fail).

## Impact

- `apps/backend/services/profiling/`:
  - `text.py` (`PhraseMatcher`)
  - `readme.py` (`tech_sections`, `_ATX`, comment stripping)
  - `manifests.py` (`parse_pyproject`, `parse_requirements`, `parse_pom`, `parse_gradle`)
  - `collectors.py` and `interests.py` (fork check)
  - `analysis.py` (`_upsert_catalog_skills`, `_upsert_catalog_interests`)
- Also benefits matching and issue analysis, which share the matcher
  (`services/matching/signals.py`, `services/issues/technologies.py`): they no longer crash on
  such text.
- No migration, API or setting change. No ranking or config change; the evaluation baselines
  must stay unchanged (checked by the baseline test).
- `TAXONOMY_VERSION` is bumped. Profiles record it in `analysis_config`, so a reanalysis is
  visible.
