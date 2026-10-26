## Why

Batch 8 of `Bug_Backlog.md` (signal and explanation accuracy) was parked until K-1 because it
is ranking-visible. 0.12.14 shipped B-14, B-15, B-16 and D-7, and 0.12.15 shipped D-12 and
D-13, without a spec change. Re-checked on 2026-10-22 and 2026-10-23, the rest of this change
leaves the v1 and v2 benchmark numbers alone:
- they touch only explanation text;
- or validation, which v1 and v2 pass;
- or issue analysis, which the benchmark does not run (its issues carry stored difficulty).

**Shipped in code, missing from the specs** (this change records them; no code work):
- **D-7** (0.12.14). `recommendation-explanations` still says "a signal whose value is above
  0". The code also requires a weight above 0.
- **D-12** (0.12.15). The description-length difficulty vote ignores issue-template HTML
  comments (`<!-- Describe the bug -->`, `classify._HTML_COMMENT`). `issue-analysis` does not
  say so.
- **D-13** (0.12.15). `[Type] Bug`-style labels are normalized like `Type: Bug`
  (`labels._SCOPE`, `ISSUE_TAXONOMY_VERSION` 2026.10.3). `issue-analysis` lists only `:` and
  `/` scopes.

**Still to build**, and can ship without a ranking search:
- **D-8.** The relevance gate checks raw signal values. A configuration that weights a
  relevance signal 0 still lets that signal admit a candidate.
- **D-9.** "3 open issues match your profile" is said even when the issues matched only through
  a `good first issue` or `help wanted` label. The spec allows such issues to count; the wording
  claims a profile match that did not happen.
- **D-15.** A scoring configuration stays editable in the admin until a recommendation
  references it. A version that was evaluated, recorded in `baselines.json`, snapshotted by
  feedback or briefly active can still change its numbers under the same name.
- **D-16.** An issue whose difficulty is `unknown` still gets the configured neutral
  difficulty-fit value in its score, but no reason explains that part.
- **D-17.** Openness points are not checked to sum to at most 1. A larger sum silently caps the
  signal at 1, so having every affordance looks the same as having half of them.
- **D-18.** The difficulty vote hard-codes "two technologies vote intermediate" and "a level
  needs two votes". The rule is that thresholds are configuration, and the other four already
  are (`ISSUE_DIFFICULTY`).

Out of scope, and still waiting:
- **B-6** (experience cutoffs): it changes users' experience levels, and which cutoff is right
  needs a decision first.
- **D-11** (title keyword order): it reorders contribution types.

Both stay in batch 8.

## What Changes

- **Relevance gate on contributions (D-8).** A candidate passes the gate only when a relevance
  signal (skill, language, framework, interest) has both a value above 0 and a weight above 0.
  This applies to the issue-matching preselection and to the final cut.
- **Reasons follow the score (D-7, spec only).** A recommendation reason exists only for a
  signal that adds to the score. The code already does this (0.12.14).
- **Issue availability wording (D-9).** The text says how the issues matched:
  - all through technologies: "N open issues mention technologies you use";
  - none through technologies: "N open issues are labeled good first issue or help wanted";
  - a mix: "N relevant open issues, M mentioning technologies you use".

  The evidence records the technology-matched count. The "including N bug-fix issues" suffix
  stays.
- **Unknown difficulty explained (D-16).** An issue of unknown difficulty whose difficulty-fit
  part is above 0 gets a `difficulty` reason, "Difficulty not estimated (too few signals)",
  with detail `{"difficulty": "unknown", "estimated": false}`. Scores are unchanged.
- **Issue analysis.**
  - D-18: `ISSUE_DIFFICULTY` gains `several_technologies` (default 2) and `min_votes`
    (default 2), with startup checks: `several_technologies` from 2 up to `many_technologies`,
    `min_votes` at least 2. The defaults equal today's hard-coded values, so no analysis
    changes and `ISSUE_TAXONOMY_VERSION` stays 2026.10.3.
  - D-12, D-13 (spec only): description length ignores HTML comments, including one left open
    by truncation; a bracketed scope (`[Type] Bug`, `[area] docs`) is stripped like `type:`.
    The code already does both (0.12.15).
- **Configuration validation (D-17).** Openness points must sum to at most 1. v1 and v2 sum to
  exactly 1 and stay valid.
- **Stored configurations are immutable (D-15).**
  - Once saved, a configuration's version, weights and params cannot change: the admin shows
    them read-only on every saved row, and `ScoringConfig.save()` refuses a change to them.
  - Activation and deletion rules are unchanged.
  - A new set of numbers needs a new version.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `recommendation-engine`:
  - "Recommendation score and ranking": the gate needs a relevance signal that contributes to
    the score, not only a value above 0.
  - "Versioned scoring configuration": openness points sum to at most 1, and stored versions
    are immutable.
- `recommendation-explanations`, "Reasons from scoring evidence": a reason only for a signal
  that contributes to the score; issue availability says how the issues matched.
- `issue-matching`, "Issue reasons": an unknown difficulty with a difficulty-fit part above 0
  has a reason saying it was not estimated.
- `issue-analysis`:
  - "Label normalization": bracketed scope prefixes (already implemented, 0.12.15).
  - "Difficulty estimate": description length excludes HTML comments (already implemented,
    0.12.15); the technology-count and vote thresholds are configuration.

## Impact

- Backend:
  - `services/ranking/score.py` (gate) and `pipeline.py` (preselection);
  - `services/ranking/explain.py` (issue availability text);
  - `services/matching/issues.py` (unknown-difficulty reason, technology-matched count);
  - `services/ranking/config.py` (openness sum);
  - `recommendations/models.py` and `admin.py` (immutability);
  - `services/issues/classify.py` (D-18 thresholds only; `labels.py` is unchanged);
  - `config/settings/base.py` and `core/checks.py` (`ISSUE_DIFFICULTY` keys);
  - `.env.example` if it lists `ISSUE_DIFFICULTY`;
  - tests.
- Ranking:
  - v1 and v2 score and rank every benchmark dataset as before, and `baselines.json` is not
    rewritten. The baseline test must pass unchanged.
  - Live data: issue analyses are unchanged (D-18 defaults equal today's values; the D-12 and
    D-13 shifts already shipped in 0.12.15).
- API: reason texts change (D-9), and issues of unknown difficulty gain one reason (D-16). No
  schema change, OpenAPI stays `1.0.0`.
- UI: no code change; the texts come from the API.
- Release: patch 0.12.16. Docs: `Bug_Backlog.md` (batch 8 rows), CHANGELOG, features, README,
  CLAUDE.md §7.
