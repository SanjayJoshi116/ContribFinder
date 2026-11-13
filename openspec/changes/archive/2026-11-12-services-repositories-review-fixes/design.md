## Context

See proposal.md (Why). Every GitHub read goes through `GitHubClient._get`, which returns a
`_Response` built from a fresh 200 or from the ETag cache on a 304. Callers read `.text` (raw
files: READMEs, manifests) or `.json()` (everything else, including `_paginate`). OAuth token
exchange (`oauth.py`) parses its own httpx responses and stores no GitHub text.

Repository analysis (`services/repositories/analysis.py`) decides the parts to fetch in `run`,
fetches outside any transaction, then stores under `lifecycle.hold`. `hold(fetched_name=)` raises
`NameChanged` when our stored name changed during a fetch made without metadata.
`backlog.queue_released` runs inside the caller's transaction, whether that is a search upsert,
a profile sync upsert, an analysis store, or the analysis' `NameChanged` handler (autocommit).

## Goals / Non-Goals

**Goals:** no GitHub string can make a database write fail; no repository stores another
repository's data; saved work never fails because of a broker refusal afterwards; stored
transition times are wall clock times.

**Non-Goals:**
- A case-insensitive unique constraint on `full_name`: it would need a migration that repairs
  existing duplicates first. Case-insensitive release (RS-6) stops new ones from staying.
- Storing the identity check's metadata as a metadata refresh (D2).
- RS-4 (false positive).

## Decisions

### D1. Clean text at the client boundary (RS-2)

`services/github/client.py` gets `storable(text)` and `_storable_json(value)`:
- `storable(text)` removes `\x00` and replaces every code point in U+D800–U+DFFF with U+FFFD.
  After `json.loads`, a valid surrogate pair is already one astral character, so any surrogate
  left is unpaired. Raw text decoded by httpx can't hold surrogates, but the same function
  serves both.
- `_storable_json(value)` walks the parsed body recursively (dicts, keys included; lists;
  strings) and applies `storable`.
- `_Response.json()` returns `_storable_json(json.loads(self.text))`. `_Response` gets a
  `content` property, `storable(self.text)`, and the raw-file methods (`get_readme`,
  `get_profile_readme`, `get_file`) read it instead of `.text`.
- The ETag cache keeps the raw body, so a cleaning change applies to cached responses as well.

Alternatives:
- Cleaning in each storing service (analysis, storage, sync) misses fields and repeats itself;
  repository descriptions from search results were one such miss.
- A regex over JSON escapes before parsing breaks on `\\u0000` (an escaped backslash).
- Removing NUL instead of replacing it: NUL carries no meaning in text and is often a symptom of
  UTF-16 read as UTF-8, where replacing every second character with U+FFFD would be worse.

### D2. Identity check before a refresh without metadata (RS-1)

In `_fetch`, when `"metadata"` is not among the parts and there are other parts, the first step
is `_between_parts`, then `client.get_repository(name)` (with 404 caught). On the same GitHub
ID, the fetch continues under the stored name; a redirect to a new name answers with the same
ID, and the other requests follow the redirect as today. On another ID or a 404, `_fetch` takes
the metadata path (`_metadata(repo)`, which asks for the name again from the ETag cache and then
by ID), then languages, then the other parts under `out.metadata.full_name`. A 404 by ID raises
`GitHubNotFound` → FAILED `not_found`, as a metadata refresh does.

`run` computes `fetched_name` after the fetch: `None` when `fetched.metadata` is set, else the
stored name. `hold` keeps its check for our own database renames.

Alternatives:
- Always fetch metadata on every refresh: two requests (metadata and languages) per refresh,
  and it rewrites `synced_at`, which changes what "only stale parts" means.
- Compare an ID from the fetched payloads: issue and README payloads carry no repository ID.

Cost: one extra conditional request per refresh without metadata. After the first fetch it is
usually a 304.

### D3. Broker refusal in `queue_released` (RS-3)

`send` tries `sync_repository.delay(pk)` for every picked pk, collects the pks whose send
raised, logs once (`logger.warning`, count only), and calls `unmark_queued(failed)` (autocommit
after the commit). It is registered with `transaction.on_commit(send, robust=True)`, so an
unexpected error inside `send` is logged, never raised into the caller. This is the same shape
as `process_repository_backlog` and `queue_revocation`.

### D4. Wall clock for re-check transitions (RS-5)

`recheck_eligibility(ids, *, now)` keeps `now` for the eligibility rules (the run's reference
time, so one run judges consistently) and stamps `lifecycle_changed_at = timezone.now()`, taken
once per call. The analysis' `*_synced_at = now` (job time) is left alone: `complete` already
stamps the transition with the wall clock, and freshness reads it (`pool_changed`).

### D5. Case-insensitive release (RS-6) with an index

`release_name` filters `full_name__iexact=full_name`. Django renders this as
`UPPER("full_name"::text) = UPPER(%s)`, which the existing unique index can't serve, and every
search upsert runs it. A new index `repository_full_name_upper_idx` on `Upper("full_name")`
(migration `repositories.0010`, index only, no data change) serves it. The contributions code's
`full_name__iexact` lookups benefit from it as well.

### D6. Lock order and outcome (RS-10, RS-7)

- `release_name` reads the holders with `select_for_update().order_by("github_id")` before the
  four updates. The deadlock in which two repositories swap names stays possible (each caller
  already holds its own row), and PostgreSQL aborts one side, which is then retried.
- `lifecycle.fail` returns whether it updated a row. `run` returns `Outcome.SKIPPED` when it did
  not, logged as for a lost claim.

### D7. Entry labels (RS-8)

`_store` computes `categories = {labels.category(name) for name in f.labels or []}`, then
`has_good_first_issue_label = labels.GOOD_FIRST_ISSUE in categories` and the same for
`HELP_WANTED`. `normalize_label`, `GOOD_FIRST_ISSUE` and `HELP_WANTED` in `analysis.py` are
removed (`__all__` too). The benchmark datasets store the flags, so `evaluate_ranking` must
report the same numbers as `baselines.json` (no `--write-baseline`).

### D8. `mark_stale` (RS-9)

`candidates.only("pk", "lifecycle", "full_name", "activity_synced_at", *PART_FIELDS.values())`.
These are the fields `stale_parts` reads (`activity_synced_at` is also a part field). Rows are
grouped as `{(lifecycle, tuple(parts)): [pk, ...]}`, then one
`filter(pk__in=pks, lifecycle=lifecycle).update(...)` per group, summing the counts. The
`lifecycle` filter keeps the guard against a row that changed meanwhile.

## Risks / Trade-offs

- [Cleaning changes stored text that a user might compare with GitHub] → only NUL and
  unpaired surrogates change, and neither renders.
- [The identity check adds a request to every partial refresh] → conditional and usually a 304.
  The background refresh's batch size bounds the total.
- [RS-8 changes stored flags, and so rankings, on the next community refresh (weekly)] → the
  intended correction. The benchmark cannot move; recommendations regenerate through freshness
  when the data changes.
- [Index build on a large `repositories_repository`] → a plain `CREATE INDEX` on a table of
  thousands of rows takes milliseconds; no `CONCURRENTLY` needed at this size.

## Migration Plan

Deploy normally: `repositories.0010` adds one index. Cleaned text and corrected flags arrive with
each repository's next fetch of that part. Rollback: revert the code and migrate
`repositories` back to `0009`.
