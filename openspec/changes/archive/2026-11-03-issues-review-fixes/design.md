## Context

See proposal.md (Why). `core.admin.ViewOnlyAdmin` (`NoAddDeleteAdmin` plus no change) is the
one view-only base for job-written data. Developers, repositories and jobs already use it, with
admin tests through `shared_fixtures.assert_view_only` and `changelist_queries`.
`recommendations.admin.ReadOnlyAdmin` still allows delete. Feedback and recommendations still
import it.

## Goals / Non-Goals

**Goals:** the issue admins cannot add, change or delete; the issue changelist query count does
not grow with its rows; the technology source choices have one definition.

**Non-Goals:** removing `ReadOnlyAdmin` (the `recommendations/` sweep does that); changing what
the issue detail shows (ISS-3, ISS-4, ISS-6 are accepted, see D3).

## Decisions

### D1. Admin (ISS-1, ISS-2, ISS-5, ISS-8)

Both admins subclass `ViewOnlyAdmin[...]`. `IssueAdmin.list_select_related = ("repository",)`,
because its `repository` column prints `Repository.__str__` (`full_name`).
`RecommendedIssueAdmin` needs none: `Recommendation.__str__` and `Issue.__str__` read only ids.
`readonly_fields` are removed; with change permission off, Django shows every field read-only.

### D2. Technology source choices (ISS-7)

`choices=[technologies.TITLE, technologies.LABEL, technologies.BODY]`, imported from
`services.issues.technologies`. The values and order are unchanged, so the schema does not
change. A test checks the field's choices against the constants.

### D3. Detail staleness accepted (ISS-3, ISS-4, ISS-6)

The freshness sweep (every 30 minutes) regenerates a profile when its `analyzed_at` or a pooled
repository's `issues_synced_at` moves. Regeneration re-runs `load_issues`, which filters by
assignee, lock and repository, and rewrites the reasons. That bounds every case.

Alternative considered: the detail view also requires `issue.repository_id ==
recommendation.repository_id` and no assignee or lock, and otherwise answers 404. Rejected: the
recommendation detail would still list the issue, and its link would then 404. A consistent fix
would filter both endpoints, or show a "taken since" flag, which is a spec change for minutes of
staleness.

## Risks / Trade-offs

- [Staff can no longer delete a bad issue row] → the next issue fetch rewrites or deletes it
  (`_store_issues` drops rows the listing no longer holds); data deletion removes orphans.
