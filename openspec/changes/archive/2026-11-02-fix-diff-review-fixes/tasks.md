## 1. Fixes (made before commit, in the 0.12.45–0.12.47 working tree)

- [x] 1.1 FD-1: `revoke_later` caps a `GitHubRateLimited` wait at `GITHUB_MAX_RETRY_DELAY` before `decide_retry` (D1); docstrings name `GitHubRateLimited`; test: a reset an hour away is retried with countdown ≈ the cap
- [x] 1.2 FD-8: `error_for_response(..., method="GET")`, revocation passes `DELETE` (D2)
- [x] 1.3 FD-10: `running_sync_job` test helper (D3)

## 2. Checks

- [x] 2.1 Backend `uv run pytest` (1722), `ruff check`, `ruff format --check`, `mypy`; no frontend or e2e change

## 3. Release

- [x] 3.1 Archive (delta into `github-authentication`); `Bug_Backlog.md` batch 35 already records FD-1…FD-10
- [x] 3.2 Release notes: part of 0.12.45 (CHANGELOG already lists FD-1, FD-8); no version bump of its own; commit only when the owner says so
