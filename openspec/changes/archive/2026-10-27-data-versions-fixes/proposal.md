## Why

A code review of the uncommitted 0.12.24–0.12.30 work (`Bug_Backlog.md` batch 20, U-1…U-8) found
gaps in `data-versions` (0.12.27) and a miscount in discovery's pool cleanup:
- U-1: the `github` version follows completed syncs only, so a sync that fails after storing
  data no longer refreshes anything (before 0.12.27 every finished job refreshed `['profile']`).
- U-2: the hidden list belongs to no data area, so background refreshes never reach it.
- U-3: `_remove_not_code` reports the flagged count, not the candidates it deleted (and its log
  counts cascaded discovery records), so `pool_not_code` / `analysis_not_code` can over-count.
- U-5: a finished discovery refetches the data versions although it changes no data area.
- U-6: overlapping versions fetches (two jobs finishing together) refetch the changed areas twice.
- U-7: delete-data removes the versions query while the signed-in layout still observes it.
No ranking change.

## What Changes

- `github` = end of the last finished sync, completed or failed (U-1).
- `recommendations` area also refreshes the hidden list (U-2).
- `_remove_not_code` returns the number of `RepositoryCandidate` rows deleted (U-3).
- Discovery's job transition refetches only the generation status (U-5).
- `refreshDataVersions` does not cancel a running versions fetch, so one diff invalidates once
  (U-6); delete-data resets the versions query instead of removing it (U-7).
- U-4 (versions on every route change) accepted by design; U-8 (feedback snapshots not shifted
  by the rank repair) wontfix: no rank 0 was ever written.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `sync-jobs`: "Data versions endpoint" — `github` from the last finished sync.
- `web-client`: "Refresh derived data on job transitions" (discovery refetches only the
  generation status), "Refresh derived data by data versions" (hidden list in `recommendations`;
  overlapping fetches refetch once).

## Impact

- Backend: `services/data_versions.py`, `services/discovery/service.py`; tests.
- Frontend: `src/app/dataVersions.ts`, `features/discovery/api.ts`, `features/auth/api.ts`; tests.
- `Bug_Backlog.md` batch 20; CLAUDE.md §7 shipped entry; CHANGELOG, `features.txt`, README.
  Release: patch 0.12.31.
