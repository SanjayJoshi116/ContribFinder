## Context

- `services/feedback.py`: `record` and `save` read only `recommendation.pk` (then `_current`
  re-reads under the lock); `dismiss` reads only `recommendation.repository_id`
  (`_current_recommendation`). `feedback/api._own_recommendation` loads
  `only("pk", "repository_id")` for the ownership 404. `unsave(user, repository_id)` and
  `restore(user, repository_id)` already take ids.
- `services/issues/classify._vote(signal, ...)` writes five names; `LEVEL_VOTERS` repeats them.
  `issues/serializers.IssueAnalysisSerializer.difficulty_evidence` is a `DictField`, so the
  schema says `{[key: string]: unknown}`. `evidence.ts` `SIGNAL_TEXT` is
  `Record<string, …>`.

## Goals / Non-Goals

**Goals:**
- Feedback service signatures that cannot be handed a partly loaded model.
- One declared signal list, checked by the backend tests and by `tsc`.

**Non-Goals:**
- Changing the response body or validating stored evidence on output (old rows stay as stored;
  FI-4: evidence is data, not a promise).
- Retiring `DELETE /recommendations/{id}/save` (separate contract change, ideas.md §15).
- Typing `contribution_type_evidence` (no consumer needs it yet).

## Decisions

- **Ids, not a lighter model or a dataclass.** `record(user, recommendation_id, ...)`,
  `save(user, recommendation_id)`, `dismiss(user, repository_id, reason)`. Each already uses
  exactly that one value; `unsave`/`restore` set the precedent. The view keeps its ownership
  check (`values_list("pk", "repository_id")` instead of `only(...)`), so a foreign id is still
  404 before any service runs. `_current` takes a pk.
- **`DifficultySignal(models.TextChoices)` in `issues/models.py`.** Same place as other choice
  lists that `ENUM_NAME_OVERRIDES` points to; no migration (JSON column, no `choices=` on a
  field). `classify._vote` takes a `DifficultySignal`; `LEVEL_VOTERS` uses its members.
- **Schema-only typing with `@extend_schema_field`.** A `DifficultyEvidenceSerializer`
  (`signals: DifficultyVote[]`, `votes: dict[str, int]`, `thresholds: dict`, all
  `required=False`) documents the shape; the field still outputs the stored dict. Alternative
  (serialize through it) would reject or rewrite old rows; rejected. Enum name pinned with
  `ENUM_NAME_OVERRIDES["DifficultySignalEnum"]` → exported as `DifficultySignal` in
  `src/api/types.ts`.
- **`SIGNAL_TEXT: Record<DifficultySignal, …>`** gives the compile-time check; the
  `Object.hasOwn` filter stays for unknown stored names. `Vote` derives from the schema type
  where it can, keeping `value: unknown`.
- **Replace the regex test** with `test_classifier_writes_declared_signals`: the set
  `classify.difficulty` writes equals `DifficultySignal.values`. The words are then `tsc`'s job;
  `api:sync` drift in CI ties the two.

## Risks / Trade-offs

- [Schema drift between `DifficultyEvidenceSerializer` and what `classify` writes] → the new
  backend test checks names; a test also checks a real evidence dict validates against the
  serializer (`is_valid`), so key renames are caught.
- [47 test call sites change] → mechanical (`rec` → `rec.pk` / `rec.repository_id`); behaviour
  tests stay as they are.
- [Third-party API clients see a richer schema] → additive only; contract stays `1.0.0`.
