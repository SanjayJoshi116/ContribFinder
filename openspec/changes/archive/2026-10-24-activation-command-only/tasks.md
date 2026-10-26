## 1. Admin (D1, D2, S-6)

- [x] 1.1 `recommendations/admin.py`:
  - remove `actions = ["activate"]`, the `activate` method and the now unused imports;
  - add the read-only `activation` method field for saved rows (active / command text,
    `format_html`); not on the add form.

## 2. Activation service (D3)

- [x] 2.1 `services/ranking/activation.py`: `activate(version, *, force, reason, judge)`; audit
  metadata `via: "command"`; no user or request; docstrings say "the command".
- [x] 2.2 `activate_scoring_config`: call without `via`.

## 3. Tests

- [x] 3.1 `tests/test_activation.py`:
  - replace the two admin action tests: the changelist offers no `activate` action (posting it
    activates nothing and runs no judge), and the change page of `v1-deterministic` shows
    `npm run manage -- activate_scoring_config v1-deterministic`, while the active one says it
    is active;
  - service tests drop `via=`; `events()[0].metadata["via"] == "command"` still holds.
- [x] 3.2 `test_models_phase5.py` admin read-only test still passes (the new field is
  read-only too).

## 4. Verification and housekeeping

- [x] 4.1 Backend `ruff check`, `ruff format --check`, `mypy`, `pytest`; `npm run manage --
  check`. No frontend or e2e change.
- [x] 4.2 Manual: open a configuration in the admin; the activation hint shows and the action
  menu has no "Activate".
- [x] 4.3 Docs:
  - README "To make a configuration active": command only;
  - CLAUDE.md §6 activation line (no admin action) and §7 shipped entry (K-1 carry-over
    unchanged);
  - `ideas.md` §17 moved to "Shipped";
  - `Bug_Backlog.md`: S-6 `fixed (activation-command-only)`, removed from Open items, batch 18
    row, "Next" line, "Fixed by release" row and total.
- [x] 4.4 Release housekeeping (CLAUDE.md §8): next patch version (0.12.17, or 0.12.18 after
  `keyset-paging-links`); `CHANGELOG.md` (removed: admin activation action).
