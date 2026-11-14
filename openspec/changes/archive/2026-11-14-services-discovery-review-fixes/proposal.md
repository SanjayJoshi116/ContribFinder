## Why

The review sweep's third low-priority module, `apps/backend/services/discovery/`
(`Bug_Backlog.md` batch 59, DSC-1…DSC-8), found that discovery spends its search requests and
records ranks less well than its spec says:
- A recurring topic of the developer's own repositories is never searched when the skill or
  interest query that "covers" it is cut by the budget (DSC-1).
- When a retried run searches the same query in a second band, the better rank is not kept: the
  "same run" test compares against the attempt's clock, which a retry resets (DSC-2).
- Leftover budget slots go to the first strategies in order, not by share, so non-default shares
  are not respected (DSC-4).
- The yield report filters its window by a start time that cancelled-before-start runs do not
  have, and labels runs that never searched as runs "from before the yield was recorded" (DSC-5).

The rest are efficiency and structure (DSC-6…DSC-8). DSC-3 (empty login) was rejected: a run
cannot start without a GitHub account, whose username sign-in requires to be non-empty, and a
deletion cancels the run before removing the account. The security review found nothing.

## What Changes

- DSC-1: a recurring own-repository topic is left out of topic search only when a skill or
  interest query for that topic is actually planned within the budget.
- DSC-2: the same query in two bands keeps the better rank across attempts of one run: "this
  run" is the run's recorded search start, not the attempt's clock.
- DSC-4: the budget is split by largest remainder (ties in strategy order). With the default
  shares and budget (2/4/3/1, 10 queries over two bands) the split is exact and unchanged.
- DSC-5: the yield report's window uses the job's start, or its creation when it never started.
  Runs that made no search request are counted on their own line, apart from runs that searched
  before the yield was recorded.
- DSC-6: the report reads only the needed keys of the job metadata.
- DSC-7: `prefilter` reads stored dependencies only when no other rule rejected the repository.
- DSC-8: one filters-stage helper decides whether a stored search result is not code. The search
  step calls it instead of repeating the rule.
- No scoring or configuration change. DSC-1, DSC-2 and DSC-4 change which requests a run makes
  or which rank a discovery record holds. The pool order reads those ranks, so the pool and its
  cap can differ. Benchmarks store their candidates, so baselines cannot move.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repository-discovery`: "Search queries from the developer profile" (topics covered only by
  planned queries; largest-remainder split), "Discovery provenance" (better rank across attempts
  of one run), "Discovery yield report" (window for never-started runs; runs without a search).

## Impact

- Code: `services/discovery/queries.py` (`plan_queries`, `allocate`), `service.py` (`_record`,
  search step), `filters.py` (`prefilter`, new stored-result helper), `yield_report.py` (`load`,
  `build`, `YieldReport`), `repositories/management/commands/discovery_report.py` (new line).
- JSON of `discovery_report`: new key `runs_without_search`.
- Tests: `test_discovery_queries.py`, `test_discovery_service.py`, `test_discovery_yield_report.py`.
- No API, model, migration, setting or OpenAPI change. No ranking configuration change.
