## Why

Three findings in `Bug_Backlog.md` sit outside any batch. They were re-checked against the code
on 2026-10-22, and none of them changes ranking, so none waits for K-1:
- **Y-6.** Profile data changed by a job no status query watches stays cached for up to
  5 minutes. A standalone `profile_analysis` from `reanalyze_profiles` is one such job.
- **Y-7.** The saved and hidden lists page by number. A save, unsave, dismiss or restore made
  between two "Show more" clicks, for example in another tab, shifts the pages. The list then
  shows an entry twice (a duplicate React key) or skips one.
- **Z-1.** Re-applying the `v2-deterministic` seed after a rollback activates v2 over an
  operator who deliberately chose `v1-deterministic`.

Batch 8 still waits for K-1.

## What Changes

- **Profile data follows the pipeline (Y-6).**
  - A profile analysis always ends in a generation: analysis → discovery → generation.
  - When the SPA sees a generation finish, it now also refetches the developer profile,
    skills and interests.
  - Profile changes from `reanalyze_profiles`, or any analysis no sync started, then show up
    when that pipeline ends, not up to 5 minutes later.
  - Only the job-status refresh changes; there is no new endpoint and no shorter cache time.
- **Stable saved and hidden lists (Y-7).**
  - `GET /api/v1/saved` and `GET /api/v1/dismissed` accept an opaque `cursor` and page by
    (save or dismiss time, id).
  - Their `next` link carries the cursor, so a page stays stable however the list changes
    between requests.
  - `count` and the `page` parameter keep working, so the response shape is unchanged and no
    contract version bump is needed.
  - An invalid cursor answers 400 `invalid_cursor`.
  - The SPA follows the cursor instead of counting pages.
- **The v2 seed respects a stored v2 (Z-1).**
  - Seeding activates `v2-deterministic` only when the seed creates it, and only while no
    configuration or only `v1-deterministic` is active.
  - When the `v2-deterministic` row already exists, re-applying the seed leaves every
    activation unchanged. A row can survive a rollback because an operator deactivated it, or
    because it produced recommendations.
  - An operator re-activates v2 explicitly (admin "Activate").
  - This is a spec change: re-applying the seeds after a rollback no longer always ends with v2
    active.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-client`: a finished generation also refreshes the developer profile, skills and
  interests. "Refresh derived data on job transitions" gains that rule and a scenario for a
  standalone profile analysis.
- `recommendation-feedback`: the saved and hidden lists page by cursor and stay stable when
  entries are added or removed between pages ("Complete saved and hidden lists").
- `recommendation-engine`: the v2 seed activates v2 only when it creates it ("Versioned
  scoring configuration", including the scenario "Seeds reversed and re-applied").

## Impact

- Backend:
  - `feedback/api.py` gets a keyset pagination class shared by both lists, with cursor encoding
    and the `invalid_cursor` error.
  - `recommendations/migrations/0003_seed_v2_deterministic.py` changes its `seed` rule. It is
    an edited data migration: it only changes what a re-apply does, and databases that have
    already applied it are untouched.
  - Tests: `tests/test_feedback.py` (or a new paging test) and `tests/test_seed_migrations.py`.
- Frontend:
  - `features/feedback/api.ts`: `usePagedList` passes the cursor as `pageParam`.
  - `features/recommendations/api.ts`: the generation refresh also covers the profile keys.
  - Tests in `feedback.test.tsx` and `app.test.tsx`.
- API:
  - OpenAPI adds the `cursor` query parameter on `saved_list` and `dismissed_list`
    (`npm run api:sync`). Not breaking, so `/api/v1` stays at OpenAPI `1.0.0`.
- Docs: `Bug_Backlog.md` (Y-6, Y-7, Z-1), `ideas.md` §14 (keyset lists shipped; data versions
  stay an idea), CLAUDE.md, CHANGELOG, features, README. Patch release 0.12.12.
