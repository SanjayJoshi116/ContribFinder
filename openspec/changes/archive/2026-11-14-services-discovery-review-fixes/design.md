## Context

Findings and verdicts are in `Bug_Backlog.md` batch 59. Each was checked by reading the code
against the spec. `plan_queries` is pure and its tests pin exact plans. `allocate` is shared by
every plan. `_record` runs inside the search step's `job_write`. `search_started_at` is written
once, by the first attempt that reaches the search step, and pruning already reads it. The yield
report is one query (`load`) plus a pure `build`.

## Goals / Non-Goals

**Goals:** behavior as the spec deltas say, with plans for the default configuration unchanged
except where DSC-1 applies, and no extra queries.

**Non-Goals:** changing shares, bands, budget or any scoring weight. DSC-3 (empty login) gets no
guard, since it cannot happen (proposal).

## Decisions

### D1. Covered topics from planned queries: two passes (DSC-1)

The topic strategy's candidate list depends on which skill and interest queries are planned. The
skill and interest quotas depend on the topic list only through the wrap-around, where budget
the topic strategy cannot use returns to earlier strategies.
- Pass 1: allocate with topic candidates that exclude every skill and interest topic (today's
  list). Covered = the topics of skill and interest queries within pass-1 quotas.
- Pass 2: the topic list excludes only the covered topics. Allocate again and cut as before.

A longer topic list can only lower what wraps back, so the pass-2 skill and interest quotas are
at most the pass-1 ones. A topic covered in pass 1 whose query loses its wrapped slot in pass 2
stays excluded. That slot went to another topic query, so no request is wasted. Two passes are
deterministic and bounded. A fixed-point loop was rejected: it can oscillate, and it is no
clearer.

Alternative: plan topics without exclusion, then drop duplicates after cutting and backfill.
Rejected: a backfill outside `allocate` duplicates the carry rule.

### D2. Largest remainder in `allocate` (DSC-4)

`base` is the floor of each share. The leftover goes one slot each to strategies sorted by
descending `budget * share % total`, ties in `STRATEGIES` order. A strategy with share 0 has
remainder 0 and gets a slot only after every positive remainder is served. Today a share-0
strategy is skipped entirely, so the leftover is restricted to positive shares. The carry and
wrap-around passes are unchanged. Default shares at budget 10 have no remainder, so
`test_budget_*` plans stay as they are. The existing `allocate(10, ...)` wrap test keeps its
numbers, also with no remainder.

### D3. "This run" is `search_started_at` (DSC-2)

`_record` reads the run's search start once (the step already holds `self.job.metadata`). It
treats a record as seen this run when `last_seen_at >= search_started_at`. Pruning uses the same
boundary, so "seen this run" has one definition. Interaction records have no rank and are not
affected.

### D4. Report reads three keys (DSC-5, DSC-6)

`load` returns per run `(query_yield, planned, searched)` from
`values_list("metadata__query_yield", "metadata__plan__0", "steps__search")`. These are JSON key
transforms, so the rest of the metadata is never fetched. Rules:
- A run has no search when it planned nothing (`plan` empty or missing) or never reached the
  search step (`steps.search` missing).
- A run without yield searched but has no `query_yield`.

The window filters on `Coalesce("started_at", "created_at")`. `YieldReport.runs_without_search`
joins the JSON (`runs_without_search`) and the printed header. `build` takes the triples. Its
dict-only input in tests becomes a small helper in the test module.

### D5. Filters (DSC-7, DSC-8)

`prefilter` computes `stored_has_dependencies` only inside `reason is None`.
`filters.stored_result_not_code(gh, repo, cfg) -> bool` is true when the search result is a
suspected list and the stored row says it has no dependencies. It reads dependencies only for a
suspected list. The search step calls it. The rule then lives in `filters.py` only.

## Risks / Trade-offs

- [DSC-1 changes plans for profiles whose skill or interest queries are cut] → Tests pin a case.
  The benchmark stores candidates, so baselines cannot move. The yield report shows the topic
  strategy's share after release.
- [A run from before `search_started_at` existed, resumed after the upgrade] → Without the key,
  `_record` falls back to the attempt clock (today's behavior). Every run since 0.12.7 writes it.
- [JSON key transforms on PostgreSQL] → One SQL query. The report test asserts the query count.

## Migration Plan

None: no model, setting or API change. Stored discovery records correct themselves on the next
run.
