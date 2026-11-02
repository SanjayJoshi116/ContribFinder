## Context

See proposal.md (Why). `core/admin.NoAddDeleteAdmin` already serves the audit, GitHub and (since
0.12.48) jobs admins. Developer data is rebuilt by analysis and removed only by
`services/data_deletion.py` under `lock_developer`. `services.jobs.active_jobs(user, job_type)`
is the one definition of an active job (it excludes stalled RUNNING jobs).

## Goals / Non-Goals

**Goals:** the admin cannot change or delete developer data; stable, documented list order;
the command does not queue work the app would refuse or duplicate.

**Non-Goals:** SPA paging for skills and interests (not needed below the page size; the guard
test marks when it is); changing `start_profile_analysis` itself (the sync's own analysis step
and the beat paths do not go through the command).

## Decisions

### D1. Admin (DEV-1, DEV-2, DEV-9)

`class ReadOnlyAdmin[M: Model](NoAddDeleteAdmin[M])` with `has_change_permission` False. The
inline already has `can_delete=False`; an `InterestEvidenceInline` mirrors `SkillEvidenceInline`
(read-only fields, `extra = 0`). `list_select_related`: `("user",)` for profiles,
`("profile", "skill")` for developer skills, and `("profile", "interest")` for developer
interests. `DeveloperProfile.__str__` prints only `user_id`, so the profile row is enough.

### D2. Evidence and list order (DEV-3, DEV-7)

One constant per app module, `EVIDENCE_ORDER = ("source", F("observed_at").desc(nulls_last=True),
"pk")`, used by both prefetches. Model `Meta.ordering` gets the same expressions
(`AlterModelOptions` migration: state only, no SQL). List order: `("-confidence",
"skill__name", "pk")` and `("-strength", "interest__name", "pk")`.

### D3. Schema guard (DEV-8)

`if getattr(self, "swagger_fake_view", False): return DeveloperInterest.objects.none()`, as in
`SkillListView`.

### D4. Command (DEV-4, DEV-5)

Base queryset adds `is_active=True`. In the loop, `active_jobs(user, SYNC).exists()` → count as
`syncing` and skip (the sync ends in its own analysis). Output: `Queued N analysis job(s); M
already active; K syncing (skipped).` With `--user`, an inactive user raises `CommandError("User
<id> is inactive.")`; a user without a completed sync keeps the current error.

Alternative: put the sync check into `start_profile_analysis`. Rejected: it changes
specified job behavior (`sync-jobs`, `developer-profile`) for every caller, while the
duplication only arises from the operator command.

### D5. Catalog guard (DEV-6)

Test: `len(SKILLS) <= ProfileListPagination.max_page_size` and the same for `INTERESTS`, with a
message naming `features/profile/api.ts`.

## Risks / Trade-offs

- [Staff can no longer delete an obsolete Skill row] → stale catalog rows are harmless (analysis
  never links them); a cleanup belongs in a migration or command with its own review.
- [`nulls_last` ordering cannot use an index] → evidence lists are a few rows per skill.
