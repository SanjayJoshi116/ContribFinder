## 1. Service and queued revocation

- [x] 1.1 ACC-9: task `github.revoke_grant(encrypted)` (decrypt, `oauth.revoke_grant`, retries on temporary failures, logs failure type only; skip a token under a removed key)
- [x] 1.2 ACC-8, ACC-3: `services/accounts.py` `disconnect_github(user, request)` and `delete_account(user, request)`; revocation queued `on_commit`; audit + anonymize + `user.delete()` in one transaction
- [x] 1.3 Views call the service; `DisconnectResultSerializer` choices gain `queued` (`revoked`, `failed` kept, no longer returned)

## 2. Sign-in callback

- [x] 2.1 ACC-1: refuse a deactivated user before linking (queue revocation of the new token, audit `sign_in_failed` reason `account_inactive`, redirect `failed`)
- [x] 2.2 ACC-2: unexpected errors after the exchange → log type, audit `sign_in_failed` reason `internal_error`, redirect `failed`
- [x] 2.3 ACC-6: callback without `throttle_scope`

## 3. Admin, sessions, index

- [x] 3.1 ACC-5: `AuditEventAdmin` without add and delete permissions
- [x] 3.2 ACC-10: `list_select_related`; `AuditEvent` index on `-created_at` (migration `accounts.0004`)
- [x] 3.3 ACC-7: task `accounts.clear_expired_sessions`, daily beat entry

## 4. Tests and checks

- [x] 4.1 Tests: disconnect queues and returns `queued`, never calls GitHub in the request; deletion queues; failed `user.delete()` rolls back the audit entry and anonymization; deactivated user refused (no token stored, no sync, audited); linking error redirects `failed`; callback never 429; admin permissions; expired sessions cleared; revoke task retries and logs without the token
- [x] 4.2 `uv run pytest`, `ruff`, `mypy`, `makemigrations --check`; `npm run api:sync` and frontend `typecheck`, `test`

## 5. Release (workflow steps 6-8)

- [x] 5.1 `/simplify`, then `/code-review` on the fix diff; record and fix (simplify applied while writing; the fix-diff `/code-review` skipped on the owner's decision, 2026-10-30)
- [x] 5.2 Archive (deltas into `github-authentication`, `data-controls`); `Bug_Backlog.md` batch 28 rows marked fixed (ACC-4 accepted)
- [x] 5.3 Release housekeeping (CLAUDE.md §8)
