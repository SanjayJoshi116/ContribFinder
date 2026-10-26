## Context

See proposal.md for why.
- `services/feedback.dismiss(user, recommendation)`: under `lock_developer`, creates the
  `DismissedRepository` (get-or-create), records a `dismissed` event with the snapshot of the
  current recommendation, unsaves (`unsaved` event) and deletes the recommendation. The event
  log is append-only; current state lives in `SavedRepository` / `DismissedRepository`.
- `DismissView.post` has no request body (`request=None` in the schema).
- `DismissedRepositorySerializer`: `repository_id`, `repository`, `dismissed_at`; the hidden list
  is keyset-paged (`DismissedPagination`).
- Frontend: `DismissButton` (`RecommendationActions.tsx`) calls `useDismiss().mutateAsync(id)`
  and then `onDismissed` for the Undo notice; `useDismiss` removes the card optimistically and
  rolls back on error. Components: only `button` and `alert-dialog` from shadcn are installed.
- `services/evaluation/feedback_report.py`: `Event` from one `values_list`; per-configuration
  bucket rows, label rows and calibration.
- `tests/test_privacy_coverage.py` checks user-linked models only, so new fields on existing
  models need no entry, but the privacy page text should still say what is kept.

## Goals / Non-Goals

**Goals:**
- A reason, when given, is part of the dismissal's single `dismissed` event, so the event log
  stays append-only and the feedback report can attribute it to a configuration.
- Plain dismissal unchanged (one click, same request, same e2e flow).

**Non-Goals:**
- Free-text reasons (privacy and moderation cost), editing a reason after the fact, reasons on
  restore.
- Using reasons in scoring or discovery (a ranking change for after K-1).

## Decisions

**D1. Reason travels with the dismiss request.**
- `DismissReason(TextChoices)` in `feedback/models.py`: `not_my_stack`, `too_big`, `inactive`,
  `already_know`, labels "Not my stack", "Too big", "Inactive", "Already know it".
- Fields: `RecommendationFeedback.dismiss_reason` and `DismissedRepository.reason`, both
  `CharField(max_length=20, choices=DismissReason.choices, blank=True, default="")`. Migration
  `feedback.0004` (adds two columns with a default; no backfill, old rows have no reason).
- `services.feedback.dismiss(user, recommendation, reason="")`: sets `reason` when the hidden
  entry is created and passes it to the `dismissed` event (`_event(..., dismiss_reason=)`).
  Re-dismissing an already hidden repository (not reachable from the interface) records no new
  event and leaves the stored reason, as today.
- `DismissSerializer(reason: ChoiceField(required=False, allow_blank=False))`; `DismissView`
  validates `request.data` (empty body → no reason) and documents the request body
  (`request=DismissSerializer`). Unknown value → 400 through the error envelope.
- *Alternative:* add the reason later from the Undo notice. Rejected: the `dismissed` event
  already exists by then, so it needs an extra event type or an update of an append-only row,
  and the report could not tie it to the snapshot cleanly.

**D2. Hidden list returns the reason.**
- `DismissedRepositorySerializer.fields` adds `reason`, `null` when blank (a
  `SerializerMethodField` typed as the enum or null, so OpenAPI shows a nullable
  `DismissReasonEnum`).

**D3. Interface: a separate reason control, no new dependency.**
- `DismissButton` keeps its button. A second small icon button ("Dismiss with a reason",
  `aria-haspopup="menu"`, `aria-expanded`) toggles an inline `role="menu"` list of four
  `role="menuitem"` buttons positioned under it. Escape or a click outside closes it and returns
  focus to the toggle; arrow keys move between items.
- Choosing an item calls the same dismiss flow with the reason (`useDismiss().mutateAsync({ id,
  reason })`); the Undo notice and optimistic removal are unchanged.
- `useDismiss` sends a JSON body only when a reason is given, so a plain dismiss sends the
  request it sends today.
- `SavedPage` shows "Reason: Too big" (the label) under a hidden entry with a reason.
- Reason labels live in one map in `features/feedback/messages.ts` (or the existing messages
  module), shared by the menu and the hidden list.
- *Alternative:* `@radix-ui/react-dropdown-menu`. Rejected for now: one small menu does not
  justify a new dependency; revisit if more menus appear.

**D4. Feedback report counts reasons.**
- `Event` gains `dismiss_reason` (default ""); `load` reads it.
- Per configuration: `dismiss_reasons: dict[str, int]` over attributed `dismissed` events,
  keyed by reason, with `""` reported as `none`. Shares, buckets, labels and calibration are
  untouched.
- Command prints `dismiss reasons: inactive 6, not_my_stack 3, none 4` per configuration (only
  when it has dismissals); JSON key `dismiss_reasons` per configuration.

## Risks / Trade-offs

- [Few users give a reason, so counts stay small] → The report shows "none" next to the reasons,
  so coverage is visible.
- [A home-made menu has accessibility gaps] → Tested with Testing Library by role and keyboard
  (open, arrow, Escape, focus return); the plain Dismiss button remains the primary path.
- [The card gets busier] → The reason control is an icon button with a tooltip-style label, next
  to Dismiss.

## Migration Plan

- Migration `feedback.0004` adds two defaulted columns; safe online. Deploy backend and the
  regenerated schema with the frontend.
- Rollback: revert the release; reverse the migration to drop the columns (reasons are lost).
