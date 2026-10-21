## Context

Discovery (`services/discovery/service.py`) stores search results as shared `Repository` rows
through `services/github/storage.upsert_repository`. The profile sync and repository analysis
store through it too. Analysis (`services/repositories/analysis.py`) claims a row, fetches,
then stores inside `lifecycle.hold` → `_store` → `lifecycle.complete`. The background tasks in
`repositories/tasks.py` mark rows STALE and queue refreshes.

Batches 4–6 already provide what this change builds on:
- claim tokens, so only the current claim can write lifecycle (`_held`);
- `lifecycle.SCORABLE`, so eligibility is what generation reads;
- `record_refresh_failure`, which already keeps state as it is.

What is still missing:
- One owner of eligibility. The pool step writes it directly today.
- A notion of "this name now belongs to another repository" that doesn't need a delete.
- A stable plan and order for the pool and its analysis.

See proposal.md for the findings.

## Goals / Non-Goals

**Goals:**
- No code path deletes a `Repository` row because of a name conflict.
- Eligibility and the RECOMMENDABLE/INDEXED state change only through `services/repositories/lifecycle.py`.
- One candidate order, in one helper. The cap, the analysis plan and the API all use it.
- Background refreshes are queued once and fetch only what is stale.
- No change to scores, ranking or benchmark baselines.

**Non-Goals:**
- Detecting docs-style repositories that have a language and no list marker (K-4).
- Batch 11 cleanups (C-20, C-21, C-23), even in code this change moves.
- A history of discovery records: pruned records are gone.

## Decisions

### D1. Free the name, resolve by GitHub ID (C-2)

**Releasing the name.** `upsert_repository` no longer deletes. Before its `update_or_create`,
it calls `lifecycle.release_name(full_name, github_id)`. That helper renames any other row
holding the name to `"{full_name}~{github_id}"`. GitHub repository names allow only letters,
digits, `.`, `-` and `_`, so a released name can never collide with a real one, and
`staleness.is_released_name(name)` (contains `~`) recognizes it. The row keeps everything
else: data, eligibility, links. Nothing cascades.

**Resolving a released name.**
- `stale_parts()` reports `metadata` stale for a released name. The hourly sweep and
  discovery's `_needs_analysis` therefore pick the row up with no extra state.
- `RepositoryAnalysisService.run` always puts `metadata` first in `wanted` for a released name.
  Every later part then uses the resolved name, never the placeholder.
- In `_fetch`, the metadata lookup goes by name first. When the name is released, GitHub
  answers 404, or the answer has another `github_id`, it falls back to the new
  `GitHubClient.get_repository_by_id(github_id)` (`GET /repositories/{id}`). A 404 there is the
  usual `not_found` FAILED. The `pragma: no cover` identity check in `_store` becomes reachable
  only by a bug and stays a `RuntimeError`.

**Data fetched under a name that changed meanwhile.** `hold` re-reads the row (D4). If its
`full_name` differs from the name the fetch used and the fetch did not include metadata, the
fetched data is discarded: a new `NameChanged(ClaimLost)` releases the claim and returns
SKIPPED. The next analysis then fetches metadata first.

**Alternatives rejected:**
- Skip storing the newcomer until the holder is refreshed. That loses a candidate for a run,
  and the holder's own refresh can hit the same conflict on a chain of renames.
- A boolean `name_released` column. It is the same information as the placeholder, and a
  second field could disagree with the name.

### D2. Search results are not metadata fetches (C-8)

`upsert_repository(gh, now, *, metadata_fetched=True)`. Search passes `False`, and
`update_or_create` then puts `synced_at` only in `create_defaults` (Django ≥ 5.0). Existing
rows get the fresh fields and keep their fetch time.

A new row still gets `synced_at=now` because the column is non-null. That is harmless:
`stale_parts` treats a never-analyzed row (`activity_synced_at` null) as all-stale. The profile
sync keeps `True`, since it fetches languages right after.

### D3. Lock order for bulk repository writes (C-7)

`_step_search` prefilters a query's results, then stores the survivors sorted by `github_id`
(ranks are computed before sorting). Two runs therefore take row locks in the same order.

Analysis locks only its own row (and that row's children), and bulk readers use
`skip_locked` (D5), so neither joins a cycle. Name releases (D1) lock a second row outside
that order. That needs a rename race and two runs at once; a deadlock there fails one query
transaction, and the job retries through its usual policy. Accepted.

### D4. `hold` re-reads the locked row (C-14)

`hold(repo)` now selects the full row `FOR UPDATE` and copies its fields onto the in-memory
`repo`, after checking the claim token. `complete()` then computes eligibility from current
stars, push date, archive flag, license and topics, including search updates made during the
fetch. `_store` keeps setting only the fields it fetched.

### D5. Eligibility re-check is a lifecycle operation (R-4, R-12)

New `lifecycle.recheck_eligibility(repo_ids, *, now) -> int`:
- It runs in one transaction, selecting
  `filter(pk__in=ids, lifecycle__in=(RECOMMENDABLE, INDEXED, STALE)).select_for_update(skip_locked=True).order_by("github_id")`,
  annotated with `has_dependencies` and with topics prefetched.
- The filter excludes in-progress rows (their `complete()` decides), FAILED rows (their
  reason is the failure) and DISCOVERED rows (no eligibility yet). `skip_locked` makes the
  pool step never wait on an analysis's `hold`.
- For each row, it runs `eligibility()`. When the result differs from the stored one, it
  updates `is_eligible` and `ineligible_reason`. A RECOMMENDABLE row whose eligibility flips
  swaps with INDEXED and gets `lifecycle_changed_at=now`, so freshness sees a pool change. A
  STALE row keeps STALE: generation reads `is_eligible` (SCORABLE), and `complete()` decides
  the end state.
- It returns how many changed.

The pool step:
1. Removes not_code candidates (`filters.stored_not_code(repo)`, any lifecycle, candidate
   rows only).
2. Calls `recheck_eligibility` for the remaining pool's repository ids.
3. Applies the cap.

`_remove_not_code` no longer writes `Repository`. Job metadata gains `pool_eligibility_changed`.

**Alternative rejected:** re-check only `not_code`, as now. That leaves settings changes
(R-12) unhandled, and keeps a second writer of eligibility.

### D6. `not_code` with code evidence (R-5)

```
not_code(full_name, topics, primary_language, cfg, *, has_dependencies: bool | None) -> bool
    no primary language            → True
    suspected list (name/topic)    → has_dependencies is False
    otherwise                      → False
```

`None` means not analyzed yet, so the repository passes. Callers:
- `prefilter` on a search payload passes `None`.
- `eligibility()` and `stored_not_code(repo)` pass
  `repo.dependencies.exists()` when `dependencies_synced_at` is set, else `None`. Bulk callers
  annotate `has_dependencies` (`Exists`), which `_has_dependencies(repo)` reads first.
- `_step_search` and `_step_interactions` also reject with `NOT_CODE` when the stored row of a
  suspected list is `stored_not_code`. One analysis per list, globally, decides it.

The default `DISCOVERY_EXCLUDED_TOPICS` keeps its generic topics (`list`, `lists`, `books`).
Dependency evidence is what keeps a tagged library eligible. Dropping them (tried first) made
`public-apis` and `free-programming-books`, which have no dependencies, eligible at the top of a
real pool.

**Alternatives rejected:**
- Only narrowing the topics. `awesome-lint` stays rejected forever, because it is never
  analyzed, and the biggest lists (`public-apis`, `free-programming-books`) carry only generic
  topics.
- Manifest presence instead of dependencies. Manifest presence isn't stored, and a manifest
  without dependencies is rare for a tool.

### D7. Pool before analysis, with a fixed plan (C-11, C-12)

`STEPS` (service) and `DISCOVERY_STEPS` (jobs) become
`queries, search, interactions, pool, analysis`.

The analysis step plans once. If `metadata["analysis_plan"]` is absent, it takes
`pending = [r for r in ordered pool if _needs_analysis(r)]` and stores
`analysis_plan = [pk for pk in pending[:cap]]` and `analysis_total = len(pending)` (plus
`analysis_capped`). A resumed step then works on `analysis_plan` minus `analyzed`.

A job that was in flight across the deploy has no plan: it plans on entry, and a job whose
pool step is still pending runs the pool step first.

### D8. Provenance without bands, pruned per run (R-6, C-13)

`PlannedQuery.core` drops the `stars:` part. `key` keeps `@{band index}`, so resume still
tells the two requests apart. `_record` keys on `(candidate, source, query=core)`, so both
bands write one record, and the last write's rank wins.

`_step_search` stores `metadata["search_started_at"]` (this attempt's `now`) the first time it
starts, before the empty-plan check. Every record a run writes has
`last_seen_at >= search_started_at`, including after a retry with a later `now`. The pool step
deletes this developer's `CandidateDiscovery` rows with `last_seen_at < search_started_at`.
Candidates are untouched; retention still removes them.

Old band-qualified records die on each developer's first run after the release.

### D9. One pool order (C-17)

New `services/discovery/ordering.py: pool_order(queryset, *leading) -> QuerySet` annotates:
- `interacted`: `Exists` of a `previously_interacted` record;
- `best_rank`: a `Subquery` of the lowest non-null `search_rank`, which avoids the
  `GROUP BY` of `Min` and keeps the API's constant query count.

It orders by `*leading, interacted desc, best_rank asc nulls last, last_seen_at desc,
repository__full_name`. Callers:
- the pool cap;
- `_pool_repositories`, the analysis order;
- `CandidateListView`, with `leading=("state",)`.

### D10. Band counting (R-9)

`queries.band_of(stars, bands) -> Band | None` returns the band with
`low <= stars <= high` (open high = ∞). `_band_counts` labels a repository:
- `below`: under the lowest band's low;
- the band label: inside a band;
- `other`: anything else, a gap or above a closed last band.

The `other` key is present only when non-zero, so default-band metadata keeps its shape.

### D11. Backlog in a service, queued once (C-15, C-16)

New `services/repositories/backlog.py`:
- `mark_stale(now) -> int`: the body of `mark_stale_repositories`.
- `queue_batch(now) -> list[tuple[int, Kind]]` with `Kind = Literal["all", "readme", "issues"]`.
  It selects due rows as today, plus `~Q(refresh_queued_at__gte=queued_before(now))` on the
  STALE/DISCOVERED/FAILED branches (not on `abandoned_claims`). It stamps
  `refresh_queued_at=now` on the batch and returns it.

`queued_before(now) = stale_before(now) - GITHUB_MAX_RETRY_DELAY` is the same window as job
`_requeue`: a queued or retrying task gets that long to claim and finish.

The tasks only dispatch: `{"all": sync_repository, "readme": ..., "issues": ...}[kind].delay(id)`.

`complete()` and `fail()` clear `refresh_queued_at`. `release()` and `claim()` keep it, so a
retrying task's countdown is not raced.

**Explicit parts.** `RepositoryAnalysisService.run(repo_id, parts)`:
- FAILED retry: every part (C-5).
- Otherwise: `wanted = [p for p in stale_parts(repo, now) if parts is None or p in parts]`.
- Then: `metadata` is prepended for a released name.

An empty `wanted` still completes, which returns a STALE row to its state, as a `None`-parts
run with nothing stale does today.

### D12. `lifecycle_changed_at` always set (C-18)

The field becomes `DateTimeField(default=timezone.now)`, not null. The migration:
1. backfills nulls with `synced_at` (the closest real time; `RunPython`, reversible no-op);
2. alters the field.

Removed:
- the two `if repo.lifecycle_changed_at is None` patches in discovery;
- the `isnull` branches in `process_repository_backlog` and `_needs_analysis`.

`abandoned_claims` keeps its `claimed_at__isnull` branch, which is a different field.

### D13. Configuration (R-3, R-10, R-11)

**Bands.** In `base.py`, the default bands derive from `DISCOVERY_MIN_STARS`:
`[[m, 999], [1000, None]]` when `m < 1000`, else `[[m, None]]`. The E025 check stays as it
is.

**Budget warning.** New `core.W003` in `discovery_config_check` when
`DISCOVERY_MAX_QUERIES % len(bands)`. It names the unused requests.

**Topics.** `filters._topics` uses `repo.topics.all()`, so a prefetch is used. Interactions
and the pool load with `prefetch_related("topics")` and the `has_dependencies` annotation. The
module docstring drops "Pure functions" (it reads stored rows).

## Risks / Trade-offs

- **[Suspected lists cost analysis budget once each]** → The result is stored on the shared
  row, and later searches reject them without a request. Lists without a language (most of
  them) are still rejected at search.
- **[A released name is visible until the next analysis]** (`org/tool~123` in the candidate
  list) → `stale_parts` makes it due right away. Discovery's analysis or the next backlog run
  (≤ 15 min after the hourly sweep) resolves it.
- **[Pruning drops a record whose query was skipped this run (422)]** → The candidate stays
  for its retention period. Only the stale rank goes, which is the intent.
- **[`skip_locked` re-check misses a row being written]** → That row's analysis computes
  eligibility itself. Otherwise the next discovery run catches it.
- **[Explicit-part tasks no longer force a fetch]** → Background tasks only. Tests that force
  a part must make it stale first.
- **[The same query in two bands: last rank wins]** → A repository lives in one band at a
  time, and both requests run in the same run.
- **[Discovery job step order changes]** → The frontend doesn't depend on it.
  `test_discovery_api` asserts the order and is updated.

**Review follow-ups (X-1…X-6, applied before release):**
- D1: a holder that gives up its name is made ineligible `name_released` (INDEXED, and a
  claimed holder's saved state), since its name and URL are no longer its own.
- D8: pruning is skipped when the search step was SKIPPED, and records of `queries_skipped`
  are kept. Within one run, a record keeps the better rank of the two bands.
- D5/D7: the pool step's writes run inside `job_write(self.job)`.
- D11: `run()` with nothing stale on a non-STALE row releases and returns SKIPPED, instead of
  completing (which stamped a transition). `queue_batch` selects with `skip_locked` and stamps
  in one transaction; `pooled()` uses `Exists`, so the rows can be locked.

**Cleanup pass (/simplify, before release):** `DISCOVERY_STAR_BANDS` defaults to None and
`queries.configured_star_bands()` derives the default at call time (D13 moved out of
settings). `hold` uses `refresh_from_db(from_queryset=...)` and raises plain `ClaimLost`
(no `NameChanged`). The queued window is `job_guard.lost_before`, shared with job recovery.
`recheck_eligibility` writes one UPDATE per distinct outcome.

## Migration Plan

1. One `repositories` migration:
   - backfill `lifecycle_changed_at`;
   - make it non-null with a default;
   - add `refresh_queued_at` (nullable).

   Reversible: drop the column and relax the field.
2. Deploy. In-flight discovery jobs resume under the new step order (D7).
3. The first discovery run per developer prunes band-qualified records and re-checks
   eligibility. The first hourly sweep marks released names and stale-metadata rows due.

Rollback: revert the code and migrate back. Released placeholder names stay until those
repositories are next analyzed. The old code has no fallback by GitHub ID, so it would FAILED
them `not_found` on the old name. Resolve released rows before rolling back, or accept that.
