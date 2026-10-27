## Why

A discovery run maintains its pool before it analyzes anything (design D7 of
`discovery-repository-data`): the pool step removes known lists (`not_code`) and applies the cap,
then the analysis step analyzes the kept candidates. A suspected list (`awesome-*`, a list topic)
is only decided by its analysis, so a list this run's own analysis finds `not_code` stays in the
pool until the next run, up to a day or more later. Meanwhile the profile page counts it as an
ineligible candidate, the candidate list shows it, and the recorded pool size and band counts
include it. `Bug_Backlog.md` X-9 accepted this as by design in 0.12.7; `ideas.md` §11
("Post-analysis pool cleanup", next in the "can ship now" list) asks for the cheap second pass.
No ranking change: such a repository is already ineligible, so no recommendation changes.

## What Changes

- After its analysis step has analyzed the planned repositories, a discovery run removes from the
  developer's pool every candidate it analyzed whose stored data now shows `not_code`, using the
  same rule as the pool step. It records how many it removed (`analysis_not_code`) and records
  the pool size and band counts again, so the job reflects the pool it leaves.
- The removal happens in the analysis step (no new job step, no new GitHub request) and is
  fenced like the pool step: a cancelled or reclaimed run removes nothing.
- Nothing else changes: the pool cap, eligibility re-check, analysis plan and generation are as
  before. The shared repository row is never deleted.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repository-discovery`, "Candidate pool maintenance": a candidate this run's analysis found to
  be not a code project leaves the pool at the end of the run, and the job records the removals
  and the resulting pool size and band counts.

## Impact

- Backend: `services/discovery/service.py` (`_step_analysis` ends with the cleanup; the pool
  summary that the pool step records becomes one helper used by both); tests in
  `tests/test_discovery_repository_data.py` / `tests/test_discovery_service.py`.
- No migration, API, frontend or setting change.
- `Bug_Backlog.md` X-9: fixed (post-analysis-pool-cleanup).
- Release: patch 0.12.26. Docs: CLAUDE.md §7, `ideas.md` §11 (item to "Shipped"), CHANGELOG,
  features, README status line.
