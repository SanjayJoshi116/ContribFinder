## Context

See proposal.md for motivation. State this builds on (v0.5.0):

- Per-user data: `GitHubAccount` (encrypted token), `GitHubProfile` (incl. raw profile README), `UserRepository` links (owner/contributor) to shared `Repository` rows, `DeveloperProfile` (cascades skills, interests, evidence, `RepositoryCandidate`/`CandidateDiscovery`, `Recommendation`/`RecommendationReason`), `SyncJob` history, `AuditEvent` (user FK `SET_NULL`).
- Shared data: `Repository` and its languages, topics, dependencies, README, snapshots are shared across users. Evidence rows point at repositories with `SET_NULL`.
- GitHub responses are cached in Redis per scope: `github:etag:{scope}:{digest}` and `github:ratelimit:{scope}`, with scope = user pk for user-token calls and `public` for shared repository calls (`GITHUB_ETAG_TTL` 24h).
- Disconnect today cancels jobs, revokes the grant, deletes `GitHubAccount`, audits and logs out; all derived data is kept.
- The refresh chain already exists: sync (its final step is profile analysis) → `start_discovery_after` → `start_recommendations_after`. Each stage is its own `SyncJob` with a status endpoint the dashboard polls.
- `Recommendation` ids are stable across regenerations (upsert per developer and repository); a generation loads candidates in `load_candidates` and persists in one transaction.
- Onboarding starts a sync only on a button press; the dashboard redirects to onboarding when there is no `last_synced_at`.

## Goals / Non-Goals

**Goals:**
- One deletion routine shared by "delete GitHub data", disconnect and account deletion, so the three can never drift apart.
- Feedback that stays interpretable after recommendations change (snapshot fields), without influencing ranking.
- Dismissals honored by every generation, including one already running.

**Non-Goals:**
- Personalized ranking from feedback (post-MVP), notes on saved projects (SRS-2 §58 "future version").
- Issue interactions beyond accepting `opened_issue` events (issue UI arrives in Phase 7).
- Delayed or soft deletion, data export, and email confirmation of deletion.
- Purging `public`-scope cached GitHub responses: they hold public repository data shared by all users and expire within 24 hours.

## Decisions

### D1. Data model (new `feedback` app)

- `RecommendationFeedback`: FK user (CASCADE), FK repository (`SET_NULL`, nullable), FK recommendation (`SET_NULL`, nullable), `repository_full_name` (snapshot), `action` (choices), `match_label`, `rank`, `config_version` (snapshots, blank/nullable when unknown), `created_at`; index (user, recommendation, action, -created_at) for the view de-duplication query.
  - Why snapshots and `SET_NULL`: SRS-2 §59 wants feedback independent of the recommendation; the snapshot keeps an event meaningful for evaluation after regeneration, and `SET_NULL` keeps other users' events when a shared repository is deleted.
- `SavedRepository`: FK user, FK repository (CASCADE), `saved_at`; unique (user, repository).
- `DismissedRepository`: FK user, FK repository (CASCADE), `dismissed_at`; unique (user, repository).
- Why separate tables rather than deriving state from the event log: save/dismiss are current state that ranking and the list read on every request; the log is append-only history.
- `AuditEvent.Action` gains `github_data_deleted` and `account_deleted`.

### D2. Feedback, save and dismiss services (`services/feedback.py`)

- `record(user, recommendation, action)`: snapshots label, rank and config version. For `viewed`, skip when the same user and recommendation has a `viewed` event newer than `FEEDBACK_VIEW_DEDUP_MINUTES` (30).
- `save(user, recommendation)` / `unsave(user, repository)`: `get_or_create` / delete, each recording its event (only when the state actually changed).
- `dismiss(user, recommendation)`: in one transaction create `DismissedRepository`, delete the recommendation, delete a `SavedRepository` for the same repository, and record `dismissed`. `restore(user, repository)`: delete the dismissal, record `undismissed`, and `start_recommendations(user)`.
- Recommendation-scoped endpoints look the recommendation up within the user's own recommendations (404 otherwise), like the detail endpoint.

### D3. Dismissals in ranking

- `load_candidates(profile)` excludes candidates whose repository the profile's user has dismissed (`~Exists(DismissedRepository…)`).
- `RecommendationService._persist` re-reads the user's dismissed repository ids inside its transaction and drops them from the kept list before upserting, so a dismissal made while the job ran is honored (spec scenario "Dismiss during a generation"). Ranks stay contiguous among the remaining ones.

### D4. API (`feedback/api.py`, routes under `/api/v1`)

- `POST /recommendations/{id}/feedback` `{action: viewed|opened_repository|opened_issue}` → 204 (other actions → 400).
- `POST|DELETE /recommendations/{id}/save` → 200 `{saved}`; `POST /recommendations/{id}/dismiss` → 204.
- `GET /saved` (paginated, `-saved_at`): repository summary, `saved_at`, current activity label (latest snapshot), `recommendation: {id, match_label, reasons} | null`. `DELETE /saved/{repository_id}` → 204.
- `GET /dismissed` (paginated): repository summary, `dismissed_at`. `DELETE /dismissed/{repository_id}` → 204 (restore).
- The recommendation list and detail serializers gain `saved` through an `Exists` annotation, so the list query count stays constant.

### D5. Deletion routine (`services/data_deletion.py`)

`delete_github_data(user) -> dict[str, int]` in one transaction, after `jobs.cancel_active_syncs(user)`:
1. collect the repository ids the user touches (links, candidates, recommendations, saves, dismissals);
2. delete the user's `DeveloperProfile` (cascades skills, interests, evidence, candidates, discoveries, recommendations, reasons), `GitHubProfile`, `UserRepository`, `SavedRepository`, `DismissedRepository`, `RecommendationFeedback`, `SyncJob`;
3. delete the collected repositories that no longer have any link, candidate, recommendation, save or dismissal (one `DELETE … WHERE NOT EXISTS …` statement, so another user's concurrent reference either wins or blocks on the row lock);
4. return counts for the audit entry.

After commit, `purge_user_github_cache(user.pk)` deletes `github:etag:{pk}:*` and `github:ratelimit:{pk}`: on Redis through the backend's client with `SCAN MATCH` (prefix-aware), on the in-process cache by key iteration. A purge failure is logged, not raised: entries expire within `GITHUB_ETAG_TTL`.

- Callers:
  - `DELETE /profile/github-data`: routine → audit `github_data_deleted` (counts) → 204, keeping the account and connection;
  - disconnect: the current flow plus the routine before logout; audit metadata gains the counts;
  - `DELETE /auth/account`: cancel jobs → revoke grant (failure recorded) → routine → audit `account_deleted` (user still set) → `user.delete()` (cascades `GitHubAccount`; audit entries become user-less via `SET_NULL`) → logout → 204.
- Why a service rather than relying on cascades from `User`: "delete GitHub data" must keep the user, and shared repositories never cascade from a user, so the orphan step is needed in every path.

### D6. Refresh visibility (FR-DATA-002)

No backend change: the chain exists. A `usePipelineStage()` hook combines the three status queries already polled (sync: `analysis` step running → "Analyzing your profile", other steps → "Syncing GitHub data"; discovery active → "Finding projects"; generation active → "Preparing recommendations") and renders one line near the Refresh button. A backend test drives the whole chain with stubbed stages to pin the order.

### D7. Frontend

- Card and detail: Save/Saved toggle (optimistic update of the list and detail caches, rolled back on error) and Dismiss (removes the card from the cached list, shows an Undo button for a few seconds that calls restore).
- Events: the detail page posts `viewed` once on mount; GitHub links post `opened_repository` with `fetch(…, {keepalive: true})` and never block the navigation or show errors.
- `/app/saved`: saved projects (with a "No longer recommended" note when `recommendation` is null) and a "Hidden projects" list with Restore.
- Dashboard "Your data" section (next to Disconnect): "Delete GitHub data" and "Delete account" `AlertDialog`s listing what goes. After success: delete-data refetches `/auth/me` and the dashboard, which falls through to onboarding; delete-account clears the query cache and navigates to `/`. The existing disconnect copy changes from "kept until data deletion ships" to "deletes your GitHub data".
- Public route `/privacy` (outside `RequireAuth`): stored categories, purpose, retention and deletion, linked from the landing page and "Your data".

### D8. Settings

`FEEDBACK_VIEW_DEDUP_MINUTES` (30), with an env override, `.env.example` entry and a system check (positive).

### D9. Carry-over: Ctrl+C

Run the per-runner test from CLAUDE.md §6 in an interactive console (WMI-launched `cmd /K`), fix the runner that breaks console Ctrl+C, and verify with a real Ctrl+C. The user asked to hold that test earlier, so it runs only with their go-ahead; otherwise the task stays open.

## Risks / Trade-offs

- [Disconnect now deletes data (behavior change)] → The confirmation dialog says so, the spec delta records it, and the changelog marks it as a breaking behavior change. Reconnecting starts from scratch.
- [Deleting shared repositories other users are about to reference] → Single-statement delete guarded by `NOT EXISTS`; worst case another user's next discovery re-fetches the repository.
- [Cache purge with the Django Redis backend uses its internal client] → Isolated in one function, tested with both backends; failure only delays expiry by up to 24 hours.
- [Feedback volume] → Views are de-duplicated; events are tiny. Retention of feedback follows the account (deleted with GitHub data), stated on the privacy page.
- [Dismiss removes the recommendation row, so its feedback's recommendation FK becomes null] → Snapshots keep the event meaningful.
- [Undo after dismiss depends on a new generation] → Restore starts one immediately; generation is fast (no GitHub).

## Migration Plan

1. Additive migrations: the `feedback` app tables and the two audit actions.
2. Deploy the backend, then the frontend (types regenerated).
3. Nothing to backfill: existing users start with no saves, dismissals or feedback.

Rollback: revert the frontend and the new endpoints; the new tables can stay. Deletions already performed cannot be rolled back (by design).
