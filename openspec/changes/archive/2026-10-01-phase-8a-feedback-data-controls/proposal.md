## Why

Since v0.5.0 developers get explained recommendations but cannot act on them: they cannot keep the projects they like, hide the ones they don't, or leave a trace ContribFinder can later evaluate. They also cannot delete what ContribFinder stored about them: disconnecting GitHub still keeps all synced and derived data ("kept until data deletion ships"). SRS-2 §58–60 and §65–66 (FR-FEEDBACK-001 to 004, FR-DATA-002, FR-DATA-003) close these gaps, and they are the last missing items of the MVP definition of done (save, refresh, disconnect/delete data).

## What Changes

- **Feedback events**: a `RecommendationFeedback` log (viewed, saved, unsaved, dismissed, undismissed, opened repository, opened issue) stored independently of the recommendation, with a snapshot of the match label, rank and scoring config version at the time. Views are de-duplicated per recommendation within a short window. Feedback is for analytics and evaluation only: it does not change ranking yet.
- **Save**: users can save and unsave a recommended repository. Saved repositories survive regenerations and remain listed when they are no longer recommended, with their current recommendation (if any) and repository status. A saved-projects page lists them.
- **Dismiss**: users can dismiss a recommendation. It disappears from the list at once and its repository is excluded from every later ranking run, until the user restores it from the saved-projects page.
- **Refresh (FR-DATA-002)**: the existing Refresh already chains sync → analysis → discovery → recommendations. This change specifies that behavior and makes the dashboard say which stage is running.
- **Delete GitHub data (FR-DATA-003)**: `DELETE /api/v1/profile/github-data` cancels the user's jobs and deletes everything derived from GitHub: profile and README, repository links, developer profile with skills, interests and evidence, candidate pool, recommendations, saves, dismissals, feedback and job history, plus the user's cached GitHub responses. Shared repository data no longer referenced by anyone is removed too. The GitHub connection and the account stay, so the user can sync again.
- **Delete account**: `DELETE /api/v1/auth/account` revokes the GitHub grant, deletes GitHub-derived data and the account itself, and ends the session.
- **BREAKING (behavior)**: disconnecting GitHub now also deletes GitHub-derived data (SRS-2 §66), keeping only the account and its audit trail.
- **Privacy page**: a public `/privacy` page lists what is stored, why, how long, and how to delete it. The dashboard gets a "Your data" section with the delete actions and confirmations.
- **Audit**: GitHub data deletion and account deletion are audit-logged; audit entries survive account deletion without the user reference.
- **Carry-over**: fix Ctrl+C for `npm start` in an interactive Windows console.

## Capabilities

### New Capabilities
- `recommendation-feedback`: feedback events, save/unsave, dismiss/restore, the saved-projects page, the saved state on recommendations, and the exclusion of dismissed repositories from ranking (FR-FEEDBACK-001 to 004).
- `data-controls`: refresh of the whole pipeline with stage visibility, deletion of GitHub-derived data, account deletion, the privacy page and retention statement, and their audit entries (FR-DATA-002, FR-DATA-003).

### Modified Capabilities
- `github-authentication`: disconnecting GitHub also deletes GitHub-derived data; the audit trail also covers GitHub data deletion and account deletion.

## Impact

- **Backend**:
  - new `feedback` app: `RecommendationFeedback`, `SavedRepository`, `DismissedRepository`; API for feedback, save, dismiss, saved and dismissed lists;
  - `services/feedback.py` (recording, de-duplication, save/dismiss) and `services/data_deletion.py` (one deletion routine used by delete-data, disconnect and account deletion, including orphaned shared repositories and the user's cached GitHub responses);
  - `services/matching/features.load_candidates` excludes dismissed repositories; the recommendation serializer gains `saved`;
  - `accounts`: account deletion endpoint, disconnect calls the deletion routine, two new audit actions;
  - `github`: `DELETE /profile/github-data`.
  - Migrations are additive.
- **Frontend**: save/dismiss actions on cards and the detail page, view and GitHub-link events, a saved-projects page with restore, a pipeline stage line on the dashboard, a "Your data" section with confirm dialogs, and a public privacy page. API types are regenerated.
- **GitHub API usage**: only the existing grant revocation on disconnect and account deletion.
- **Privacy**: deletion is complete and immediate for relational data; shared public repository data is kept only while another user still references it. Audit entries keep no credentials and lose their user link when the account is deleted.
