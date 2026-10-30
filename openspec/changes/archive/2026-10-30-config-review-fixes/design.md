## Context

Batch 26 of `Bug_Backlog.md` (CFG-1…CFG-10), from the review sweep of `apps/backend/config/`.
All fixes are settings-level or in the error handler; no model, API or spec change.

## Decisions

### D1. Test settings take only the local database from `.env` (CFG-1)

`test.py` sets `DJANGO_READ_DOTENV=DATABASE_URL`; `base.py` then parses the repo-root `.env` with
django-environ's own parser into a separate mapping (`_DotenvValues`, not `os.environ`) and
passes on only `DATABASE_URL`. `REDIS_URL`, `NUM_PROXIES`, `DISCOVERY_*` and the rest come from
defaults, as in CI. The value is compared trimmed and case-insensitively; `0` still turns reading off (e2e), any
other value keeps reading it all;
an explicit `DATABASE_URL` in the environment wins.

### D2. JSON settings name themselves (CFG-4)

`env_json(name, default)` turns invalid JSON into `ImproperlyConfigured` naming the setting
(also used by `DISCOVERY_STAR_BANDS`, `DISCOVERY_EXCLUDED_TOPICS`). `env_mapping(name, defaults)`
builds on it: missing → defaults; a JSON object → merged over
the defaults; anything else (list, string, invalid JSON) → `ImproperlyConfigured("<name> must be
a JSON object ...")`. The system checks (`core.E0xx`) still validate the merged values.

### D3. Broker timeouts (CFG-2, CFG-5)

`socket_timeout` uses `REDIS_SOCKET_TIMEOUT`, like the cache, but never below 2 s: workers block
on BRPOP for kombu's 1 s `brpop_timeout`. `visibility_timeout` is
`max(3600, 2 * GITHUB_MAX_RETRY_DELAY)`: kombu's default, raised only when the retry delay is
configured above half an hour. A task running longer than that is still redelivered; claim
fencing cancels the copy (accepted).

### D4. Error envelope (CFG-6)

A dict detail (not a `ValidationError`) keeps `exc.default_detail` as the message and goes to
`details` (an object, as documented). A list detail becomes the message, items joined.

### D5. Scopes (CFG-10)

`env_words(name)` (beside `env_list`) splits on commas and whitespace, empty items dropped;
`GITHUB_OAUTH_SCOPES` uses it and the authorize URL still joins them with spaces.

## Risks / Trade-offs

- A local `.env` that relied on overriding test settings no longer does; that is the point.
- `CONN_HEALTH_CHECKS` adds one cheap check per request on a reused connection.
