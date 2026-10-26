## Why

A dismissal says "not for me" but not why. `ideas.md` §4 ("Dismiss reasons", first in the
"can ship now" list): an optional reason (not my stack, too big, inactive, already know it)
turns dismissals into labeled negatives. They tell judging (K-1) what a 0 grade means for real
users, and the feedback report (0.12.20–0.12.21) can show which reasons each scoring
configuration produces, for example "inactive" pointing at the activity signal, "not my stack"
at the technology signals. No ranking change: reasons are recorded and reported, never scored.

## What Changes

- `POST /api/v1/recommendations/{id}/dismiss` accepts an optional body `{"reason": ...}` with
  one of `not_my_stack`, `too_big`, `inactive`, `already_know`. Without a body it works exactly
  as today. An unknown reason is a 400.
- The reason is stored on the `dismissed` feedback event (next to the existing snapshot) and on
  the hidden entry. `GET /api/v1/dismissed` returns it (`null` when none).
- Interface:
  - The one-click Dismiss button is unchanged, so dismissing stays one click and Undo works as
    before.
  - Next to it, a small "Dismiss with a reason" control opens the four reasons; choosing one
    dismisses with that reason. Keyboard and screen-reader usable; Escape closes it.
  - The hidden list shows an entry's reason when it has one.
- `feedback_report` counts dismissals per reason for each configuration (and the JSON gains
  `dismiss_reasons`). Shares are unchanged: a dismissal is decisive with or without a reason.
- Privacy page: the feedback category says hidden projects keep the optional reason.
- No ranking change. OpenAPI stays `1.0.0`: an optional request body and a new nullable response
  field are additive.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `recommendation-feedback`:
  - "Feedback events": a `dismissed` event may carry a reason.
  - "Dismiss recommendations": the optional reason, its values, the 400, and `reason` on the
    hidden list.
  - "Save and dismiss in the interface": dismiss with a reason; one-click dismiss unchanged.
- `recommendation-evaluation`, "Feedback report": dismissals per reason per configuration.

## Impact

- Backend:
  - `feedback/models.py`: `DismissReason` choices; `RecommendationFeedback.dismiss_reason` and
    `DismissedRepository.reason` (blank by default; migration `feedback.0004`, no backfill);
  - `services/feedback.dismiss(user, recommendation, reason="")`;
  - `feedback/serializers.py` (`DismissSerializer`, `reason` on the hidden list), `feedback/api.py`
    (`DismissView` request body);
  - `services/evaluation/feedback_report.py` and the command (reason counts);
  - tests.
- Frontend: `features/feedback/api.ts` (`useDismiss` takes an optional reason),
  `RecommendationActions.tsx` (reason control), `SavedPage.tsx` (reason on hidden entries),
  `routes/PrivacyPage.tsx`; generated `src/api/openapi.json` and `schema.d.ts` (`npm run
  api:sync`); tests. No new dependency.
- e2e: the plain dismiss flow is unchanged; run `npm run e2e` anyway, since the card's actions
  change.
- Release: patch 0.12.23. Docs: README, CLAUDE.md §7, `ideas.md` §4, CHANGELOG, features.
