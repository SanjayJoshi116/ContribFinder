## 1. Feedback services take ids

- [x] 1.1 `services/feedback.py`: `record(user, recommendation_id, action, *, issue_id=None)`,
  `save(user, recommendation_id)`, `dismiss(user, repository_id, reason="")`; `_current` takes a pk
- [x] 1.2 `feedback/api.py`: ownership check returns `(pk, repository_id)`; views pass ids
- [x] 1.3 Update test call sites (`tests/test_feedback.py`, `test_data_deletion.py`, others by grep)

## 2. Declared difficulty signals

- [x] 2.1 `issues/models.py`: `DifficultySignal` TextChoices; `classify._vote` and `LEVEL_VOTERS`
  use it
- [x] 2.2 `issues/serializers.py`: `DifficultyVoteSerializer` / `DifficultyEvidenceSerializer`
  (all optional) via `@extend_schema_field` on `difficulty_evidence`; output unchanged
- [x] 2.3 `config/settings/base.py`: `ENUM_NAME_OVERRIDES` entry for the signal enum
- [x] 2.4 Replace `tests/test_issue_signal_wording.py` with: classifier writes exactly
  `DifficultySignal.values`; a real evidence dict validates against the serializer; the issue
  detail response body is unchanged

## 3. Frontend

- [x] 3.1 `npm run api:sync` in `apps/frontend`; export `DifficultySignal` from `src/api/types.ts`
- [x] 3.2 `evidence.ts`: `SIGNAL_TEXT: Record<DifficultySignal, …>`, keep the unknown-name filter;
  existing `evidence` tests still pass, plus one for an unknown stored signal if missing

## 4. Checks

- [x] 4.1 Backend: `uv run pytest`, `ruff check`, `ruff format --check`, `mypy`
- [x] 4.2 Frontend: `npm test`, `npm run lint`, `npm run format:check`, `npm run typecheck`,
  `npm run build`; confirm a missing `SIGNAL_TEXT` key fails `typecheck` (then revert)

## 5. Docs and release

- [x] 5.1 ideas.md §15: move both ideas to Shipped; `Bug_Backlog.md` SIM2-11 / CR-9 closed
- [x] 5.2 CLAUDE.md §7 rules (feedback services take ids; `SIGNAL_TEXT` keyed by
  `DifficultySignal`); CLAUDE_HISTORY.md entry
- [x] 5.3 Release housekeeping (CLAUDE.md §8): patch bump, CHANGELOG, features.txt, README version
  line, `npm run check:version`
