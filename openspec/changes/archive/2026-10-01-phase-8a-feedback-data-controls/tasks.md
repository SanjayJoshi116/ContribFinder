## 1. Data model (spec: recommendation-feedback, data-controls; design D1)

- [x] 1.1 Create the `feedback` app with `RecommendationFeedback` (user CASCADE, repository and recommendation SET_NULL, `repository_full_name`, `action`, `match_label`, `rank`, `config_version`, `created_at`, de-duplication index), `SavedRepository` and `DismissedRepository` (unique user+repository)
- [x] 1.2 Add `AuditEvent.Action.GITHUB_DATA_DELETED` and `ACCOUNT_DELETED`. Generate migrations (`--settings config.settings.test`). Register read-only admin views
- [x] 1.3 Add `FEEDBACK_VIEW_DEDUP_MINUTES` (env override, `.env.example`, positive system check)
- [x] 1.4 Tests: unique constraints; feedback survives recommendation and repository deletion (SET_NULL, snapshot kept); saves and dismissals cascade with the user

## 2. Feedback, save and dismiss (spec: recommendation-feedback; design D2, D3)

- [x] 2.1 Implement `services/feedback.py`: `record` (snapshots, view de-duplication), `save`/`unsave`, `dismiss` (dismissal + delete recommendation + unsave + event, one transaction), `restore` (+ event + `start_recommendations`)
- [x] 2.2 Exclude dismissed repositories in `load_candidates`, and drop repositories dismissed during a run inside `RecommendationService._persist` (ranks contiguous)
- [x] 2.3 Tests: view recorded once within the window and again after it; events for each action with snapshots; save idempotent; unsave records once; dismiss removes the recommendation and unsaves; dismissed repository absent after regeneration; dismissal during a run honored; restore starts a generation; feedback does not change scores

## 3. Feedback API (spec: recommendation-feedback; design D4)

- [x] 3.1 Add `POST /recommendations/{id}/feedback`, `POST|DELETE /recommendations/{id}/save`, `POST /recommendations/{id}/dismiss`, `GET /saved`, `DELETE /saved/{repository_id}`, `GET /dismissed`, `DELETE /dismissed/{repository_id}`; add `saved` to the recommendation list and detail serializers via an `Exists` annotation
- [x] 3.2 Tests: each endpoint's shape and status; 404 for another user's recommendation; invalid feedback action → 400; saved list includes a no-longer-recommended repository with `recommendation: null`; `saved` flag on list and detail; list query count constant; CSRF required; 401 signed out
- [x] 3.3 Regenerate the OpenAPI schema and TypeScript types

## 4. Data deletion (spec: data-controls, github-authentication; design D5)

- [x] 4.1 Implement `services/data_deletion.py`: `delete_github_data(user)` (cancel jobs, delete per-user rows, delete orphaned shared repositories, return counts) and `purge_user_github_cache(user_id)` (Redis SCAN and in-process backends; failures logged)
- [x] 4.2 Add `DELETE /api/v1/profile/github-data` (audit `github_data_deleted` with counts; 204) and `DELETE /api/v1/auth/account` (cancel, revoke with recorded failure, delete data, audit `account_deleted`, delete user, logout; 204)
- [x] 4.3 Make disconnect call the deletion routine before logout and add the counts to its audit metadata
- [x] 4.4 Tests: every per-user table empty after delete-data while the account and connection remain; a repository shared with another user's pool is kept, an orphan is deleted; user-scope cache keys purged and `public` keys kept; account deletion removes user, credential and data, keeps a user-less `account_deleted` audit entry and ends the session; revocation failure still deletes; disconnect deletes data; no token in logs or audit metadata; CSRF required

## 5. Refresh pipeline (spec: data-controls; design D6)

- [x] 5.1 Backend test: a refresh with stubbed stage runners completes sync → discovery → recommendation generation in order, and a failed discovery starts no generation and keeps the previous recommendations

## 6. Frontend (spec: recommendation-feedback, data-controls; design D7)

- [x] 6.1 Add feedback hooks: `useSave`/`useUnsave` (optimistic), `useDismiss`/`useRestore`, `recordFeedback` (keepalive, silent), `useSaved`, `useDismissed`
- [x] 6.2 Add Save/Saved and Dismiss (with Undo) to recommendation cards and the detail page; record `viewed` on the detail page and `opened_repository` on GitHub links
- [x] 6.3 Add the `/app/saved` page (saved projects with "No longer recommended", hidden projects with Restore) and a dashboard link to it
- [x] 6.4 Add the pipeline stage line (`usePipelineStage`) next to Refresh
- [x] 6.5 Add the "Your data" section (Delete GitHub data, Delete account, confirm dialogs, privacy link), update the disconnect copy, and add the public `/privacy` page linked from the landing page
- [x] 6.6 Tests (Vitest + RTL): save toggles without reload; dismiss removes the card and Undo restores; detail page records one view; GitHub link records an event without blocking; saved page shows the no-longer-recommended note and Restore; stage line for each stage; delete dialogs require confirmation and redirect correctly; privacy page renders signed out

## 7. Carry-over, verification, docs and release

- [x] 7.1 Ctrl+C carry-over (design D9): with the user's go-ahead, run the per-runner test, fix the culprit, verify with a real Ctrl+C in an interactive console, and update CLAUDE.md §6 Known issues
- [x] 7.2 Manual end-to-end with `npm start`: save, dismiss with undo, saved page, refresh stage line, delete GitHub data then sync again, privacy page; delete account on a test account
- [x] 7.3 Release housekeeping per CLAUDE.md §8 at archive time (v0.6.0): versions and lockfiles, CHANGELOG (disconnect deleting data marked as a behavior change), features.txt (MVP definition of done items), README status, CLAUDE.md (Phase 8a shipped, layout, deviations, carry-overs)
