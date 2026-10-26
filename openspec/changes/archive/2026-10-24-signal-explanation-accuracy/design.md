## Context

See proposal.md for why.
- **Gate.** `score.has_relevance(signals)` checks `signals[name].value > 0` for
  `RELEVANCE_SIGNALS`.
  - `pipeline.rank_pool` calls it to choose the candidates whose issues get matched.
  - `rank` calls it through `is_relevant(scored)`.
  - `Scored.relevance` is the rounded (4 places) sum of the relevance contributions.
- **Reasons.**
  - Since 0.12.14, `explain.reasons` skips a signal whose contribution is 0.
  - `_issue_availability` reads `{"count", "by_type"}` from the `issue_fit` evidence, built in
    `matching.issues.match_issues`.
  - `score_issue` adds a `difficulty` reason only when `issue.difficulty != UNKNOWN`. The
    unknown column of the difficulty-fit table is 0.3–0.5 in v2, so an unknown issue's score
    contains up to 0.25 × 0.5 with no reason.
- **Issue analysis** (`services/issues/`) runs on every issue fetch and is stored on the
  `Issue` row.
  - The benchmark does not run it: dataset issues carry their difficulty, labels and
    technologies (`evaluation/dataset.py`).
  - `labels.normalize` lower-cases, joins separators and strips edge symbols. Since 0.12.15
    `_SCOPE` (`^[a-z ]{1,20}[:/\]]\s*`) also strips a `[type]` scope, whose `[` `_EDGES`
    already dropped (D-13; `ISSUE_TAXONOMY_VERSION` 2026.10.3).
  - `classify.difficulty` measures the body without HTML comments since 0.12.15
    (`_HTML_COMMENT = <!--.*?(?:-->|\Z)`, D-12). It still hard-codes `technology_count >= 2`
    and `MIN_VOTES = 2`, and reads the other thresholds from `settings.ISSUE_DIFFICULTY`. The
    startup check `core.E040` validates `ISSUE_DIFFICULTY`.
- **Configurations.**
  - `config.validate` checks openness points as a unit map (each 0..1), not their sum.
  - `ScoringConfigAdmin.get_readonly_fields` locks version, weights and params only when
    recommendations reference the row.
  - Activation (`services/ranking/activation.py`) and the seeds change `is_active` only, through
    `QuerySet.update`.
  - Migrations use historical models, so they bypass a model's `save()`.

## Goals / Non-Goals

**Goals:**
- v1 and v2 produce identical scores, ranks and signal values on every benchmark dataset;
  `baselines.json` stays byte-identical.
- Every number in a stored score or issue score has a reason or a recorded vote behind it.

**Non-Goals:**
- B-6 (experience cutoffs) and D-11 (title keyword order); see proposal.md.
- Removing the neutral difficulty fit for unknown issues. The spec gives it a configured value,
  and dropping it is a ranking change.
- Making `ISSUE_DIFFICULTY` part of `ScoringConfig`. Issue analysis is shared across users and
  configurations, so a per-configuration threshold would need per-configuration analyses.
- Guarding `QuerySet.update` or raw SQL against edits to a configuration's numbers. The guard
  covers the admin and model saves, the paths an operator uses.

## Decisions

**D1. The gate is `weights[name] > 0 and value > 0`, computed once into `Scored`.**
- `has_relevance(signals, weights)` takes the configuration's weights, and pipeline passes them.
- `Scored` gets a `relevant: bool` set by `score_candidate`; `is_relevant` returns it.
- *Why not `Scored.relevance > 0`:* that value is rounded to 4 places. A tiny contribution, say
  weight 0.1 × value 0.0004, would round to 0 and drop a candidate that passes today, which is a
  ranking change.
- *Why the weight and not the contribution:* with relevance scaling the relevance contributions
  are never scaled, so weight > 0 and value > 0 is the same test, without rounding.
- v1 and v2 weight every relevance signal above 0, so neither result changes.

**D2. Issue availability text from a technology-matched count.**
- `match_issues` adds `"technology_count"`, the kept issues with tech > 0, to the `issue_fit`
  evidence item.
- `_issue_availability` picks one of three openings:

  | Technology-matched | Text |
  |---|---|
  | all N | "1 open issue mentions technologies you use" / "N open issues mention technologies you use" |
  | 0 | "1 open issue is labeled good first issue or help wanted" / "N open issues are labeled good first issue or help wanted" |
  | M of N | "N relevant open issues, M mentioning technologies you use" |

- The `, including …` suffix is unchanged.
- *Stored evidence from older generations* has no `technology_count`. The text treats a missing
  count as "all", which is today's wording. The next generation (freshness sweep) rewrites the
  evidence. No data migration.
- *Alternative:* per-issue reason types in the evidence. Rejected: the count is all the text
  needs.

**D3. Unknown-difficulty reason.**
- In `score_issue`, when `issue.difficulty == UNKNOWN and diff_fit > 0`, append
  `(weights["difficulty"] * diff_fit, {"type": "difficulty", "text": "Difficulty not estimated
  (too few signals)", "detail": {"difficulty": "unknown", "estimated": False}})`.
- The reason types per issue stay unique (`technology`, `difficulty`, `approachability`), which
  the issue detail page relies on for its React keys.
- Scores are unchanged.

**D4. Issue analysis thresholds (D-18).**
- `ISSUE_DIFFICULTY` gains `several_technologies: 2` and `min_votes: 2`.
  - `classify.difficulty` reads both, and they join the evidence's `thresholds`. `MIN_VOTES`
    goes.
  - `ISSUE_DIFFICULTY_KEYS` in `core/checks.py` adds the two keys, so a partial override in
    `.env` still merges onto the defaults (`base.py` spreads the JSON over them).
  - New `core.E040` messages: `several_technologies` must be at least 2 and at most
    `many_technologies`; `min_votes` must be at least 2 (the spec's floor).
- The defaults equal the hard-coded values, so every analysis is unchanged and
  `ISSUE_TAXONOMY_VERSION` stays 2026.10.3 (the label taxonomy does not change).
- D-12 and D-13 shipped in 0.12.15 as described in Context; the `issue-analysis` delta records
  them and needs no code. As built, D-13 adds `]` to the scope separators after `_EDGES` drops
  the `[`, rather than matching the bracket before the edges are stripped; `[Bug]` → `bug` and
  emoji labels still hold.

**D5. Openness sum.**
- `validate` adds `"openness points must sum to at most 1"` when every point is a number and
  the sum exceeds 1 by more than 1e-6.
- Stored configurations go through the same check: v1 and v2 sum to exactly 1.0 (0.4 + 0.3 +
  0.2 + 0.1), so the tolerance matters.

**D6. Immutable stored configurations.**
- `ScoringConfigAdmin.get_readonly_fields` returns version, weights and params for every saved
  row (`obj is not None`).
- `ScoringConfig.save()` loads the stored `version, weights, params` when `self.pk` exists and
  raises `ImmutableConfig` (a `ValidationError` subclass, so the admin shows it) when any
  differs.
  - `is_active` and `description` stay writable.
  - `update_fields` that leave out the three fields skip the check.
- Seeds and activation use `QuerySet.update` or historical models, so neither is affected.
- *Alternative:* a database trigger. Rejected: heavier than the risk, and the spec's operator
  path is the admin.

## Risks / Trade-offs

- [A test or fixture edits a stored configuration in place] → Tests that need different numbers
  create a new version. The apply step fixes any test the guard trips.
- [Old recommendations keep the "match your profile" text until regenerated] → The freshness
  sweep regenerates them within its normal cycle. D2's fallback keeps them readable.
- [`min_votes` set high makes every difficulty `unknown`] → Allowed: it is the operator's
  choice, and `unknown` is the safe value. The check enforces only the floor.

## Migration Plan

- No schema migration.
- Deploy, then wait for the freshness sweep to regenerate (new reason texts). Issue analyses
  need no refetch: D-18's defaults change nothing.
- Rollback: revert the release. The next generation writes the old reason texts back.
