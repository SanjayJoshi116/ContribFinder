## 1. Relevance gate on weights (D1, D-8)

- [ ] 1.1 `services/ranking/score.py`:
  - `has_relevance(signals, weights)` is true when some relevance signal has value > 0 and
    weight > 0;
  - `Scored.relevant`, set in `score_candidate`;
  - `is_relevant` returns `scored.relevant`.
- [ ] 1.2 `services/ranking/pipeline.py`: the issue preselection passes the configuration's
  weights.
- [ ] 1.3 Tests:
  - a candidate matching only interests under a configuration with interest weight 0 is not
    ranked, and its id is not passed to `issues_for`;
  - under v1 and v2 the same candidates pass as before.

## 2. Explanations (D2, D3, D-9, D-16)

- [ ] 2.1 `services/matching/issues.py`:
  - `match_issues` adds `technology_count` to the `issue_fit` evidence;
  - `score_issue` adds the unknown-difficulty reason when the difficulty-fit part is above 0.
- [ ] 2.2 `services/ranking/explain.py`: `_issue_availability` uses the three openings in D2,
  with the fallback for evidence without `technology_count`.
- [ ] 2.3 Tests:
  - all-technology, label-only and mixed texts, singular and plural;
  - old evidence without `technology_count`;
  - the unknown-difficulty reason (text, detail, weight), and none when the table value is 0;
  - issue scores unchanged.
  Check `apps/frontend` tests and the e2e seed (`e2e/builders.py`) for the old "match your
  profile" text and update any fixture that names it.

## 3. Issue analysis (D4, D-12, D-13, D-18)

- [ ] 3.1 `services/issues/labels.py`: bracketed scope in `_SCOPE`, and `forms` strips the scope
  before the edges are stripped. Bump `ISSUE_TAXONOMY_VERSION` to `2026.10.3`.
- [ ] 3.2 `services/issues/classify.py`:
  - body length without HTML comments, including an unterminated one;
  - `several_technologies` and `min_votes` read from the thresholds;
  - remove `MIN_VOTES`.
- [ ] 3.3 `config/settings/base.py`: `ISSUE_DIFFICULTY` defaults `several_technologies: 2` and
  `min_votes: 2`, plus the comment. Do the same in `.env.example`'s commented
  `ISSUE_DIFFICULTY` line.
- [ ] 3.4 `core/checks.py`:
  - add the two keys to `ISSUE_DIFFICULTY_KEYS`;
  - new `core.E040` messages for `several_technologies` (2..`many_technologies`) and
    `min_votes` (≥ 2).
- [ ] 3.5 Tests:
  - labels: `[Type] Bug` → `bug` and `[Area] Docs` → `documentation`; `[Bug]`, `Type: Bug` and
    emoji labels unchanged;
  - classify:
    - a template with long comments and a short report votes beginner;
    - an unterminated comment is dropped;
    - with `several_technologies: 3`, two technologies abstain;
    - `min_votes: 3` turns a two-vote beginner into unknown;
  - checks: each new error, and a partial `ISSUE_DIFFICULTY` override still valid.

## 4. Configuration rules (D5, D6, D-15, D-17)

- [ ] 4.1 `services/ranking/config.py`: openness points must sum to at most 1 (tolerance 1e-6).
- [ ] 4.2 `recommendations/models.py`: `ImmutableConfig(ValidationError)`; `save()` refuses a
  change to version, weights or params of a stored row. `is_active`, `description` and
  `update_fields` without those fields pass.
- [ ] 4.3 `recommendations/admin.py`: version, weights and params read-only for every saved row.
  Update the comment.
- [ ] 4.4 Tests:
  - openness sum over 1 rejected, and v1 and v2 still valid with `stored=True`;
  - `save()` with changed weights raises and leaves the row unchanged;
  - `is_active` toggled through `save()` passes;
  - the admin change form for a configuration without recommendations shows the three fields
    read-only;
  - activation and the seed round-trip tests still pass. Fix any test that edits a stored
    configuration in place: it creates a new version instead.

## 5. Verification and housekeeping

- [ ] 5.1 Backend `ruff check`, `ruff format --check`, `mypy`, `pytest`.
  - The baseline test passes and `baselines.json` is unchanged (`git diff --exit-code
    apps/backend/evaluation/baselines.json`).
  - Run `npm run manage -- evaluate_ranking` without `--write-baseline`: identical metrics for
    v1 and v2.
  - Frontend lint, format:check, typecheck and test.
  - Root `check:version`.
  - No `npm run e2e`, unless 2.3 changed the e2e seed or a spec.
- [ ] 5.2 Manual:
  - in the admin, open a configuration without recommendations: weights and params are
    read-only;
  - `npm run manage -- check` passes;
  - a dashboard issue of unknown difficulty shows "Difficulty not estimated (too few
    signals)".
- [ ] 5.3 `Bug_Backlog.md`:
  - D-8, D-9, D-12, D-13, D-15, D-16, D-17, D-18 marked `fixed (signal-explanation-accuracy)`;
  - remove them from Open items and the triage table;
  - the batch 8 row and the "Next" line keep B-6 and D-11;
  - add the 0.12.15 row to "Fixed by release".
- [ ] 5.4 CLAUDE.md §7: shipped entry, with the K-1 carry-over unchanged.
- [ ] 5.5 Release housekeeping (CLAUDE.md §8), patch release 0.12.15:
  - `VERSION`, the package files and lockfiles;
  - `CHANGELOG.md`, which notes that live issue types and difficulties shift on the next
    fetch;
  - `features.txt`, README status line.
