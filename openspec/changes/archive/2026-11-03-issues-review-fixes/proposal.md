## Why

The review sweep's next module, `apps/backend/issues/` (`Bug_Backlog.md` batch 40,
ISS-1…ISS-8), found that both issue admins still let staff delete rows (SIM-8 for this module,
as DEV-1 and REPO-6). Deleting an `Issue` cascades into every developer's `RecommendedIssue`
outside `data_deletion` and the lock order. Deleting either kind of row leaves the
recommendation's issue snapshots (`relevant_issue_count`, `issue_difficulties`,
`issue_contribution_types`) counting it, so the difficulty and contribution-type filters return
recommendations with no matching issue until the next generation. It also found smaller issues:
- the issue changelist runs one query per row;
- the technology source choices repeat the literals of `services/issues/technologies.py`;
- the `readonly_fields` lists do nothing once change permission is off.

Three findings about the issue detail are accepted. Each is bounded by the freshness sweep, and
the spec allows it:
- ISS-3: "matched" uses the current skills, while the reasons come from the last generation.
- ISS-4: an issue assigned or locked since generation is still shown.
- ISS-6: an issue transferred between two pooled repositories keeps its old link.

The security review of the module found nothing.

## What Changes

- ISS-1, ISS-2, ISS-8: `IssueAdmin` and `RecommendedIssueAdmin` use `core.admin.ViewOnlyAdmin`
  (no add, change or delete) instead of `recommendations.admin.ReadOnlyAdmin`. The redundant
  `readonly_fields` are removed.
- ISS-5: `IssueAdmin.list_select_related = ("repository",)`.
- ISS-7: `IssueTechnologySerializer.source` takes its choices from `technologies.TITLE`,
  `LABEL` and `BODY`. The OpenAPI output is unchanged.
- ISS-3, ISS-4, ISS-6 accepted and recorded with their reasons. The freshness sweep regenerates
  after a profile analysis (`analyzed_at`) or an issue fetch (`issues_synced_at` in
  `staleness.PART_FIELDS`). That regeneration removes the stale link or reason.
- SIM-8 stays open for `feedback/` and `recommendations/`, which still import `ReadOnlyAdmin`.
  The `recommendations/` sweep removes it.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None (`skip_specs: true`). Admin permissions, query counts and serializer choice sources are
not specified. The issue detail keeps the shape and behavior the `issue-matching` spec
describes.

## Impact

- `apps/backend/issues/{admin.py,serializers.py}`, tests.
- No migration, no API shape change (OpenAPI `1.0.0`; `npm run api:sync` must show no drift),
  no frontend change, no ranking change.
