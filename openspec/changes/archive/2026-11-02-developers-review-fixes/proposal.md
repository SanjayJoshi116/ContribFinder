## Why

The review sweep's next module, `apps/backend/developers/` (`Bug_Backlog.md` batch 37,
DEV-1…DEV-9), found that the "read-only" admin still lets staff delete skills, interests and
profiles. Those deletes cascade across every developer and bypass the app's deletion routine,
locks, job cancellation and audit. It also found smaller issues:
- the admin lists run one query per row, and interest evidence is not shown;
- undated evidence is listed before the newest dated evidence;
- the skill and interest list order has no unique tiebreaker, so pages can repeat or skip rows;
- the interests list has no schema-generation guard;
- `reanalyze_profiles` queues deactivated users, and users whose sync is running.

The security review of the module found nothing.

## What Changes

- DEV-1, DEV-2, DEV-9: `ReadOnlyAdmin` builds on `core.admin.NoAddDeleteAdmin` (no add, no
  delete) and keeps no change permission. Each admin selects its related rows with the list
  (`list_select_related`), and `DeveloperInterestAdmin` shows its evidence inline.
- DEV-3: evidence is ordered by source, then newest first with undated evidence last, in the
  model ordering and in both API prefetches.
- DEV-7: the skill and interest lists break ties by primary key.
- DEV-8: `InterestListView.get_queryset` returns an empty queryset during schema generation,
  like every other list view.
- DEV-4, DEV-5: `reanalyze_profiles` only takes active users, and skips users whose GitHub sync
  is active (reported as a separate count). `--user` names the reason when it cannot queue.
- DEV-6 (accepted with a guard): the catalog (170 skills, 16 interests) is below the lists'
  `max_page_size` (200), and analysis only creates catalog entries, so the SPA's single page
  holds every row. A test fails once either catalog grows past the page size, which is when
  the SPA must follow `next`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None (`skip_specs: true`). The specs order skills by confidence and interests by strength,
which stays true; evidence order, admin behavior and the command are not specified.

## Impact

- `apps/backend/developers/{admin.py,models.py,api.py,management/commands/reanalyze_profiles.py}`,
  a migration for the evidence ordering (state only, no SQL), tests.
- No API shape change (OpenAPI `1.0.0`; `npm run api:sync` must show no drift), no frontend
  change, no ranking change: evidence order and tiebreakers do not feed scoring.
