## 1. Backend

- [x] 1.1 FB-1: move the `opened_issue` relevance check into the service (D1).
  - `services.feedback.record(user, recommendation, action, *, issue_id=None)`, after
    `_current(lock=True)`, locks the issue by pk, checks
    `RecommendedIssue(recommendation=current, issue_id=...)`, and raises `IssueNotRelevant` when
    the issue is missing or not linked.
  - `test_services_review_fixes`: an issue deleted before the lock now raises
    `IssueNotRelevant`.
  - `FeedbackView` passes `issue_id`, no longer reads `RecommendedIssue`, and maps
    `IssueNotRelevant` to the 400 `{"issue_id": ...}`.
  - Tests in `tests/test_feedback_review_fixes.py`:
    - an issue removed from the recommendation's relevant issues between the view's ownership
      check and the lock gives 400 and stores no event;
    - an issue id never relevant gives 400;
    - a relevant issue stores the event;
    - a recommendation gone before the lock gives 204 and no event.
- [x] 1.2 FB-5: make `_own_recommendation` a light ownership check (D3).
  - `_own_recommendation` loads `only("pk", "repository_id")`.
  - `dismiss` reads the repository by id inside its transaction (no `recommendation.repository`
    before the re-read).
  - Tests for `POST feedback` (`viewed`), `POST`/`DELETE save` and `POST dismiss`:
    - the ownership `SELECT` joins no repository or configuration;
    - at most two recommendation `SELECT`s;
    - behavior unchanged (existing feedback tests pass).

## 2. Frontend

- [x] 2.1 FB-3: unsave by repository id (D2).
  - The unsave side of `useSaveToggle` (`features/feedback/api.ts`) takes
    `{ id, repositoryId }`, calls `DELETE /saved/{repositoryId}`, and keeps the optimistic update
    and rollback by `id`.
  - `RecommendationActions.tsx` passes `recommendation.repository_id`.
  - Tests: unsave calls `/saved/<repository id>` (`callsTo`); a 404 from the old path is no
    longer possible; the rollback still restores Saved on a 500.

## 3. Backlog

- [x] 3.1 `Bug_Backlog.md` batch 42: FB-1, FB-3 and FB-5 marked fixed (0.12.53); FB-2 and FB-6
  accepted (owner, 2026-11-03) with their reasons; FB-4 false positive and FB-7 wontfix as
  recorded.

## 4. Checks

- [x] 4.1 Backend checks:
  - `uv run pytest`;
  - `uv run ruff check . && uv run ruff format --check .`;
  - `uv run mypy .`;
  - `makemigrations --check --settings config.settings.test`.
- [x] 4.2 Frontend checks: `npm test`, `npm run lint`, `npm run typecheck`,
  `npm run format:check`, `npm run build`.
- [x] 4.3 `npm run api:sync` shows no drift. No e2e run: the change touches no browser flow
  beyond the unsave request.

## 5. Release

- [x] 5.1 `/simplify`, then `/code-review` on the fix diff; record the findings and fix them
  (or the owner skips this step) — skipped by the owner (2026-11-03).
- [x] 5.2 Archive (`skip_specs`); release housekeeping (CLAUDE.md §8, 0.12.53); commit only when
  the owner says so.
