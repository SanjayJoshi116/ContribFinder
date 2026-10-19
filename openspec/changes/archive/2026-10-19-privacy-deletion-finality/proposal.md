## Why

"Delete my data" and "Disconnect GitHub" don't fully do what they promise. Batch 2 of
`Bug_Backlog.md` (verified) found these gaps:
- A sync or analysis that is already running keeps writing after the deletion commits, so
  deleted data comes back (A-1, B-4).
- GitHub identity outlives deletion: in sign-in audit metadata (A-7), in `User.display_name`
  (A-8), and in tokens that a later sign-in replaced but never revoked (A-9).
- Disconnect ends only the current session (A-12).
- The privacy page misstates what is kept and leaves categories out (H-8, H-9).
- The benchmark export is called anonymized, but it names the repositories the developer
  contributed to, which identifies them (E-3).

E-3 has to be fixed before `benchmark-v2` is built and committed (K-1). The rest is a privacy
promise made in the UI.

## What Changes

- **Deletion is final.** Every job step that writes a user's data does so in a transaction that
  locks the user's job and checks it is still running. Deletion cancels the jobs first, so a
  write that is in flight either commits before the deletion (and is then deleted) or sees the
  cancellation and writes nothing. This covers profile sync, profile analysis, discovery and
  recommendation generation.
- **GitHub identity removed on deletion.**
  - Disconnect and "delete GitHub data" clear `User.display_name`.
  - Account deletion clears the GitHub identifiers and the IP hash from the user's audit
    entries. Action, outcome, time, reason and counts stay.
- **Replaced tokens are revoked.** When a returning sign-in stores a new token, the old one is
  revoked on GitHub. This is best effort and never blocks sign-in.
- **Disconnect ends every session** of the user, not only the current one.
- **Privacy page matches what is stored.**
  - The GitHub account ID is kept until account deletion, because it links a returning sign-in
    to the account.
  - Job history, the candidate pool and search queries, and sessions are listed.
  - Audit entries are described as kept without any link to the person.
- **Benchmark export leaves out interacted repositories** (contributed to or previously
  interacted with) by default, so a committed export does not reveal the developer's
  contribution set. An explicit `--include-interacted` flag keeps them for private use.
- Disconnect and account deletion cancel jobs once, not twice (A-19).

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `data-controls`:
  - Deletion stays final when background work is running.
  - Account deletion removes identifying audit fields.
  - The privacy page lists what is actually stored and kept.
- `github-authentication`:
  - Disconnect ends all of the user's sessions and clears the GitHub-derived display name.
  - A returning sign-in revokes the token it replaces.
- `recommendation-evaluation`: the developer snapshot export leaves out interacted repositories
  unless asked to include them.

## Impact

- **Backend:**
  - `services/jobs.py`: a write guard shared by all job services, built from the check that
    `services/ranking/service.py` already does.
  - The services that write user data: `services/github/sync.py`,
    `services/profiling/analysis.py` (the standalone analysis job), `services/discovery/service.py`
    and `services/ranking/service.py`.
  - `services/data_deletion.py` and `accounts/views.py` (disconnect, account deletion).
  - `services/github/accounts.py` and `services/github/oauth.py` (single-token revoke).
  - `services/audit.py` (scrub on account deletion).
  - `services/evaluation/export.py` and the `export_benchmark_developer` command.
- **Frontend:** `routes/PrivacyPage.tsx` text only.
- **API:** unchanged. The OpenAPI schema is unchanged.
- **Data:** no migration. The audit scrub runs only when an account is deleted.
- **Out of scope:** dismissal races (batch 6), and the export dropping stale or dismissed
  repositories (E-4, batch 6).
