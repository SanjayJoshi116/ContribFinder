## Why

Issue collection fetches one page of the 100 most recently updated open issues per repository.
In large repositories, older issues labeled `good first issue` or `help wanted` fall past that
cap. As a result, the repositories with the most entry points for a newcomer get the lowest
`issue_fit` and the fewest relevant issues (`ideas.md` §7). Ranking changes no longer wait for
judged real developers (K-1 optional since 2026-10-28), so this cheap, high-value coverage fix
can ship now.

## What Changes

- When the recent listing reaches its cap, issue collection also fetches open issues carrying
  each configured entry label, newest update first, one page per label. The default labels are GitHub's defaults, `good first issue`
  and `help wanted`. The result is merged with the recent page, with no duplicates.
- New setting `ISSUES_ENTRY_LABELS` (default the two labels above; an empty list turns the
  extra fetches off), validated by a system check.
- The stored issue set is the merged set. The existing refresh rule still applies: issues
  absent from both the recent page and the labeled pages are removed. A failed labeled fetch is
  a failed issue fetch, so the stored issues are kept, as today.
- "Truncated" still describes the recent listing only.
- Cost: two more GitHub requests per issue fetch of a repository with more open issues than the
  cap (default settings); none for smaller ones. They are
  conditional (ETag), like every other client request.
- Ranking-visible through data only: no scoring code or configuration changes. The benchmark
  stores each repository's issues, so the baselines cannot move. The change records a
  before/after measurement on the local candidate pool instead (see design D6).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `issue-ingestion`: "Issue collection" also fetches issues carrying the configured entry
  labels and merges them with the recent page.

## Impact

- `services/github/client.py` (labeled listing), `services/repositories/analysis.py` (fetch
  and merge), `config/settings/base.py` (`ISSUES_ENTRY_LABELS`), `core/checks.py` (new check
  id), `.env.example`.
- Tests: recorded fixtures for labeled listings, merge, 410, failure, setting check.
- GitHub request budget: +2 requests per issue fetch of a capped repository (default settings).
- No API, model, migration, scoring-config or frontend change. Users see more relevant issues
  on large repositories after their next issue refresh (6 h staleness).
