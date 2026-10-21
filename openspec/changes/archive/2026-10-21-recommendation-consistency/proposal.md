## Why

What users see as their recommendations depends on timing, not just on their data. Batch 6 of
`Bug_Backlog.md` (verified) found these gaps. They break two promises:
- a recommendation keeps its identity across regenerations;
- a dismissed repository stays hidden, and every reason is backed by stored data.

- **Stale ≠ gone.**
  - The hourly stale sweep moves repositories from RECOMMENDABLE to STALE. Generation scores
    only RECOMMENDABLE, so the next regeneration deletes those recommendations. They come back
    later with new ids, or never when app credentials are missing (D-1).
  - The benchmark export reuses the same loader. The judged pool therefore depends on when the
    sweep last ran, and it leaves out the user's dismissed repositories, which are their clearest
    "not relevant" examples (E-4).
  - A developer whose pool became empty keeps their old recommendations forever, because the
    freshness sweep only looks at developers that have candidates (D-14).
- **Save, dismiss and generation race each other.**
  - Generation reads dismissals before it locks the recommendation rows. A dismiss that commits
    in between is missed, and the repository is recreated (D-2).
  - Dismiss and generation lock rows in opposite orders and can deadlock (D-3). So can generation
    and an issue refresh (D-4).
  - A save from a stale tab can race a dismiss (E-5).
  - Dismiss deletes the save without recording an `unsaved` event (E-6).
  - Two concurrent views both store a `viewed` event (E-7).
  - In the interface, a fast double click on Save sends save and unsave with no ordering, and
    the button can end up showing the opposite of the server state (F-4).
- **Results that don't match their inputs.**
  - Restoring a dismissed repository reuses a generation that already loaded its candidates, so
    the restored repository stays missing until something unrelated changes (D-5).
  - Dismissals made during a run are removed after the top-N cut, so fewer than N are stored even
    when more candidates exist (D-10).
  - An issue deleted while a run works is dropped from the stored issues. The score, the label
    and the reason text ("3 open issues…") still count it (D-6).

This is theme 5 ("stale ≠ gone") and theme 7 ("save/dismiss consistency") of the backlog. It
lands after batch 5. Batch 4's job fencing (`job_write`) is what makes one lock order possible.

## What Changes

- **Stale repositories stay recommendable.**
  - Generation scores eligible repositories that are RECOMMENDABLE, STALE or REFRESHING. Stale
    data is still data, so a sweep no longer removes recommendations or changes their ids.
  - Moving into STALE or REFRESHING no longer counts as a pool change for freshness; a completed
    refresh or a failure still does.
- **One lock order for a developer's recommendations.**
  - Generation's write, save, unsave, dismiss, restore and `viewed` recording each lock the
    developer profile row first, so they run one at a time per developer.
  - Within generation, the order is: job, profile, dismissals read, recommendations, then issues
    sorted by id. An issue refresh locks the issues it deletes, sorted by id, before deleting
    them.
- **Save and dismiss state stays consistent.**
  - A save that finds the recommendation already gone or the repository dismissed is a 404, as
    for any missing recommendation.
  - Dismiss records an `unsaved` event when it removes a save.
  - The `viewed` de-duplication runs under the same lock.
  - The Save button is disabled while a save or unsave is pending.
- **Results match their inputs.**
  - Dismissals are applied before the top-N cut.
  - If a matched issue disappeared before the write, generation ranks again from stored data,
    up to 3 attempts, then fails without replacing anything. Stored scores, labels and reasons
    are always computed from the issues that are stored.
  - Starting a generation while one is RUNNING marks that job to run again once it completes.
    A restore, or a discovery that finishes mid-run, is therefore always reflected.
  - The freshness sweep also regenerates developers who have recommendations but no candidates
    left.
- **Benchmark export** takes the pool generation would see (stale included) plus dismissed
  repositories.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `recommendation-engine`:
  - Stale and refreshing eligible repositories are scored.
  - Dismissals apply before the top-N cut.
  - Stored results are consistent with stored issues.
  - A generation started during a running one runs again.
  - Freshness ignores staleness marks and covers emptied pools.
- `recommendation-feedback`:
  - A save never outlives a dismissal.
  - Dismissing a saved repository records `unsaved`.
  - Concurrent views are recorded once.
  - The Save button can't send overlapping requests.
- `recommendation-evaluation`: the developer export includes stale and dismissed candidates.

## Impact

- **Backend:**
  - `services/matching/features.py`: `load_candidates` lifecycle filter, plus an
    `include_dismissed` option.
  - `services/ranking/service.py`: lock order, dismissal filter before the cut, rank again when
    issues changed.
  - `services/ranking/pipeline.py` and `score.rank`: `top_n` may be `None`.
  - `services/ranking/freshness.py`: profiles with recommendations, staleness marks ignored.
  - `services/feedback.py`: profile lock, save re-check, `unsaved` on dismiss, locked view
    de-duplication.
  - `services/jobs.py`: a rerun request on a RUNNING generation; generation's `on_completed`
    hook.
  - `services/repositories/analysis.py` (`_store_issues`): lock before delete.
  - `services/data_deletion.py`: lock the profile first.
  - `services/evaluation/export.py`.
- **Data:** a migration adds `SyncJob.rerun_requested` (boolean, default false).
- **Frontend:** `features/feedback/RecommendationActions.tsx` (SaveButton disabled while
  pending).
- **API:** unchanged. A save race now answers 404 where it could leave a hidden save behind. The
  OpenAPI schema is unchanged.
- **Ranking:** no change to scores or ordering. The benchmark baselines stay as they are:
  evaluation does not use `load_candidates` filters, and `rank_pool` keeps its cut there.
- **Out of scope:**
  - Eligibility re-checks on stored data (batch 7).
  - Issue-level ranking changes (batch 8).
  - Frontend query invalidation (batch 9).
