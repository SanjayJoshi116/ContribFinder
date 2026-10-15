## Context

See proposal.md (Why). Discovery today (`services/discovery/`):

- `queries.plan_queries` builds query cores per strategy (language, skill, interest, topic), allocates `DISCOVERY_MAX_QUERIES` (10) across strategies by `DISCOVERY_QUERY_SHARES`, and appends one qualifier string: `archived:false fork:false is:public pushed:>=… stars:>=20 -user:…`. `PlannedQuery.core` (the query without qualifiers) is the stable provenance text stored in `CandidateDiscovery.query`; `key` identifies the query for resuming.
- `GitHubClient.search_repositories` takes the first page in best-match order (`DISCOVERY_RESULTS_PER_QUERY` = 30). Best match weighs popularity heavily, so with no upper bound the top 30 of every query are the most-starred matching repositories.
- `filters.prefilter` (search results and interactions) and `filters.eligibility` (after analysis, via `services/repositories/lifecycle.py`) return a reason code. Neither looks at name, topics or primary language.
- `_step_pool` caps the pool by (interacted desc, best search rank asc, last seen desc, name); `_pool_repositories` uses the same order for analysis.

The `real-a` export: median 906 contributors; lists and documentation repositories among the 39.

## Goals / Non-Goals

**Goals:**
- Every query yields smaller projects as well as established ones; the capped pool keeps both.
- Curated lists and documentation repositories never become eligible candidates.
- Visible band mix per discovery run, so the effect can be checked without exporting.

**Non-Goals:**
- Ranking by project size or using `DeveloperProfile.preferred_project_size` (it is not derived yet). Ranking still decides the order; this change only widens what it sees.
- Changing the search sort (best match stays) or paging deeper.
- Re-filtering the benchmark datasets: they are fixed pools and unaffected.

## Decisions

### D1. Star bands as query qualifiers, not a post-filter
Each planned query core is requested once per band: `stars:20..999` and `stars:>=1000` by default (`DISCOVERY_STAR_BANDS`, JSON list of `[low, high]`, `high` null for open-ended). The band's lower bound replaces `DISCOVERY_MIN_STARS` in the query; the pre-filter's minimum-stars check uses the lowest band's lower bound, so `DISCOVERY_MIN_STARS` stays as the first band's default lower bound and validation requires them to agree (the first band starts at `DISCOVERY_MIN_STARS`).

Alternatives: (a) one query, then drop results above a star ceiling: the top 30 would be mostly dropped, leaving almost nothing. (b) `sort=updated` or `sort=stars&order=asc`: loses relevance ordering (asc stars returns near-empty repos). (c) Paging deeper (pages 2–3): more requests per query and still popularity-ordered. Bands keep GitHub's relevance ordering inside each size range at one request per band.

Two bands by default: three bands at 10 queries would be 30 requests, the whole per-minute search limit. The split at 1000 is a starting point, configurable without code change.

### D2. Budget counts requests, planned per query
`DISCOVERY_MAX_QUERIES` keeps its name and now counts requests; default 20. The allocator divides the budget by the number of bands (floor) to get the number of query cores, allocates those across strategies as today, and expands each chosen core into one `PlannedQuery` per band, bands in ascending order, cores in today's order. A core is never planned in only some bands. With one band configured the behavior is exactly today's (budget = queries).

`PlannedQuery.core` includes the band (`language:Python stars:20..999`) so each band has its own `CandidateDiscovery` record with its own rank; `key` gets a `@<band index>` suffix so resume works per request. Old in-flight jobs keep their stored plan and resume unchanged.

### D3. Pool mix by per-band ranks, ordering unchanged
Search ranks restart at 1 in every band, so ordering by best rank already interleaves bands (rank 1 of each band, then rank 2, …). No change to the pool or analysis ordering is needed. `_step_pool` records `pool_bands`: count of pool candidates per band by the repository's current stars (label `20..999`, `1000+`), plus candidates below the lowest band (previously interacted) under `below`. Job metadata only; no API or schema change.

Alternative: explicit round-robin by band in the ORDER BY. Rejected: needs the band computed in SQL for little gain over the natural interleave, and a repository found in both bands (stars changed between requests) would complicate it.

### D4. `not_code` rule in the shared repository rules
A pure function `not_code(name, topics, primary_language, cfg)` returns true when the repository name is `awesome` or starts with `awesome-` (case-insensitive), any topic is in `DISCOVERY_EXCLUDED_TOPICS` (default `awesome`, `awesome-list`, `awesome-lists`, `curated-list`, `list`, `lists`, `books`, `free-books`, `interview-questions`, `cheatsheet`, `cheatsheets`), or the primary language is empty. It runs in `prefilter` after the existing repository rules (so `archived` etc. keep precedence) and in `eligibility`, which loads the repository's topics (one query; lifecycle calls it per repository already). Applies to previously interacted repositories too: a list is not a contribution target regardless of history.

Alternatives: `-topic:awesome-list` qualifiers in the query: saves result slots but needs one qualifier per topic and cannot express "no language" or the name rule; the filter stage is where rules live (design D4 of Phase 4). Checking descriptions for words like "curated": too many false positives.

Re-check in the pool step (added during verification): the first refresh showed lists from earlier runs still recommended. Their analysis was fresh, so eligibility was not re-run, and their pre-band discovery records (ranks 1–3) kept them under the cap. The pool step now applies `not_code` to stored data (name, topics, primary language; one prefetched query) before the cap: matching candidates are removed and the shared repository is marked ineligible `not_code` (`RECOMMENDABLE` → `INDEXED`), as eligibility would. Job metadata `pool_not_code` counts removals. Generation then deletes their recommendations, as it does for any repository that leaves the ranking.

Known gaps, accepted: documentation-style repositories with code languages and no list topics (`system-design-primer`, `developer-roadmap`, `prompts.chat`) still pass. Ranking and the judge handle those.

### D5. Validation at startup
A Django system check (`core` checks module) validates `DISCOVERY_STAR_BANDS`: non-empty, integer bounds, ascending, non-overlapping, only the last band open-ended, first lower bound equal to `DISCOVERY_MIN_STARS`, and `DISCOVERY_MAX_QUERIES` at least the number of bands. Errors stop `runserver`, workers and management commands, like other configuration errors.

## Risks / Trade-offs

- [Twice the search requests per run] → 20 per run is within 30/min; search rate limits already retry with backoff and resume (Phase 4). Users who refresh often hit the limit sooner; the budget is configurable.
- [Smaller projects can be less maintained] → the push window and license rules still apply, and activity signals in ranking are unchanged.
- [Star count is a proxy for contributors] → it is the only size filter search offers. The pool band counts and the next `real-a` export show whether it works.
- [Existing pools still hold giants and lists] → lists become ineligible on their next analysis; giants stay until they lose their place under the cap or expire after 30 days. For the re-export, a Refresh is enough: new small-band candidates take rank-1 slots.
- [Name and topic rules miss some non-code repositories, or catch a real project tagged `list`] → topics are configurable; rejections are counted per reason on the job, so a spike is visible.

## Migration Plan

No schema migration. Deploy, then the next discovery run (beat refresh or Refresh button) plans banded queries. Rollback: set `DISCOVERY_STAR_BANDS=[[20, null]]` and `DISCOVERY_MAX_QUERIES=10` for the old query shape; `DISCOVERY_EXCLUDED_TOPICS=[]` narrows `not_code` to name and language.
