## Why

S-6 of `Bug_Backlog.md` (batch 18, from the review of 0.12.13/0.12.14). The Django admin's
"Activate the selected configuration" action runs the benchmark comparison (`rank_pool` for
every benchmark developer, under both configurations) inside the HTTP request. That breaks the
rule that long-running work runs outside requests (CLAUDE.md §3.3), and an unexpected error in
the comparison shows the operator a 500 page.

It is fast today (`benchmark-v1`: 6 personas), but it grows with every judged real developer
in `benchmark-v2` after K-1. Of the two options in the backlog, a tracked job or the admin
pointing to the command, this change takes the second: activation is a rare operator step, and
the command already handles forcing, the reason and the audit trail. A new job type for it is
not worth the code.

## What Changes

- **BREAKING (operators only):** the admin activation action is removed. A scoring
  configuration is activated only with `npm run manage -- activate_scoring_config <version>`
  (`--force --reason "..."` for a deliberate exception). The rule it applies is unchanged.
- The admin change page of a configuration shows how to activate it: the command line with
  its version, or that it is already active. `is_active` stays read-only in the admin.
- Audit entries keep `via` (`command` for every new activation); entries recorded by the admin
  action keep `admin`.
- No API, UI or ranking change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `recommendation-evaluation`, "Activating a configuration": activation happens only through
  the management command; the admin shows the command instead of running the comparison. The
  scenario "Admin action refused" is replaced by one for the admin page.

## Impact

- Backend:
  - `recommendations/admin.py`: no `activate` action; a read-only field with the activation
    command;
  - `services/ranking/activation.py`: `activate` loses the `via`, `user` and `request`
    parameters that only the admin passed;
  - the activation command (call site only);
  - `tests/test_activation.py` (admin tests replaced).
- Docs: README "To make a configuration active", `ideas.md` §17 (shipped), CLAUDE.md §6
  (activation line) and §7, `Bug_Backlog.md` (S-6), CHANGELOG, features.
- Release: patch 0.12.17 (or 0.12.18 if `keyset-paging-links` ships first).
