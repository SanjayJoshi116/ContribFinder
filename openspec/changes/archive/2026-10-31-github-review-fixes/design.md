## Context

See proposal.md (Why) and `Bug_Backlog.md` batch 29. Since 0.12.41, disconnect and account
deletion are `@transaction.atomic` services in `services/accounts.py`; delete-data is the one
leaving flow still assembled in a view. `data_deletion.delete_github_data` already opens its own
inner transaction and purges the user's GitHub cache `on_commit`. `run_tracked_job` treats eager
mode as the last attempt (D4 of `job-claim-fencing`); `revoke_later` does not.

## Goals / Non-Goals

**Goals:** close GH-1…GH-5, GH-7, GH-8 with one test each, without new settings, migrations or
API contract changes.

**Non-Goals:** GH-6 (accepted, see proposal); a generic retry decorator shared by
`run_tracked_job` and `revoke_later`; changing which errors are retried (a database error stays a
final `internal_error`, as for jobs).

## Decisions

**D1 — Delete-data service in `services/accounts.py`.** `delete_github_data(user, request) ->
None`, `@transaction.atomic`, calls `data_deletion.delete_github_data(user)` and records
`GITHUB_DATA_DELETED` with the counts. The view keeps only `current_user` and the 204. It sits
next to `disconnect_github`/`delete_account` (the three user-initiated leaving flows); the name
shadows `data_deletion.delete_github_data`, so callers import the module (`accounts.delete_...`),
never the bare name. The inner job cancel now commits with the outer transaction: a worker that
blocks on the job row sees the cancel at commit, as it already does for disconnect.
Alternative: put the audit inside `data_deletion` — rejected, disconnect and account deletion
audit different actions over the same routine.

**D2 — Repository page cap from the setting.** `RepositoryPagination.max_page_size` becomes a
property returning `max(100, settings.GITHUB_SYNC_MAX_REPOS)` (DRF reads the attribute per
request, so `override_settings` works in tests). The SPA's `useRepositories` keeps
`page_size=100` and follows `next` (read the `page` parameter from it, as `usePagedList` reads
`cursor`) until it is null, returning one page object with every result and the first page's
`count`. Following `next` makes the dashboard correct even if the two values drift again.
Alternative: SPA asks for a huge `page_size` — rejected, it silently depends on the server cap.

**D3 — Eager revocation decides as the last attempt.** `attempts = REVOCATION_ATTEMPTS if
settings.CELERY_TASK_ALWAYS_EAGER else self.request.retries + 1`, the same rule as
`run_tracked_job`. A transient failure in eager mode is recorded as `github_unavailable` at once.
This replaces ACC-17's acceptance (batch 28).

**D4 — Traceback only for non-GitHub errors.** In `revoke_later`, when the error is not a
`GitHubError` (the policy's `internal_error` branch), `logger.exception("GitHub revocation
failed unexpectedly")` before `record_revocation_failure`. GitHub errors keep the code-only
warning. The task holds ciphertext only, and `oauth` builds messages from status codes and type
names, so no token reaches the traceback; a test asserts the plaintext is absent from the log.

**D5 — Admins.** `has_add_permission` and `has_delete_permission` return False on both admins
(as `AuditEventAdmin`), `list_select_related = ("user",)`. Change views stay (read-only fields).

## Risks / Trade-offs

- [The SPA loop issues several requests for a large cap] → at most `cap / 100` requests, only on
  the dashboard after a sync; the default cap needs one.
- [Staff can no longer delete a stuck `GitHubAccount` in the admin] → the user's disconnect, or
  `delete_account`, is the supported path; both revoke.
- [The admin also refuses to delete a User who has a GitHub account or profile (the cascade needs
  delete permission on both)] → intended: that delete would drop the account without revoking
  its token, GH-2's hole; `delete_account` is the path (GH-9).
- [Wrapping the job cancel in the outer transaction delays its visibility to workers until
  commit] → identical to disconnect since 0.12.41; deletion is one short transaction.
