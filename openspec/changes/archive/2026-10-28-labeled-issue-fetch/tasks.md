## 1. Setting and check

- [x] 1.1 `config/settings/base.py`: `ISSUES_ENTRY_LABELS = env.list(..., default=["good first issue",
  "help wanted"])` with a comment; `.env.example` entry (commented, like `ISSUES_MAX_PAGES`).
- [x] 1.2 `core/checks.py` `issue_config_check`: `core.E041` when not a list of non-empty
  strings or a label repeats (case-insensitive). Tests in the checks test file (`checks_helpers.ids`).

## 2. Client

- [x] 2.1 `GitHubClient.list_open_issues(full_name, *, label=None)`: with a label, adds
  `labels=<label>` and reads one page; docstring says why one request per label.
- [x] 2.2 Fixture tests: labeled URL and query (`respx`), pull requests dropped, 410 → empty.

## 3. Fetch and merge

- [x] 3.1 Pure `merge_issue_pages(recent, labeled)`: recent first, then unseen labeled issues by
  `github_id`; `truncated` from `recent`. Unit tests (overlap, order, truncated kept).
- [x] 3.2 `RepositoryAnalysisService._fetch` (`issues` part): recent listing, then one labeled
  listing per `ISSUES_ENTRY_LABELS` entry only when the recent one is truncated; merged
  result into `out.issues`. Tests register labeled routes directly (`respx`, before the generic one).
- [x] 3.3 Tests through the analysis: an old `good first issue` beyond the cap is stored;
  an issue in two listings is stored once; empty setting or an untruncated listing makes no
  labeled request; a 5xx on a
  labeled listing fails the part and keeps the stored issues.

## 4. Verification

- [x] 4.1 Backend `ruff check`, `ruff format --check`, `mypy`, `pytest`; `git diff --exit-code
  apps/backend/evaluation/baselines.json`.
- [x] 4.2 Measurement (design D6) on the local database, read-only: for each capped pooled
  repository, entry issues stored and those the labeled listings add; totals in the CHANGELOG
  entry. `relevant_issue_count` not measured (needs a real refresh and a regeneration).

## 5. Docs and release

- [x] 5.1 README (issue settings), CLAUDE.md §7 entry, `ideas.md` §7 moved to Shipped,
  `features.txt`, `CHANGELOG.md`.
- [x] 5.2 Release housekeeping (CLAUDE.md §8): patch version, lockfiles, `check:version`;
  archive the change.
