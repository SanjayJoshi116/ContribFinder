## Why

Review sweep of `apps/frontend/src/features/sync/` and `features/discovery/` (onboarding
progress, pipeline stage, discovery card). `/code-review` reported 10 findings, each checked
against the code and `services/jobs.py` (PIPE-1…PIPE-10 in `Bug_Backlog.md`, batch 68).
`/security-review` found nothing: start and status act on the signed-in user only, CSRF is
enforced, job responses leave out metadata and error detail, error codes map to fixed text, and
the sign-in URL and post-login redirects are fixed.

The main problem is in the backend's completion order. `run_tracked_job` commits a job COMPLETED
and only then runs its `on_completed` hook, which creates the next job (discovery after a sync,
a generation after discovery). The SPA re-checks the next status as soon as it sees the
completion, so it can read the previous, finished job and stop polling. The new stage then runs
unobserved, and the recommendations stay stale until focus or a route change (PIPE-1, PIPE-2).

## What Changes

- **PIPE-1, PIPE-2** Backend: `run_tracked_job` finishes the job and runs its follow-up hook in
  one transaction, with the hook in a savepoint so its failure keeps the completion. Queuing stays
  on commit, so the next job is visible with the completion. This covers sync → discovery,
  analysis → discovery, discovery → generation, and the generation rerun.
- **PIPE-3** `usePipelineStage(fetchStages)`: `AppShell` passes `!developer.data`, so the stage
  observers fetch and poll themselves when the discovery card and recommendation list are not
  mounted. Partial: the gap is short in practice (profile loading, or not analyzed while a stage
  runs).
- **PIPE-4** Onboarding offers "Sign in with GitHub again" for a start error whose code needs
  sign-in (`github_not_connected`, `github_auth_invalid`).
- **PIPE-5** `describeDiscovery` returns the stalled notice for a stalled job.
- **PIPE-6** `timeAgo` moves to `src/lib/format` as `formatRelative` (browser locale) and clamps
  future times to "now". The discovery card re-renders every minute while it shows a relative
  time.
- **PIPE-7** `SyncSteps` reads `job.stalled`: a running step then shows a static icon and
  "Stopped".
- **PIPE-8** Unknown step states fall back to pending (icon and label). Partial: the generated
  types rule it out, but a cached older SPA can see a newer backend.
- **PIPE-9** With PIPE-6: relative time lives in `src/lib/format`.
- **PIPE-10** One GitHub failure table in `features/sync/messages.ts` (a reason per code).
  Discovery adds its own follow-up sentence.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `sync-jobs`: ADDED "Follow-up job visible with the completion" (PIPE-1, PIPE-2).
- `web-client`: ADDED "Pipeline progress display" (PIPE-3…PIPE-10).

## Impact

- Backend: `services/jobs.py` (`run_tracked_job`, `_follow_up`); jobs tests.
- Frontend: `features/sync/{pipeline.ts,SyncSteps.tsx,messages.ts}`,
  `features/discovery/{messages.ts,DiscoveryCard.tsx}`, `routes/OnboardingPage.tsx`,
  `routes/AppShell.tsx`, `lib/format.ts`; their tests.
- No API, OpenAPI or migration change. `npm run e2e` runs, because the onboarding and dashboard
  progress flows change. Patch release after `profile-ui-review-fixes`.
