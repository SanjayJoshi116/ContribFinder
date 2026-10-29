## Context

`GitHubClient.list_open_issues(full_name)` reads `/repos/{name}/issues?state=open&sort=updated&direction=desc`
for `ISSUES_MAX_PAGES` pages (default 1 of 100) and returns `IssuePage(issues, truncated)`.
`RepositoryAnalysisService._fetch` calls it for the `issues` part; `_store_issues` replaces the
stored set with what was fetched (issue-ingestion "Issue set replaced on refresh"). Labels are
normalized later (`services/issues/labels.py` maps `good first issue`, `good-first-issue`,
`help wanted`, ... to `good_first_issue` / `help_wanted`). Matching reads stored issues through
`load_issues(ids, now, ISSUE_MAX_AGE_DAYS)`, so issues not updated within a year never match.

GitHub's `labels` query parameter matches issues carrying **all** listed labels and compares
label names exactly (case-insensitive). Repositories that rename their entry label (`E-easy`,
`beginner`) are not reached by this change.

## Goals / Non-Goals

**Goals:**
- Entry-labeled open issues of large repositories are stored even when they are not among the
  100 most recently updated.
- No change to scoring code, configurations, stored data shape or API.

**Non-Goals:**
- Discovering each repository's own entry-label names (would need a labels listing per
  repository and a mapping step; a later idea if the default names miss too much).
- Fetching more than one page per label, or labeled issues older than `ISSUE_MAX_AGE_DAYS`
  mattering to matching.
- Discovery search qualifiers (`good-first-issues:>0`, `ideas.md` §6): a separate idea.

## Decisions

### D1. One listing per label, one page each

`list_open_issues(full_name, *, label=None)`: with a label, the same listing plus
`labels=<label>`, one page (`max_pages=1`). One request per label because `labels=a,b` would
require both. *Alternative:* a search query `label:"good first issue" label:"help wanted"`
(OR is not supported there either, and search has its own 30/min limit). Rejected.

### D2. Setting `ISSUES_ENTRY_LABELS`

`env.list`, default `["good first issue", "help wanted"]` (GitHub's default label names). Empty
turns the extra listings off. New check `core.E041` (in `issue_config_check`): a list of
non-empty strings, no duplicates (case-insensitive). The page count is not configurable: one
page per label bounds the cost at `len(labels)` requests.

### D3. Merge order and identity

`merge_issue_pages(recent, labeled)` (pure, in `services/repositories/analysis.py` or next to
`IssuePage`): recent issues first, then each labeled page's issues not already seen, by
`github_id`. `truncated` comes from the recent page only (spec: it describes the recent
listing). The merged list goes to `_store_issues` unchanged, so refresh semantics stay: an
issue absent from every listing is removed.

### D4. Only when the recent listing is truncated; failures

A recent listing that did not reach its cap holds every open issue, so the labeled listings run
only when it is truncated. That also covers issues disabled (410 → empty, not truncated) and
keeps small repositories at one request. (Found while implementing; the first draft fetched
labels always.) Any error in a labeled listing propagates like a recent-listing
error today: the `issues` part fails, stored issues are kept (spec "Labeled listing fails").
*Alternative:* keep the recent page and drop the failed labels. Rejected: storing a partial set
would delete the labeled issues stored last time, which is worse than keeping the old set.

### D5. Cost

Per issue fetch: 1 request, plus `len(ISSUES_ENTRY_LABELS)` (2 by default) only for a
repository whose recent listing hit the cap; all conditional. The
backlog refreshes issues every 6 h per pooled repository; ETags make unchanged listings 304s.
The discovery analysis budget counts repositories, not requests, so it is unchanged.

### D6. Ranking rule

This changes what users see (more relevant issues, higher `issue_fit` for repositories with old
entry issues) without changing any configuration. The benchmark stores each repository's
issues as data, so `evaluate_ranking` and `baselines.json` cannot move; the rule "must win on
the selection benchmark" has nothing to measure. Instead, the change records a before/after
measurement on the local database: for each pooled repository, entry-labeled issues stored and
`relevant_issue_count` of the developer's recommendations, before and after one issue refresh.
`baselines.json` must stay unchanged (test). Whether issue coverage needs its own benchmark is
K-3 (issue-level evaluation), unchanged.

## Risks / Trade-offs

- [Repositories with renamed entry labels gain nothing] → Non-goal; the measurement shows how
  many pooled repositories have an entry label at all.
- [An issue that loses its label and is not recent disappears on the next refresh] → Correct
  under "Issue set replaced on refresh": it no longer qualifies.
- [More GitHub requests per refresh] → Bounded (+2 by default), conditional, and turned off by
  an empty `ISSUES_ENTRY_LABELS`.
- [Old labeled issues still filtered by `ISSUE_MAX_AGE_DAYS`] → Intended: a year-old untouched
  issue is a poor recommendation.
