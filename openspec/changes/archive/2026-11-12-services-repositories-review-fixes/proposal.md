## Why

The review sweep's first low-priority module, `apps/backend/services/repositories/`
(`Bug_Backlog.md` batch 56, RS-1…RS-10), found one serious problem and several smaller ones.

The serious one (RS-2): GitHub text is stored as received. A NUL character, or an unpaired
surrogate from a `\ud800` escape in JSON, cannot be stored by PostgreSQL. Such a write raises an
error that is not a repository error. In discovery, the analysis step re-raises it, so one
repository with a NUL in its README or in an issue fails the whole discovery job, on every
retry, for every developer whose pool holds it. Background refreshes of that repository also
fail forever, and it is never marked FAILED. The same applies to every other GitHub string the
app stores: a repository description in a search result fails the search's transaction.

The smaller ones:
- A refresh without metadata trusts the stored name, so it can store another repository's data
  under it (RS-1).
- Queuing the refresh of a repository that released its name can fail work that was already
  saved when the broker is down (RS-3).
- An eligibility re-check is stamped with the discovery job's start time, so other developers'
  freshness checks can miss it (RS-5).
- Name release compares names case-sensitively (RS-6).
- An analysis that lost its claim reports FAILED (RS-7).
- The repository's entry-label flags use a weaker label match than issue analysis (RS-8).
- `mark_stale` reads whole rows (RS-9).
- Name release locks rows out of GitHub ID order (RS-10).

The security review of the module found nothing.

## What Changes

- RS-2: the GitHub client makes every string it returns storable. It removes NUL characters and
  replaces unpaired surrogates with U+FFFD in raw text (README, files) and in every string of a
  parsed JSON body. One place (`services/github/client.py`'s response wrapper) covers README,
  issues, labels, descriptions, topics and the profile README alike.
- RS-1: a refresh that does not fetch metadata first checks by name that GitHub still has the
  same GitHub ID there. On another ID or a 404, it fetches metadata by GitHub ID first (as a
  metadata refresh does) and fetches the other data types under the current name.
- RS-3: `queue_released` sends its tasks with `on_commit(..., robust=True)`, tries every task,
  and clears the queued mark of each task the broker refused.
- RS-5: `recheck_eligibility` stamps the transition with the wall clock.
- RS-6: `release_name` finds holders case-insensitively.
- RS-7: `run` returns SKIPPED when `fail` changed nothing because the claim was lost.
- RS-8: `has_good_first_issue_label` and `has_help_wanted_label` come from
  `services.issues.labels.category`, the same rule issue analysis uses. `normalize_label` is
  removed. This shows in rankings through data, because the openness signal reads these flags.
  The benchmark datasets store the flags, so the baselines cannot move; `evaluate_ranking`
  confirms this.
- RS-9: `mark_stale` loads only the fields it needs and sends one UPDATE per (lifecycle, stale
  parts) group.
- RS-10: `release_name` locks the holders in GitHub ID order before updating them.
- RS-4 is a false positive and is not changed: `claim` overwrites `previous_lifecycle`, so a
  STALE row's refresh restores STALE.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `github-data-sync`: new "Stored GitHub text" (NUL removed, unpaired surrogates replaced);
  "Profile README ingestion" ("unchanged" except for that).
- `repository-analysis`: "Repository data collection" (entry labels by the issue label
  normalization); new "Identity confirmed before a refresh without metadata", "Repository names
  compare case-insensitively", "Broker refusal while queuing a released name".
- `repository-discovery`: new "Eligibility re-check stamped when made".

RS-7, RS-9 and RS-10 change no specified behavior.

## Impact

- `services/github/client.py` (response text cleaning), `services/repositories/{analysis,
  lifecycle,backlog}.py`, tests.
- One index-only migration (`repositories.0010`, `Upper("full_name")`, for the case-insensitive
  name lookup on every upsert). No API change (OpenAPI `1.0.0`), no frontend change, no scoring or configuration
  change. Stored data changes on the next fetch: cleaned text, corrected entry-label flags (RS-8,
  ranking-visible through data). The `normalize_label` export is removed.
