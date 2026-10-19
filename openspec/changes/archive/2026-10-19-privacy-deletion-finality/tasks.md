## 1. Job write guard (A-1, B-4)

- [x] 1.1 Add `job_write(job_id)` in `services/job_guard.py` (atomic + `select_for_update` on the SyncJob row; `JobCancelled` unless RUNNING); move `JobCancelled` to `services/errors.py` (no import cycle with `services/jobs.py`)
- [x] 1.2 Replace the inline status check in `RecommendationService._persist` with `job_write`
- [x] 1.3 `services/github/sync.py`: wrap each step's user-data write block (profile, readme, repositories, languages, topics, dependencies, contributions) in `job_write(self.job.pk)`; keep fetches outside the block
- [x] 1.4 `services/discovery/service.py`: wrap candidate, discovery-record and pool writes in `job_write`; leave shared repository upserts unguarded
- [x] 1.5 `ProfileAnalysisService(user, job_id=...)`: `_persist` under `job_write`; `run()` re-raises `JobCancelled`; pass the job id from `sync._step_analysis` and `developers/tasks.py`; the task finishes CANCELLED on `JobCancelled`
- [x] 1.6 Tests: for sync, analysis, discovery and ranking, delete GitHub data between a step's fetch and its write (patch the fetch to call `delete_github_data`) → nothing is written, the job ends cancelled; a guarded write that commits first is removed by the deletion; the guard raises for CANCELLED and missing jobs

## 2. Identity cleanup (A-7, A-8, A-12, A-19)

- [x] 2.1 `delete_github_data` clears `user.display_name`
- [x] 2.2 `services/audit.py`: `IDENTIFYING_METADATA_KEYS` and `anonymize_user_entries(user)` (empty `ip_hash`, drop identifying keys); call it in account deletion after recording `account_deleted`, before deleting the user
- [x] 2.3 Disconnect rotates the session auth hash (`set_unusable_password()` + save) before `logout(request)`
- [x] 2.4 `_revoke_and_unlink` no longer calls `cancel_active_syncs`
- [x] 2.5 Tests: display name empty after delete-data and disconnect; after account deletion, earlier sign-in entries keep action/outcome/time with no user, `github_id`, `github_username` or `ip_hash`; a second client's session is unauthenticated after disconnect from the first; jobs are cancelled exactly once

## 3. Replaced token revocation (A-9)

- [x] 3.1 Add `oauth.revoke_token(access_token)` (`DELETE /applications/{client_id}/token`, basic auth, 204/404 ok, `OAuthError` otherwise)
- [x] 3.2 `link_github_account`: if an account exists and its decrypted token differs from the new one, revoke the old token `on_commit`, best effort (log failure type only); an undecryptable old token is skipped
- [x] 3.3 Tests (respx): returning sign-in with a new token calls the token endpoint with the old token only, never the grant endpoint; same token → no call; revocation failure still signs in and logs no token

## 4. Benchmark export (E-3)

- [x] 4.1 `export_developer(..., include_interacted=False)`: drop candidates with a `previously_interacted` discovery for the profile or a `UserRepository` link for the user; return the dropped count
- [x] 4.2 `export_benchmark_developer --include-interacted`; print the dropped count to stderr
- [x] 4.3 Tests: searched + contributed candidates → only searched exported by default, both with the flag; existing export tests still pass

## 5. Privacy page (H-8, H-9)

- [x] 5.1 Update `PrivacyPage.tsx` categories per design D9
- [x] 5.2 Frontend test: the page lists account ID retention "until you delete your account", job history, candidate pool/search queries, sessions, and audit entries without identifying values

## 6. Verification and housekeeping

- [x] 6.1 Backend: pytest, ruff check + format check, mypy
- [x] 6.2 Frontend: typecheck, lint, format check, tests
- [x] 6.3 Manual: sign in, delete GitHub data while a sync runs → dashboard empty and onboarding shown, nothing reappears after the sync finishes; disconnect in one browser ends a second browser's session
- [x] 6.4 Mark A-1, A-7, A-8, A-9, A-12, A-19, B-4, E-3, H-8, H-9 `fixed` in `Bug_Backlog.md`; CHANGELOG `[Unreleased]` entry
