## Why

The review sweep's next module, `apps/backend/recommendations/` (`Bug_Backlog.md` batch 41,
REC-1…REC-10), found that its admins still let staff delete job-written rows, which is SIM-8
for this module and for `feedback/`, which imports the same base. It also found that
`ScoringConfigAdmin` can delete and add configurations. A version with no recommendations can
be deleted and stored again with other numbers, and the active configuration can be deleted.
Both break "Versioned scoring configuration" in `recommendation-engine`: exactly one
configuration is active, and a stored version keeps its numbers. Smaller findings:
- evaluation accepts a top N below 1;
- the judging commands crash on a malformed export;
- the README excerpt loses words and characters;
- the admin changelists and the status endpoint run extra queries.

REC-5 (`--write-baseline` with `--top-n`) is a false positive: the spec says the baseline is
written "at the pinned minimum score default and top N unless a top N is given". The security
review of the module found nothing.

## What Changes

- REC-1, REC-6: `recommendations.admin.ReadOnlyAdmin` is removed. `RecommendationAdmin` and the
  three feedback admins use `core.admin.ViewOnlyAdmin`, the reason inline cannot delete, and
  every changelist sets `list_select_related`. SIM-8 is closed.
- REC-2: `ScoringConfigAdmin` uses `core.admin.NoAddDeleteAdmin`. Seeds and migrations stay the
  only way to store a configuration. The description stays editable.
- REC-4: `ScoringConfig.save` refuses to save an existing instance whose row is gone, instead
  of inserting it again with the numbers it holds.
- REC-3: `evaluate_ranking --top-n` below 1 is refused, and `--top-n` is read with `is not None`.
- REC-7: `services/evaluation/sheet.py` raises `SheetError` for an export that is not an
  object, or for a candidate without a repository name. `benchmark_sheet` counts its rows before
  writing anything.
- REC-8, REC-10: `readme_excerpt` keeps a complete last word, strips `_` only at word edges and
  `~` only as `~~`, and unescapes HTML entities.
- REC-9: `RecommendationStatusView` takes the last generation time from the latest row (no
  separate `Max`).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None (`skip_specs: true`). REC-2 and REC-4 make the code follow "Versioned scoring
configuration" (`recommendation-engine`). REC-3 and REC-7 are error handling of offline
commands. REC-8 and REC-10 keep the README excerpt as specified: plain text with a capped length.
REC-9 and the admin fixes leave the specified behavior unchanged.

## Impact

- `apps/backend/recommendations/{admin.py,models.py,serializers.py,api.py}`,
  `recommendations/management/commands/{evaluate_ranking,benchmark_sheet}.py`,
  `apps/backend/feedback/admin.py`, `services/evaluation/sheet.py`, tests.
- No migration, no API shape change (OpenAPI `1.0.0`; `npm run api:sync` must show no drift),
  no frontend change, no ranking change (baselines unchanged).
