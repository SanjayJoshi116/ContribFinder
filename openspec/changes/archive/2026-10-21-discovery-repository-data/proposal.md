## Why

The candidate pool and the shared repository rows it points to drift from what GitHub and the
settings say. Batch 7 of `Bug_Backlog.md` (verified) found these gaps. They break three promises:
- shared repository data is never lost or overwritten by a side effect;
- eligibility always reflects the current data and settings;
- the pool that is kept is the pool that is analyzed, in one order.

- **Shared data lost or frozen.**
  - A search result or sync whose name another stored repository still holds deletes that row,
    even when it is a live repository that was renamed. The delete cascades to every user's
    candidates, recommendations, saves and dismissals (C-2).
  - A search result counts as a metadata fetch, so a repository found often never has stale
    metadata and its languages are never refreshed (C-8).
  - Without a metadata fetch, the analysis decides eligibility from the row it loaded at claim
    time, ignoring search updates stored meanwhile (C-14).
  - A queued README or issues refresh of a FAILED repository skips the "re-check everything"
    rule, so a deleted repository comes back eligible (C-5).
  - Concurrent discovery runs upsert the same rows in different orders and can deadlock, which
    fails the job (C-7).
- **Eligibility goes stale.**
  - The pool step writes `not_code` directly. It overwrites a FAILED or archived repository's
    real reason, and can race an analysis into "RECOMMENDABLE but ineligible" (R-4).
  - Only `not_code` is re-checked on stored data; a settings change (push window, license)
    waits for the next analysis (R-12).
  - `not_code` rejects real code: any `awesome-*` name (`awesome-lint`) and generic topics
    (`list`, `lists`, `books`) (R-5).
- **The pool, its order and its provenance drift.**
  - Analysis runs before the pool step, so it spends budget on candidates the pool then
    evicts (C-11). A resumed analysis step goes past its per-run cap (C-12).
  - Discovery records from queries that no longer match are never pruned; their old best rank
    keeps driving analysis order and eviction (C-13). The star band is part of the stored query,
    so a repository crossing a band gets a second record and users see the band (R-6).
  - The candidate order is written three times and has drifted (C-17).
  - `pool_bands` puts a repository in the wrong band when bands have gaps (R-9).
- **Background refresh and configuration.**
  - The backlog requeues a STALE repository every 15 minutes while its task is still queued or
    retrying, and an explicit-part task refetches parts that are no longer stale (C-15). The
    selection logic lives in Celery tasks, not services (C-16).
  - `lifecycle_changed_at` is null for some rows and patched in two places (C-18).
  - Setting only `DISCOVERY_MIN_STARS` makes Django refuse to start: the default bands start
    at a hard-coded 20 (R-3). A budget that is not a multiple of the band count silently
    wastes requests (R-10). Topic reads bypass prefetching (N+1) (R-11).

## What Changes

- **A name is freed, never a row deleted.** A repository whose name is taken by another GitHub
  ID gets a released placeholder name and stale metadata. Its next analysis fetches it by
  GitHub ID: it is stored under its current name, or FAILED `not_found` when GitHub deleted it.
- **Search results update metadata fields but not the metadata fetch time.** Only an analysis
  or the profile sync (which also fetch languages) set it.
- **Analysis decides eligibility from the locked current row.** A FAILED repository's retry
  always fetches every data type, whatever the task asked for.
- **Upserts in one order.** Each query's results are stored in GitHub ID order.
- **Eligibility re-check through the lifecycle.** The pool step re-runs every eligibility rule
  on stored data for its analyzed, settled candidates, through a lifecycle helper that skips
  repositories in analysis or FAILED and keeps the RECOMMENDABLE / INDEXED state (and a STALE
  row's previous state) in step with eligibility.
- **Narrower `not_code`.**
  - No detected primary language is still rejected at search.
  - An `awesome-*` name or a list topic only makes a repository a *suspected list*. After
    analysis it is `not_code` unless it has manifest dependencies.
  - A search result already analyzed as `not_code` is rejected without a new analysis.
- **Pool before analysis.**
  - The discovery steps become queries → search → interactions → pool → analysis.
  - The analysis list is planned once per job and stored, so a resumed step keeps its cap and
    its total.
- **Provenance.**
  - The stored query no longer includes the star band.
  - At the pool step, discovery records that this run did not see again are deleted.
- **One candidate order:** previously interacted, best search rank, most recently found, name.
  The pool cap, the analysis and the candidate list (after its eligibility groups) use it.
- **Correct band counts:** a repository counts in the band whose range holds its stars, or in
  `other` when no band holds them.
- **Backlog.**
  - Selection moves to `services/repositories/backlog.py`.
  - A queued refresh is not queued again until it could have run (stale-job time plus the
    maximum retry delay).
  - A task with explicit parts fetches only those still stale.
- **Configuration.**
  - The default bands derive from `DISCOVERY_MIN_STARS`.
  - A new warning flags a query budget that is not a multiple of the band count.
- **Data.**
  - `lifecycle_changed_at` becomes non-null with a default (null rows are backfilled).
  - New column `Repository.refresh_queued_at`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repository-discovery`:
  - Derived default bands and a budget warning.
  - Search upserts never delete rows, never count as a metadata fetch, and run in one order.
  - Provenance without bands, pruned each run.
  - Narrower `not_code` with code evidence.
  - Eligibility re-checked on stored data with every rule.
  - Pool step before analysis, with a fixed analysis plan.
  - One candidate order and correct band counts.
- `repository-analysis`:
  - A freed name, resolved by GitHub ID.
  - Eligibility from the current row.
  - A FAILED retry checks every part.
  - A queued refresh is not requeued.
  - Explicit parts are intersected with the stale parts.

## Impact

- **Backend:**
  - `services/github/storage.py` (`upsert_repository`: free the name, optional metadata
    time) and `services/github/client.py` (`get_repository_by_id`).
  - `services/discovery/service.py`: step order, analysis plan, sorted upserts, pruning,
    eligibility re-check, ordering helper. `services/discovery/filters.py` (`not_code`,
    `_topics`) and `services/discovery/queries.py` (provenance core, `band_of`).
  - `services/repositories/lifecycle.py`: `release_name`, `recheck_eligibility`, `hold`
    refreshes the row, `complete`/`fail` clear `refresh_queued_at`.
  - `services/repositories/analysis.py`: FAILED retry parts, explicit parts ∩ stale, metadata
    by ID.
  - New `services/repositories/backlog.py`, called by `repositories/tasks.py`.
  - `repositories/api.py` uses the shared order.
  - `config/settings/base.py`: bands default, excluded topics. `core/checks.py`: a new
    warning. `services/jobs.py`: `DISCOVERY_STEPS` order.
- **Data:** a `repositories` migration backfills `lifecycle_changed_at` and makes it non-null
  with a default, and adds `refresh_queued_at`. Old band-qualified discovery records are
  pruned by the first run after the release.
- **API:** unchanged in shape. Discovery job steps are listed in the new order, and candidate
  provenance shows queries without `stars:` qualifiers. The OpenAPI schema is unchanged.
- **Ranking:** no change to scores or ordering. The pool can now contain projects that the old
  `not_code` rule rejected. The benchmark is unaffected: its repositories are fixed and it does
  not use discovery.
- **Out of scope:**
  - `_has_app_credentials` duplication (C-23), discovery metadata write volume (C-20) and the
    serializer's `ineligible_reason` (C-21): batch 11.
  - Docs-style repositories with a language and no list marker (K-4).
