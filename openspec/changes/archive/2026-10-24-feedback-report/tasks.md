## 1. Aggregation (D1, D2)

- [x] 1.1 `services/evaluation/feedback_report.py`: `Event`, `BUCKETS`, `POSITIVE`, `DECISIVE`,
  `load(since, versions)` (one query), `build(events, *, minimum)` returning per-configuration
  bucket rows (counts per action, distinct users, share), raw and adjusted shares, and the
  unattributed counts; `as_dict()` for JSON.
- [x] 1.2 Tests (`tests/test_feedback_report.py`), `build` on plain events:
  - 12 saved and 8 dismissed at ranks 1–5 → share 0.60, users counted once each;
  - the position-adjustment scenario (raw 0.72 / 0.48, adjusted 0.60 / 0.60);
  - a group below the minimum shows counts, no share, and is left out of the adjustment;
  - a configuration with no bucket at the minimum has no adjusted share;
  - viewed, unsaved and undismissed counted but outside every share;
  - blank version or null rank → unattributed, outside every share;
  - rank 21 and 300 land in `21+`.

## 2. Command (D3)

- [x] 2.1 `recommendations/management/commands/feedback_report.py`: `--since`, `--config`,
  `--minimum`, `--json`; table output and the denominator note; validation errors as
  `CommandError`.
- [x] 2.2 Tests (database): events from the factories/builders under two versions → printed
  shares; `--since` drops old events; `--config` filters; `--minimum 0` fails; JSON has the
  documented keys and no user id, repository name, recommendation or issue id anywhere
  (walk the JSON); no stored row changes.

## 3. Verification and housekeeping

- [x] 3.1 Backend `ruff check`, `ruff format --check`, `mypy`, `pytest`. No frontend or e2e
  change.
- [x] 3.2 Run `npm run manage -- feedback_report` against the local database; note in the PR
  or CHANGELOG only that it runs (local events are test clicks, not findings).
- [x] 3.3 Docs: README "Feedback report" (what the shares mean, the adjustment, the minimum);
  CLAUDE.md §4 tree (`services/evaluation/feedback_report`), §6 command line and §7 shipped
  entry (K-1 carry-over unchanged); `ideas.md` §4 online report shipped (label calibration,
  dismiss reasons open).
- [x] 3.4 Release housekeeping (CLAUDE.md §8): patch 0.12.20; `CHANGELOG.md`, `features.txt`,
  README status line.
