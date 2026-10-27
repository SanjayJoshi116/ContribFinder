## Context

See proposal.md. Code: `services/data_versions.versions` (`last_completed(user, SYNC)` for
`github`), `src/app/dataVersions.ts` (`AREA_KEYS`, `useDataVersions`, `refreshDataVersions`),
the status refresh callbacks in `features/*/api.ts`, `useDeleteGitHubData` in
`features/auth/api.ts`, and `DiscoveryService._remove_not_code`.

## Goals / Non-Goals

**Goals:** close U-1, U-2, U-3, U-5, U-6, U-7 without changing the endpoint's shape.

**Non-Goals:** fewer versions requests on navigation (U-4, accepted); shifting feedback
snapshots in the rank repair (U-8, wontfix).

## Decisions

**D1. `github` from the last finished sync.** `SyncJob` with status COMPLETED or FAILED, newest
`completed_at`. A cancelled sync (data deletion, disconnect) is left out: deletion resets the
client's versions anyway. `recommendations` keeps COMPLETED generations only: a failed generation
persists nothing (one transaction).

**D2. Hidden list in `recommendations`.** `['profile','dismissed']` joins that area; the user's
own dismiss/restore invalidations stay.

**D3. `refreshDataVersions` uses `cancelRefetch: false`.** A running versions fetch is kept and
the second request joins it, so the comparison runs once per diff. The comparison stays in the
`queryFn` (one fetch, one comparison).
- *Alternative:* compare in a cache subscriber after the data is stored. Rejected: more moving
  parts for the same result.

**D4. Delete-data uses `resetQueries(dataVersionsKey)`.** The query keeps its observer, its data
returns to undefined and it refetches; with no previous value that fetch refetches nothing.

**D5. `_remove_not_code` counts candidates.** `delete()` returns per-model counts; the method
returns `RepositoryCandidate`'s and logs it.

## Risks / Trade-offs

- [`cancelRefetch: false` may return data fetched just before a job finished] → The job's own
  write is committed before its status reads finished, and a fetch started after that sees it;
  a fetch already running may miss it, and the next trigger (focus, route change, next job)
  catches up, as in the data-versions design.

## Migration Plan

No migration. Rollback: revert the release.
