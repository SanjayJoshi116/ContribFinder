## 1. Backend (D1, D2)

- [x] 1.1 `feedback/models.py`: `DismissReason`; `RecommendationFeedback.dismiss_reason`,
  `DismissedRepository.reason`; migration `feedback.0004` (`makemigrations --settings
  config.settings.test`).
- [x] 1.2 `services/feedback.dismiss(user, recommendation, reason="")`: reason on the new hidden
  entry and its `dismissed` event.
- [x] 1.3 `feedback/serializers.py`: `DismissSerializer`; `reason` (nullable enum) on
  `DismissedRepositorySerializer`. `feedback/api.py`: `DismissView` validates the body and
  documents `request=DismissSerializer`.
- [x] 1.4 Tests:
  - dismiss with `inactive` → event and hidden entry carry it; `GET /dismissed` returns it;
  - dismiss without a body → no reason, `reason: null`, same events as before;
  - unknown reason → 400 `invalid` envelope, nothing dismissed, no event;
  - a dismissed-with-reason repository stays out of the next generation like any dismissal;
  - restore then dismiss again without a reason → no reason.

## 2. Feedback report (D4)

- [x] 2.1 `services/evaluation/feedback_report.py`: `Event.dismiss_reason`; per-config
  `dismiss_reasons`; JSON key. Command prints the reason line.
- [x] 2.2 Tests: the spec scenario (6 inactive, 3 not_my_stack, 4 none) with shares unchanged;
  unattributed dismissals not counted per config; JSON key present and still aggregates only.

## 3. Frontend (D3)

- [x] 3.1 `npm run api:sync`; `useDismiss` takes `{ id, reason? }` and sends a body only with a
  reason; reason labels map.
- [x] 3.2 `RecommendationActions.tsx`: reason toggle and menu (roles, `aria-expanded`, arrow keys,
  Escape and outside click close, focus returns); choosing a reason dismisses with it.
- [x] 3.3 `SavedPage.tsx`: "Reason: …" on hidden entries; `PrivacyPage.tsx`: the feedback
  category mentions the optional dismiss reason.
- [x] 3.4 Tests (Vitest + Testing Library):
  - plain Dismiss sends no body and shows Undo as before;
  - open menu, choose "Too big" → request body `{"reason": "too_big"}`, card removed, Undo shown;
  - keyboard: open with Enter, ArrowDown moves, Escape closes and focuses the toggle;
  - hidden list shows the reason label; none shown without a reason.

## 4. Verification and housekeeping

- [x] 4.1 Backend `ruff check`, `ruff format --check`, `mypy`, `pytest`; frontend lint,
  format:check, typecheck, test, build; `npm run e2e` (the card's actions change); root
  `check:version`; `git diff --exit-code apps/backend/evaluation/baselines.json`.
- [x] 4.2 Manual: dismiss a card with a reason, check the hidden list and
  `npm run manage -- feedback_report`.
- [x] 4.3 Docs: README (dismiss reasons; feedback report reason line), CLAUDE.md §7 shipped entry
  (K-1 carry-over unchanged), `ideas.md` §4 dismiss reasons shipped and priority table,
  `features.txt` planned list.
- [x] 4.4 Release housekeeping (CLAUDE.md §8): patch 0.12.23; `CHANGELOG.md`, `features.txt`,
  README status line.
