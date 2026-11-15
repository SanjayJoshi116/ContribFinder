## Context

Findings and verdicts are in `Bug_Backlog.md` (batch 68, PIPE-1…PIPE-10). Relevant facts:

- `run_tracked_job` calls `finish_job(job, COMPLETED, ...)`, which commits, then
  `_follow_up(on_completed, job)`, which catches and logs exceptions. The hooks
  (`start_discovery_after`, `start_recommendations_after`, `rerun_recommendations_if_requested`)
  create the next job through `_start_job`, which queues with `transaction.on_commit`.
- `fetchStatusAndRefresh` refreshes once per newly seen finished job. The sync refresh
  invalidates `['jobs']`, and the discovery refresh invalidates the recommendation status. Each
  status polls only while its own job is active.
- `usePipelineStage` reads the discovery and recommendation statuses with `enabled: false`.
  Their active observers (`DiscoveryCard`, `RecommendationList`) are mounted only once
  `developer.data` exists.
- `failureMessage` maps codes to `{ text, needsSignIn }`. Onboarding shows sign-in only for a
  failed job, and `startErrorText` shows the start error's message.
- `SyncSteps` never sees `stalled`. `ICONS[state]` has no fallback.

## Goals / Non-Goals

**Goals:** the behavior in the spec deltas; one completion order on the backend that fixes every
stage boundary.

**Non-Goals:** server push (SSE/websocket); polling idle statuses on a timer.

## Decisions

### D1. Completion and follow-up in one transaction (PIPE-1, PIPE-2)

```python
with transaction.atomic():
    if finish_job(job, Status.COMPLETED, ...):
        _follow_up(on_completed, job)
```

`_follow_up` runs `hook(job)` inside `transaction.atomic()` (a savepoint) within its `try`, so a
failing hook rolls back only its own writes. `finish_job` keeps its lock and fencing. Its own
`atomic` becomes a savepoint. The FAILED path (`on_failed`) gets the same wrapping, for the
generation rerun. Lock order: the finished job's row lock is held while the hook creates or
locks the user's next job, which matches the existing order (job first, `services/locks.py`). No
I/O runs under the lock: the hooks only read and write rows, and queuing waits for the commit.
Rejected alternative: a frontend grace poll (keep polling the next status for N seconds after the
previous stage finishes). It guesses a delay and leaves the gap on slow workers.

### D2. Stage observers (PIPE-3)

`usePipelineStage(fetchStages: boolean)` passes it as `enabled` to the discovery and
recommendation status hooks. `AppShell` calls `usePipelineStage(!developer.isPending &&
!developer.data)` (as built: not while the profile loads, because the cards mount right after and
refetch on mount, a second status request that broke the transition tests). When the cards
mount, the stage observers turn off, so no second active observer refetches on mount.

### D3. Stalled and unknown states (PIPE-5, PIPE-7, PIPE-8)

- `describeDiscovery` checks `isStalled(job)` before `isActive` and returns the stalled notice
  (`STALLED_NOTICE`, "or press Refresh").
- `SyncSteps` reads `job.stalled`. A `running` step in a stalled job uses `CircleSlash` with no
  spin, labelled "Stopped".
- A state not in `ICONS` is treated as `pending`.

### D4. Relative time (PIPE-6, PIPE-9)

`formatRelative(iso, now)` goes in `src/lib/format.ts` with `Intl.RelativeTimeFormat(undefined,
{ numeric: 'auto' })`, and clamps positive differences to 0. `DiscoveryCard` holds `now` in state,
updated by a 60 s interval while `last_completed_at` is shown.

### D5. One failure table (PIPE-4, PIPE-10)

`sync/messages.ts` exports `GITHUB_FAILURES: Record<code, { reason, needsSignIn }>`. Sync and
discovery messages append their own next step ("to continue" / "to find projects"; "try again in
a few minutes" / "we will look again on your next refresh"). Onboarding takes `needsSignIn` from
the failed job, or else from `start.error.code` through the same table.
