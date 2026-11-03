## Context

See proposal.md (Why). `core.admin.ViewOnlyAdmin` (no add, change or delete) is the one
view-only base for job-written data. `NoAddDeleteAdmin` leaves change on, for rows staff may
annotate. Admin tests use `shared_fixtures.assert_view_only` and `changelist_queries`.
`ScoringConfig.save` already raises `ImmutableConfig` when a stored row's version, weights or
params change, and the admin shows those fields read-only.

## Goals / Non-Goals

**Goals:** no admin path deletes job-written or configuration rows; a stored version always
means the same numbers; the offline commands fail with a `CommandError` naming the problem; the
README excerpt keeps the text it shows intact.

**Non-Goals:** changing the baseline rules (REC-5 is specified); reviewing `feedback/` beyond
its admin base (its own sweep); richer markdown handling in the excerpt.

## Decisions

### D1. Admins (REC-1, REC-2, REC-6)

`ReadOnlyAdmin` is deleted. `RecommendationAdmin` uses `ViewOnlyAdmin`, its `readonly_fields`
are removed (redundant without change permission, as ISS-8), and `ReasonInline.can_delete =
False`. `list_select_related = ("developer", "repository", "scoring_config")`: the developer,
repository and scoring_config columns each load their row (`Repository.__str__` and
`ScoringConfig.__str__` read fields; the developer column loads the profile even though its
`__str__` reads only ids).

Feedback admins use `ViewOnlyAdmin`. `RecommendationFeedbackAdmin.list_select_related =
("user",)`; the saved and dismissed admins use `("user", "repository")`. Deleting a
`DismissedRepository` outside `services.feedback.restore` would bring a project back with no
`undismissed` event and no generation.

`ScoringConfigAdmin` subclasses `NoAddDeleteAdmin`. Change stays allowed: the fixed fields are
already read-only for a stored row, and `description` may be edited. Configurations are stored
by migrations (`_seeding.store_inactive`), never through the admin.

### D2. Save of a deleted configuration (REC-4)

In `ScoringConfig.save`, when the instance is not adding, fixed fields are touched and no stored
row is found, raise `ImmutableConfig("A deleted scoring configuration cannot be saved again;
create a new version instead.")`. With `update_fields`, Django already raises when no row is
updated. D1 closes the delete path in the admin; this guard covers code.

### D3. Top N (REC-3)

`top_n = options["top_n"]`; when `None`, the pinned or settings default. A value below 1 raises
`CommandError("--top-n must be at least 1.")`, checked before any dataset is loaded, as
`--resamples` is.

### D4. Judging commands (REC-7)

`sheet._single_developer` raises `SheetError` when the export is not a mapping. A helper,
`_candidates(developer)`, returns the candidate list and raises `SheetError` when it is not a
list of objects that each hold a string `repository`. `write_sheet` and `import_sheet` use it.
`benchmark_sheet` counts its rows from `_candidates`, inside its `try`, before writing the file.

### D5. README excerpt (REC-8, REC-10)

`html.unescape` runs after `plain_text`. `_MARKDOWN_NOISE` keeps stripping heading, emphasis,
quote, code and table marks (`#`, `*`, `>`, backtick, `|`) and image/link brackets, but strips
`_` only at the start or end of a word (`(?<!\w)_+|_+(?!\w)`), so `my_package` keeps its
underscore, and `~` only doubled (`~~`, strikethrough), so `~/.config` keeps its tilde.
The cut is `text[:limit + 1].rsplit(" ", 1)[0]`, so a word ending exactly at `limit` is kept. A
single word longer than the limit is still cut at the limit.

### D6. Status endpoint (REC-9)

The latest row (already read for its config version) gives the last generation time, since
`generated_at` is never null, and `count()` gives the count: three queries instead of four,
with the same response.

## Risks / Trade-offs

- [Staff can no longer fix a bad recommendation or feedback row by hand] → generation rewrites
  recommendations; feedback is append-only history by design; data deletion removes the rest.
- [The excerpt changes text on the detail page] → display only; never scored, not in the
  benchmark.
