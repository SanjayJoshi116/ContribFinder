## Why

Two rules are enforced by convention or by a regex when the type system could enforce them
(ideas.md §15):

- **Feedback services take ids.** `feedback.record`, `save` and `dismiss` take a `Recommendation`
  that the views load with `only("pk", "repository_id")`; they must not touch
  `recommendation.repository` before their own re-read, or a deferred field costs a hidden query
  and snapshots a stale row (CLAUDE.md §7 rule). They already read only `pk` or
  `repository_id`. `unsave` and `restore` already take ids.
- **Difficulty signal names in the API schema** (`Bug_Backlog.md` SIM2-11, CR-9).
  `tests/test_issue_signal_wording.py` reads `apps/frontend/src/features/issues/evidence.ts`
  with a regex to check every signal the classifier writes has words on the issue page.
  `difficulty_evidence` is a free-form object in OpenAPI, so `tsc` cannot check it.

## What Changes

- `feedback.record(user, recommendation_id, action, *, issue_id=None)`,
  `feedback.save(user, recommendation_id)`, `feedback.dismiss(user, repository_id, reason="")`.
  Views pass ids from their ownership check. Behaviour unchanged.
- A `DifficultySignal` choice list (`label`, `body_length`, `technology_count`,
  `contribution_type`, `comments`) is the one list the classifier writes from.
- The issue detail schema describes `difficulty_evidence`: `signals` (each with `signal`:
  `DifficultySignal`, `vote`: difficulty or null, `value`), `votes`, `thresholds`, all optional.
  The response body is unchanged (stored evidence passed through as before). OpenAPI addition,
  not breaking: the contract stays `1.0.0`.
- `evidence.ts`: `SIGNAL_TEXT: Record<DifficultySignal, …>`, so a signal without words fails
  `npm run typecheck`; the regex test is replaced by a backend test that the classifier writes
  exactly the declared signals.
- No ranking, data or migration change. Patch release.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `issue-matching`: adds "Difficulty signals are declared in the API schema".

## Impact

- Backend: `services/feedback.py`, `feedback/api.py`, `issues/models.py` (choices only, no
  migration: the column is JSON), `services/issues/classify.py`, `issues/serializers.py`,
  `config/settings/base.py` (`ENUM_NAME_OVERRIDES`); about 47 test call sites move to ids.
- Frontend: `src/api/openapi.json`, `src/api/schema.d.ts` (`npm run api:sync`),
  `src/api/types.ts` (`DifficultySignal`), `src/features/issues/evidence.ts`.
- Tests: `tests/test_issue_signal_wording.py` replaced; feedback tests updated.
- CLAUDE.md §7: the `recommendation.repository` rule becomes "feedback services take ids"; the
  `SIGNAL_TEXT` rule names the enum.
