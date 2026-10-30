## Context

Batch 28 of `Bug_Backlog.md` (ACC-1…ACC-10). Owner decision 2026-10-30: revocation is queued
(ACC-9), not kept in the request.

## Decisions

### D1. One service for leaving (ACC-3, ACC-8, ACC-9)

`services/accounts.py`:

- `disconnect_github(user, request) -> str` (`"queued"` | `"not_connected"`): queue revocation
  and delete the `GitHubAccount`, `data_deletion.delete_github_data(user)`, audit
  `github_disconnect` with `revocation`, rotate to an unusable password.
- `delete_account(user, request) -> None`: queue revocation and delete the account, delete
  GitHub data, then one `transaction.atomic()` for the `account_deleted` audit entry,
  `audit.anonymize_user_entries(user)` and `user.delete()`.

Views keep only `current_user`, the call, `logout(request)` and the response. Revocation is
queued with `transaction.on_commit`, so a rolled-back deletion queues nothing.

### D2. Queued revocation (ACC-9)

`github.revoke_grant(encrypted)` (Celery, `acks_late`) decrypts and calls `oauth.revoke_grant`;
like `github.revoke_replaced_token` it gets the token encrypted only (useless without the
server's keys), works after the user is deleted, and logs a failure's type only. Transient
failures are retried through Celery up to 3 times with the existing backoff
(`services/github/retry.py`); a token encrypted with a removed key is skipped. With
`CELERY_TASK_ALWAYS_EAGER` it runs inline, as other tasks do.

### D3. Refuse deactivated users before linking (ACC-1)

After the identity is read, the callback looks up `User(username=f"gh_{github_id}")`; if it
exists with `is_active=False`, it queues revocation of the token just received (single token,
`revoke_token`, through `revoke_replaced_token`'s path), audits `sign_in_failed` with reason
`account_inactive`, and redirects with `failed`. Nothing is stored, no sync starts.

### D4. Unexpected errors in the callback (ACC-2)

`link_github_account`, `login` and the initial sync start run inside `try/except Exception`:
the error type is logged, a `sign_in_failed` (reason `internal_error`) is audited, and the user is
redirected with `failed`. `OAuthError` keeps its own codes.

### D5. Smaller fixes

- ACC-5: `AuditEventAdmin.has_add_permission` and `has_delete_permission` return False.
- ACC-6: `GitHubCallbackView` drops `throttle_scope`.
- ACC-7: beat entry `clear-expired-sessions` → task `accounts.clear_expired_sessions`
  (`SessionStore.clear_expired()` of the configured engine), daily.
- ACC-10: `list_select_related = ("user",)`; `Index(fields=["-created_at"])` (migration
  `accounts.0004`).

## Risks / Trade-offs

- The disconnect response no longer says whether GitHub confirmed revocation; the task's log
  does. The SPA never showed it.
- A deactivated user's GitHub token is revoked on every refused sign-in attempt; that is the
  intent.
