## 1. Fixes

- [x] 1.1 CFG-1: `test.py` sets `DJANGO_READ_DOTENV=DATABASE_URL`; `base.py` takes only that key from `.env`
- [x] 1.2 CFG-2, CFG-5: broker `socket_timeout`; `visibility_timeout` above `GITHUB_MAX_RETRY_DELAY`
- [x] 1.3 CFG-3: `CONN_HEALTH_CHECKS = True`
- [x] 1.4 CFG-4: `env_mapping(name, defaults)` for the eight JSON object settings
- [x] 1.5 CFG-6: dict/list detail → default message plus `details`
- [x] 1.6 CFG-9, CFG-10: `LOG_LEVEL` for `django`; scopes split on commas and spaces (`env_words`). CFG-8 tried and reverted (accepted: the production-settings tests set `REDIS_URL` after `base` is imported)

## 2. Tests and checks

- [x] 2.1 Tests: `env_mapping` (object merges, list and invalid JSON raise naming the setting), error envelope for a dict detail, scopes parsing, test settings not reading `.env`
- [x] 2.2 `uv run pytest`, `ruff check`, `ruff format --check`, `mypy`

## 3. Release

- [x] 3.1a `/simplify` on the fix diff: `.env` parsing moved into `base.py` (django-environ's parser), `env_json` for the remaining JSON settings, broker options in one place, tautological tests removed
- [x] 3.1b `/code-review` on the fix diff (workflow step 7): CFG-11…CFG-20, fixed or accepted before commit
- [x] 3.2 Archive (`skip_specs`); `Bug_Backlog.md` batch 26 rows marked fixed
- [x] 3.3 Release housekeeping (CLAUDE.md §8)
