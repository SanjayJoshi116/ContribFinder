## Context

See proposal.md for why.
- `services/ranking/activation.activate(version, *, force, reason, via, user, request, judge)`
  is the one activation path (change `config-activation-loose-ends`, design D1). It audits
  `scoring_config_activated` with metadata `via`, plus `user` and `request` for the audit row.
- Callers:
  - `activate_scoring_config` (command): `via="command"`, no user or request;
  - `ScoringConfigAdmin.activate` (admin action): `via="admin"`, the admin user and request,
    never forced; on refusal it shows the failures and the forced command line.
- `ScoringConfigAdmin` shows `is_active` and `created_at` read-only, and since 0.12.16 also
  version, weights and params for every saved row.
- Allowed audit metadata keys (`services/audit.py`) include `via`; stored entries from the
  admin action carry `via: "admin"`.

## Goals / Non-Goals

**Goals:**
- No benchmark comparison can run inside a web request.
- An operator on the admin page sees exactly what to run.

**Non-Goals:**
- A tracked activation job or any activation UI (option A of S-6).
- Changing the activation rule, forcing, the audit content or the command's output.

## Decisions

**D1. Remove the admin action.**
- `ScoringConfigAdmin` loses `actions = ["activate"]` and the `activate` method; with no
  custom action left, Django's default "delete selected" stays available as before (protected
  configurations still refuse deletion).
- *Alternative:* keep the action but only print the command. Rejected: an action that does
  nothing when run is confusing, and the change page already has room for the hint.

**D2. A read-only "Activation" field on the change page.**
- A method field (`activation`) in `readonly_fields` for saved rows:
  - active row: "Active. Activate another configuration with `npm run manage --
    activate_scoring_config <version>`.";
  - other rows: "Run `npm run manage -- activate_scoring_config <its version>`; add
    `--force --reason \"...\"` for a deliberate exception (the command compares it with the
    active configuration on the selection benchmark first)."
- Escaped through `format_html`. The change list keeps `version, is_active, created_at`; the
  hint is on the change page only.
- The add form (no saved row) does not show it.

**D3. `activate` drops `via`, `user`, `request`.**
- Only the admin passed `user` and `request`; with one caller left they are dead parameters.
- The audit metadata keeps the key: `via` is always `"command"` for new entries, so reports
  that group by it keep working and old `admin` entries stay readable. `audit.record` gets no
  user or request (as the command already did).
- The module docstring and `config-activation-loose-ends` references to "the command and the
  admin" become "the command".

## Risks / Trade-offs

- [An operator used to the admin button] → The change page shows the command; README and the
  CHANGELOG say so.
- [Operators without shell access to the deployment] → None today: the command is the
  documented path for every other operator task (`reanalyze_profiles`, `evaluate_ranking`).
  Option A remains possible later as its own change.

## Migration Plan

- No data migration; `accounts.AuditEvent` choices and metadata keys are unchanged.
- Rollback: revert the release.
