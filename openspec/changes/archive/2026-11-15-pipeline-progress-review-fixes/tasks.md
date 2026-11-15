## 1. Backend completion order

- [x] 1.1 PIPE-1, PIPE-2: `run_tracked_job` finishes the job and runs its hook in one transaction; `_follow_up` runs the hook in a savepoint; same for `on_failed` (D1). Tests: a hook that checks, from a separate connection, that the user's finished job is not yet visible (no gap where the completion shows without its follow-up); after commit both are visible; a hook that raises leaves the job COMPLETED and logs; the generation rerun job is committed with the finished generation; the follow-up task is sent only after commit.

## 2. Frontend

- [x] 2.1 PIPE-3: `usePipelineStage(fetchStages)`; `AppShell` passes `!developer.data` (D2). Test: profile pending, discovery RUNNING → "Finding projects…" and the discovery status polls.
- [x] 2.2 PIPE-5: stalled discovery → stalled notice on the card (D3). Test.
- [x] 2.3 PIPE-7, PIPE-8: stalled running step shows "Stopped" without spin; unknown state → pending (D3). Tests.
- [x] 2.4 PIPE-6, PIPE-9: `formatRelative` in `lib/format` (browser locale, future clamped); `DiscoveryCard` re-renders each minute (D4). Tests (fake timers): "this minute" → "1 hour ago"; a time 90 s ahead → "now".
- [x] 2.5 PIPE-4, PIPE-10: shared `GITHUB_FAILURES`; onboarding sign-in for a start error that needs it (D5). Tests: 409 `github_not_connected` on Start sync → message and "Sign in with GitHub again"; a discovery `github_not_connected` failure gets the shared reason; existing message tests keep their wording.

## 3. Checks

- [x] 3.1 Backend: `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`, `uv run mypy .`.
- [x] 3.2 Frontend: `npm test`, `npm run lint`, `npm run typecheck`, `npm run format:check`, `npm run build`; `npm run e2e` (onboarding and dashboard progress).

## 4. Release

- [x] 4.1 `Bug_Backlog.md` batch 68: PIPE rows marked fixed.
- [x] 4.2 `/simplify`, then `/code-review` on the fix diff: skipped by the owner.
- [x] 4.3 Archive (ADDED requirements in `sync-jobs`, `web-client`). Release housekeeping per CLAUDE.md §8. Commit only when the owner says so.
