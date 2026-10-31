## Why

The review sweep's fourth module, `apps/backend/github/` (`Bug_Backlog.md` batch 29,
GH-1…GH-8), found that deleting GitHub data writes its audit entry outside the deletion's
transaction (and from the view), that the admin can delete a GitHub account without revoking or
deleting anything, that a revocation failing on an unexpected error leaves no traceback, that
eager mode retries a revocation inline with no backoff, and that a raised repository cap hides
repositories past 100 from the dashboard. The security review of the module found nothing
exploitable.

## What Changes

- GH-1: `revoke_later` logs the traceback (`logger.exception`) of an error that is not a GitHub
  error before recording the final failure; the token never appears in it (the task holds
  ciphertext only, and `revoke` raises nothing that carries the plaintext).
- GH-2: `GitHubAccountAdmin` and `GitHubProfileAdmin` have no add and no delete permission:
  removing a connection goes through disconnect, removing data through delete-data.
- GH-3: deleting GitHub data moves to `services/accounts.delete_github_data(user, request)`,
  `@transaction.atomic` around the deletion and its `github_data_deleted` audit entry; the view
  calls it. A failing audit write leaves the data in place.
- GH-4: the owned-repository list's page cap follows `GITHUB_SYNC_MAX_REPOS` (never below 100),
  and the SPA reads every page by following `next`, so every synced repository shows.
- GH-5: `revoke_later` in eager mode (no worker) decides as on its last attempt, like
  `run_tracked_job`: no inline retries inside the request.
- GH-7: the owned-repository query drops its redundant `.distinct()`.
- GH-8: both admins select the user in one query (`list_select_related`).
- GH-6 accepted: the window between reading the stored token and GitHub revoking the grant is one
  GitHub call; no lock can be held across it (no I/O under a lock) and the account row no longer
  exists after a disconnect. A user caught by it signs in again (as ACC-4).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `data-controls`: "Delete GitHub-derived data" (the deletion and its audit entry happen together
  or not at all).
- `sync-jobs`: "Synced data endpoints" (the repository list can return every synced repository
  in one page, whatever the per-sync cap).

## Impact

- `apps/backend/github/{api,admin,tasks}.py`, `services/accounts.py`, tests.
- `apps/frontend/src/features/sync/api.ts` (`useRepositories` follows `next`), its test.
- No API contract change (OpenAPI `1.0.0`; the page cap is not in the schema); no migration; no
  ranking change, baselines unchanged.
