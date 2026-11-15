## 1. Compose

- [x] 1.1 ROOT-1, ROOT-2, ROOT-3: loopback ports for backend and frontend; no Redis `ports` (D1).
- [x] 1.2 ROOT-8: drop `DJANGO_SETTINGS_MODULE` from compose `environment` (D2).
- [x] 1.3 ROOT-9: Postgres credentials once; healthcheck from the container env (D5).
- [x] 1.4 ROOT-4, ROOT-5: `VITE_WATCH_POLLING` in compose and `vite.config.ts`; README rebuild note (D4).
- [x] 1.5 `docker compose config` parses; manual `docker compose up --build` if Docker is available (owner; otherwise noted as not run). Not run: Docker is not installed here; the file parses as YAML (anchors and merge keys resolved; checked with PyYAML).

## 2. Settings and template

- [x] 2.1 ROOT-6: `development.py` honors `DJANGO_DEBUG` (default true) (D2). Test: `override` env false → `DEBUG` false under development settings.
- [x] 2.2 ROOT-7: add the 17 settings to `.env.example`; `tests/test_env_example.py` (D3). The test fails before the template change. As built: the test also found `GITHUB_OAUTH_REDIRECT_URI` and `EXPERIENCE_THRESHOLDS` (helpers the review missed), so 19 settings added.

## 3. Root package

- [x] 3.1 ROOT-10: `format:scripts:write`, `engines.node >=22` (D5); `npm run check:version`, `npm run test:scripts`, `npm run lint:scripts`, `npm run format:scripts` pass.

## 4. Checks

- [x] 4.1 Backend: `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`, `uv run mypy .`.
- [x] 4.2 Frontend: `npm run typecheck`, `npm run lint`, `npm run build` (Vite config). No e2e (no browser flow change).

## 5. Release

- [x] 5.1 `Bug_Backlog.md` batch 70: ROOT rows marked fixed; sweep table complete.
- [x] 5.2 `/simplify`, then `/code-review` on the fix diff: skipped by the owner.
- [x] 5.3 Archive (ADDED requirement in `developer-tooling`). Release housekeeping per CLAUDE.md §8 (README Docker section). Commit only when the owner says so.
