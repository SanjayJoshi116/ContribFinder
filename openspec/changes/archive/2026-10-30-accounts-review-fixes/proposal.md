## Why

The review sweep's third module, `apps/backend/accounts/` (`Bug_Backlog.md` batch 28,
ACC-1…ACC-10), found that a deactivated user can still sign in (token stored, sync queued, then
signed out at once), that an unexpected error during sign-in shows a raw JSON 500 page, that
account deletion is not atomic, that staff can delete audit entries, that sessions are never
purged, and that disconnect and account deletion keep business logic in views and call GitHub
inside the request (against invariant 3). The security review of the module found nothing
exploitable.

## What Changes

- ACC-1: the callback refuses a deactivated user before storing the token: no session, a
  `sign_in_failed` audit entry (reason `account_inactive`), the new token's revocation queued,
  redirect with the `failed` error code.
- ACC-2: any unexpected error after the code exchange is logged (type only), audited as a sign-in
  failure and redirected with `failed`, never a raw 500.
- ACC-3: account deletion records its audit entry, anonymizes the trail and deletes the user in
  one transaction, then ends the session.
- ACC-5: the audit admin is read-only: no add, no delete.
- ACC-6: the callback is no longer throttled (it needs a single-use state from the session, which
  only the throttled sign-in start issues), so a busy network never shows a raw 429 there.
- ACC-7: a daily beat task removes expired sessions.
- ACC-8: disconnect and account deletion move to `services/accounts.py`
  (`disconnect_github(user, request)`, `delete_account(user, request)`); the views call them.
- ACC-9: GitHub revocation is queued (`github.revoke_grant` task, encrypted token only), as
  sign-in already does for a replaced token. The stored token is deleted at once. The disconnect
  response reports `queued` (or `not_connected`); the task logs a failure without the token.
- ACC-10: the audit changelist selects users in one query; `AuditEvent` gets an index on
  `-created_at`.
- ACC-4 accepted: a sign-in completed after a disconnect is a new sign-in the user finished
  themselves (consent given on GitHub), and it re-creates the link as "Sign in again after
  disconnect" specifies.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `github-authentication`: "Handle the authorization callback" (deactivated user, unexpected
  error), "Disconnect GitHub" (revocation queued), "Audit trail for sensitive account actions"
  (disconnect records that revocation was queued).
- `data-controls`: "Delete account" (revocation queued; deletion and its audit are atomic).

## Impact

- `apps/backend/accounts/{views,admin,models,tasks}.py`, new `services/accounts.py`,
  `github/tasks.py`, `config/settings/base.py` (beat entry), migration `accounts.0004` (index),
  tests; `DisconnectResultSerializer` gains `queued`.
- OpenAPI: the `revocation` enum gains `queued`; `revoked` and `failed` stay listed, no longer
  returned. Not a contract break (OpenAPI stays `1.0.0`); the SPA never reads the value.
  `npm run api:sync`.
- No frontend behavior change; baselines unchanged.
