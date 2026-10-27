## 1. Backend

- [x] 1.1 `services/data_versions.py`: `github` from the last COMPLETED or FAILED sync; tests
  (scenario "Sync failed after storing data", cancelled sync ignored).
- [x] 1.2 `DiscoveryService._remove_not_code` returns and logs the `RepositoryCandidate` delete
  count; test with a flagged repository that is no longer a candidate and with discovery
  records cascading.

## 2. Frontend

- [x] 2.1 `AREA_KEYS.recommendations` adds `['profile','dismissed']`; update the `AREA_KEYS` test.
- [x] 2.2 `useDiscoveryStatus` refresh: generation status only; test scenario "Discovery
  finishes" (no versions request).
- [x] 2.3 `refreshDataVersions`: `cancelRefetch: false`; test scenario "Two jobs finish together"
  (each changed area fetched once).
- [x] 2.4 `useDeleteGitHubData`: `resetQueries(dataVersionsKey)`; update the feedback test.

## 3. Verification and housekeeping

- [x] 3.1 Backend `ruff`, `mypy`, `pytest`; baselines unchanged. Frontend `lint`, `format:check`,
  `typecheck`, `test`, `build`; `npm run e2e`.
- [x] 3.2 `Bug_Backlog.md` batch 20 (U-1…U-8 with outcomes); CLAUDE.md §7 shipped entry;
  `features.txt`; CHANGELOG; README status line; patch 0.12.31, lockfiles, `check:version`.
