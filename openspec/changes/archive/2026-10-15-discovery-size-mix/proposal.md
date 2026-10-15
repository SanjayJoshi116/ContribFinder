## Why

The first real benchmark export (`real-a`, `benchmark-real-judgments`) showed that discovery fills the pool almost only with very large projects (median 906 contributors, 2 of 39 under 50), plus several curated lists and documentation repositories (awesome-python, public-apis, free-programming-books) that are not code a developer contributes to. Search asks GitHub for "best match" with only a minimum star count, best match favors the most popular repositories, and the pool cap keeps the best-ranked ones, so smaller projects never reach ranking. Ranking cannot recommend what discovery never finds, and judging a pool of giants is not worth a judge's time, so this comes before the real-developer judging is finished.

## What Changes

- Search runs each query in configured **star bands** (default: 20–999 and 1000+), so every query contributes both smaller and established projects. The bands replace the single `stars:>=` qualifier; the lowest band's lower bound is the minimum star count.
- The query budget counts search requests (one query in one band). The default budget rises from 10 to 20, so the number of distinct queries stays 10.
- Because search ranks restart in each band, the pool cap and analysis order (previously interacted, then best search rank) now keep a mix of bands instead of only the most popular projects. Each discovery job records how many pool candidates fall in each band.
- New pre-filter and eligibility reason **`not_code`**: curated lists and documentation repositories, recognized by name (`awesome`, `awesome-*`), by configured topics (e.g. `awesome-list`, `curated-list`, `books`, `interview-questions`), or by having no detected primary language. Rejected before they become candidates. Candidates already in a pool become ineligible on their next analysis.
- No ranking change: scoring configurations, signals and the benchmark baselines are unchanged.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `repository-discovery`: search queries run in star bands with the budget counting requests; pre-filtering and eligibility add the `not_code` reason; pool maintenance records the band mix.

## Impact

- Code: `services/discovery/queries.py` (bands in the plan, budget per request), `services/discovery/filters.py` (`not_code` rule), `services/discovery/service.py` (band counts in job metadata), `services/repositories/lifecycle.py` (eligibility re-check reads topics), `config/settings/base.py` and `.env.example` (`DISCOVERY_STAR_BANDS`, `DISCOVERY_EXCLUDED_TOPICS`, `DISCOVERY_MAX_QUERIES` default 20).
- GitHub usage: up to twice as many search requests per discovery run (20 instead of 10), within the authenticated search limit of 30 per minute; rate limits are already handled by retrying.
- Data: no migration. Provenance query text now includes the band (`language:Python stars:20..999`), so existing candidates get new discovery records on the next run; old records expire with the retention period.
- API: none (job metadata is not part of the schema). Benchmark and `baselines.json`: unchanged (evaluation uses fixed pools).
- Follow-up: after a refresh, re-export `real-a`, judge it, and finish the `benchmark-real-judgments` carry-over.
