## Context

See proposal.md for the findings. Profiling is pure functions over `ProfileInput`
(`services/profiling/inputs.py`). The text matchers built here are also used on third-party text
by `services/matching/signals.py` (repository descriptions) and `services/issues/technologies.py`
(issue titles and bodies).

Analysis writes inside `_persist`, under `job_write`. The catalog rows (`Skill`, `Interest`) are
shared by every user and upserted there in one sorted order (B-3, deadlock avoidance).

## Goals / Non-Goals

**Goals:**

- No text input can make the phrase matcher raise.
- README and manifest parsing never read commented-out text, or code inside fences, as evidence.
- One fork rule for all contribution evidence, skills and interests alike.
- Catalog rows are rewritten only when they change.

**Non-Goals:**

- A full Markdown, TOML or XML parser. The parsers stay small and regex-based where they are
  today; no new dependency.
- Changing `experience.py`. Its contribution counts (`merged_external_prs`,
  `contributed_repositories`) are activity signals, not evidence, and are not covered by the
  fork rule. Left as they are; see Open Questions.
- Re-analyzing stored profiles automatically. `reanalyze_profiles` exists for that.

## Decisions

### D1: Case-fold lookup in `PhraseMatcher` (PROF-1)

- Key the phrase map by `phrase.casefold()`.
- Look up `match.group(0).casefold()`.
- Skip a match whose fold is not a key, instead of raising.

Python's `re.IGNORECASE` matches more case variants than `.lower()` maps back (`ı` U+0131,
`ſ` U+017F, `K` U+212A). `casefold()` covers those three. The skip guards any variant left over.

The returned "first matched phrase" stays the lowercased matched text, as today. Callers show
it as evidence detail.

Alternative considered: compile without `IGNORECASE` and lowercase the text first. It would also
work, but match offsets would shift for characters whose lowercase has a different length
(`İ`), and the evidence detail would no longer be the user's text.

### D2: Strip comments and skip fences in the README (PROF-2, PROF-3, PROF-7)

- `readme_skills` and `badge_skills` first remove `<!-- … -->` with a non-greedy, DOTALL regex.
  This is the same idea as `classify._HTML_COMMENT` for issue bodies, but a local constant
  (profiling must not import issues).
- `tech_sections` tracks fences: a line starting with ```` ``` ```` or `~~~` (up to 3 spaces of
  indent) toggles "in fence". Lines inside a fence are never headings, but they stay part of a
  section's text: a skills section may legitimately list technologies in a code block.
- `_ATX` takes a closing `#` sequence only after whitespace (`(?:\s+#+)?\s*$`), as in
  CommonMark.

### D3: Manifests (PROF-4, PROF-5, PROF-6)

- `parse_pyproject`:
  - `_pep508_names` accepts only a `list`; anything else gives `[]`.
  - The `optional-dependencies` and `dependency-groups` values are read only when they are
    tables (`dict`).
  - Poetry tables are read only when they are dicts.
- `parse_requirements` tries `^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*@\s*\S` (a
  PEP 508 direct reference) before the `://` skip.
- `parse_pom` removes `<!-- … -->` before matching.
- `parse_gradle` removes `/* … */` and `//`-to-end-of-line comments before matching. The
  `//` removal must not cut a URL inside a string: strip `//` only when it is preceded by
  start-of-line or whitespace. Gradle coordinates contain no `//`, so a coordinate string is
  never affected.

### D4: One fork rule for contributions (PROF-8)

`ProfileInput.contributed_work` (property) returns the contributions whose repository is not a
fork, mirroring `own_work`.

- `collectors.contribution_skills` and `interests` (contribution evidence) iterate it.
- `experience.py` keeps `contributions` (Non-Goals).

### D5: Catalog writes only on change (PROF-9)

`_upsert_catalog_skills(slugs)`:

1. `bulk_create(..., ignore_conflicts=True)`, in the existing sorted order, inserts the missing
   rows.
2. `in_bulk` reads the rows.
3. Only rows whose `name` or `category` differs from the taxonomy are updated
   (`bulk_update`, sorted by slug).

The same applies to interests (`name` only).

- Locks are taken only on inserted or changed rows, so concurrent analyses no longer queue on
  `python`.
- The update stays inside `_persist`. A taxonomy rename then updates once and is consistent with
  the evidence written next to it.

Alternative considered: upsert the catalog in its own transaction before `job_write`. Rejected:
it moves writes outside the cancellation guard (`JobCancelled`), and it is unnecessary once
unchanged rows are not written.

### D6: Taxonomy version

Bump `TAXONOMY_VERSION`. Analysis output changes for the same input, and profiles record the
version in `analysis_config`, which shows that a reanalysis picked up the new rules.

## Risks / Trade-offs

- [A README that deliberately lists skills inside a code block] → fences only stop heading
  detection, and their text still counts within a tech section (D2).
- [An unterminated `<!--`] → the non-greedy regex needs a closing `-->`. An unterminated comment
  is left as text, which is how browsers treat it too, so no content is lost silently.
- [Gradle `//` inside a string not preceded by whitespace (`"http://…"`)] → kept, by the
  whitespace rule (D3).
- [Stored profiles keep old evidence until their next analysis] → expected; `reanalyze_profiles`
  applies it at once (it queues jobs).
- [Baselines move] → they cannot: benchmarks store finished profiles and issues. The baseline
  test confirms it.

## Migration Plan

No migration or setting. Patch release 0.12.54. After deploying, optionally run
`npm run manage -- reanalyze_profiles`. Rollback is a plain revert.

## Open Questions

- Should `experience.py`'s contribution counts also ignore forks? Deferring it does not change
  this change's approach or tasks. It would be a separate signal change (experience level feeds
  matching).
