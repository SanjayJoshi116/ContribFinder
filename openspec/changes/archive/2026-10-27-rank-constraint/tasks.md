## 1. Constraints and migrations (D1, D2)

- [x] 1.1 `Meta.constraints`: `recommendation_rank_positive` on `Recommendation`,
  `recommended_issue_rank_positive` on `RecommendedIssue`, `feedback_rank_positive` (null or
  `>= 1`) on `RecommendationFeedback`.
- [x] 1.2 Migrations `recommendations.0005`, `issues.0002`, `feedback.0005`: `RunPython(repair,
  noop)` on the historical models (shift a group with a rank 0 up by one; event rank 0 → null),
  then `AddConstraint`. `makemigrations --check` clean afterwards.

## 2. Tests

- [x] 2.1 Each constraint refuses rank 0 (`IntegrityError`); an event with rank null is stored.
- [x] 2.2 Repair functions: ranks 0, 1, 2 become 1, 2, 3 for that developer only (another
  developer's ranks unchanged), matched issues likewise per recommendation, event rank 0 → null,
  no row deleted; the migrations round trip (back before and forward again).
- [x] 2.3 Existing generation and feedback tests pass unchanged (they write ranks from 1).

## 3. Verification and housekeeping

- [x] 3.1 Backend `ruff check`, `ruff format --check`, `mypy`, `pytest`; `git diff --exit-code
  apps/backend/evaluation/baselines.json`; `npm run api:sync` shows no schema change.
- [x] 3.2 Apply the migrations to the dev database (`npm run manage -- migrate`) and confirm the
  constraints exist (`\d` or `pg_constraint`).
- [x] 3.3 Docs: `Bug_Backlog.md` T-12 fixed (open items, "Next", release table); CLAUDE.md §7
  shipped entry (K-1 carry-over unchanged); `features.txt` (planned line removed).
- [x] 3.4 Release housekeeping (CLAUDE.md §8): patch 0.12.29; `CHANGELOG.md`, README status line,
  lockfiles, `check:version`.
