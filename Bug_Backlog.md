# Bug Backlog

Findings from the codebase sweep on 2026-10-19 (v0.12.0, `main` @ 50acbb8) and the reviews of
each fix release since; current through 0.12.75. Order: the full review sweep (top priority),
open items and known gaps, the release index, the fix-batch plan
(nearly all shipped), the totals, then the review history (oldest first) with every row as
verified.
Status: `open` · `confirmed` / `partial` (verified, not fixed) · `fixed in part` · `fixed` ·
`accepted` / `wontfix` · `false-positive`.

## Full review sweep (top priority)

Added 2026-10-30 (after v0.12.38), before the repository goes public: `/code-review` and
`/security-review` over every module, high priority first. Tick each column when its review has
run and its findings are recorded below as a new batch (verified rows, as in the 2026-10-19
sweep); fixes go on one branch (e.g. `review/full-sweep`). Skipped: migrations, `tests/` (review
with its module), generated `src/api/openapi.json` and `schema.d.ts`, empty `services/ai/`.
`/code-review` takes a path (`/code-review high apps/backend/services/github`); `/security-review`
reviews the branch's pending changes, so point it at the module explicitly (or diff against an
empty base).

### Workflow (reference)

review → security → verify → propose → apply → simplify → review → archive. Steps 1–3 run per
module; steps 4–8 once per priority group (high, then medium, then low).

1. **Review**: `/code-review high <module path>`. Findings only; no fixes yet.
2. **Security**: `/security-review` on the same module, named explicitly (its default is the
   branch diff). High-confidence findings only.
3. **Verify**: check every finding against the code; record a batch here (`<PREFIX>-n` rows,
   verdict `confirmed` / `partial` / `accepted` / `false-positive`, with the fix in brief);
   tick both boxes in the table (`[x] batch N`, or `[x] no findings`). Then the next module.
4. **Propose**: when the group is done, `/opsx:propose` one OpenSpec change for the group's fix
   batch: which rows are fixed, which are accepted and why. Rows that change specified behavior
   get spec deltas; pure code fixes use `skip_specs` (as `json-report-writer`).
5. **Apply**: `/opsx:apply` on one branch (e.g. `review/full-sweep`): fix, add a test per fix,
   then backend `pytest`, `ruff`, `mypy`; frontend `test`, `lint`, `typecheck`, `format:check`,
   `build`; e2e only when browser flows change.
6. **Simplify**: `/simplify` on the fix diff; apply or note skips.
7. **Review**: `/code-review` with no path (reviews the uncommitted fix diff, not the whole
   module); verify and record as the next batch, fix before commit (as batches 23–25).
8. **Archive**: `/opsx:archive`, release housekeeping (CLAUDE.md §8: patch bump, CHANGELOG,
   features.txt, README, CLAUDE.md entry), tick the batch here as fixed, commit.

Why this order: modules share code, so fixing after each one touches the same files repeatedly;
a full re-review after fixing mostly repeats recorded rows, so step 7 reviews only the change;
`/simplify` comes after the fixes so it cleans final code.

| Priority | Module | Contents | code-review | security-review |
|---|---|---|---|---|
| High | `apps/backend/config/` | settings, urls, celery, error envelope | [x] batch 26 | [x] no findings |
| High | `apps/backend/core/` | health, auth class, JSON errors, log redaction, checks, throttling, CSP | [x] batch 27 | [x] no findings |
| High | `apps/backend/accounts/` | User, AuditEvent, auth views, session, account deletion | [x] batch 28 | [x] no findings |
| High | `apps/backend/github/` | GitHubAccount/Profile, sync task, profile API | [x] batch 29 | [x] no findings |
| High | `apps/backend/e2e/` | seed command; must stay out of production | [x] batch 30 | [x] no findings |
| High | `apps/backend/services/*.py` | crypto, audit, jobs, job_guard, locks, feedback, data_deletion, data_versions | [x] batch 31 | [x] no findings |
| High | `apps/backend/services/github/` | OAuth, GitHubClient, sync, storage | [x] batch 32 | [x] no findings |
| High | `apps/frontend/src/api/` | client.ts, types.ts (skip generated openapi.json, schema.d.ts) | [x] batch 33 | [x] no findings |
| High | `apps/frontend/src/features/auth/` | sign-in, route guard | [x] batch 34 | [x] no findings |
| Medium | `apps/backend/jobs/` | SyncJob, status and versions API, recovery | [x] batch 36 | [x] no findings |
| Medium | `apps/backend/developers/` | profile, skills, interests; profile API | [x] batch 37 | [x] no findings |
| Medium | `apps/backend/repositories/` | repository models, discovery API, tasks, reports | [x] batch 38 | [x] no findings |
| Medium | `apps/backend/issues/` | Issue, RecommendedIssue, issue detail API | [x] batch 40 | [x] no findings |
| Medium | `apps/backend/recommendations/` | ScoringConfig, Recommendation, API, evaluation commands | [x] batch 41 | [x] no findings |
| Medium | `apps/backend/feedback/` | feedback, saved, dismissed; keyset pages | [x] batch 42 | [x] no findings |
| Medium | `apps/backend/services/profiling/` | taxonomy, manifest and README parsing (untrusted input) | [x] batch 43 | [x] no findings |
| Medium | `apps/frontend/src/app/` | query client, 401 handling, job transitions, data versions | [x] batch 44 | [x] no findings |
| Medium | `apps/frontend/src/routes/` | routes, AppShell, landing, privacy, RouteId | [x] batch 45 | [x] no findings |
| Medium | `apps/frontend/src/features/issues/` | issue detail (untrusted issue bodies) | [x] batch 46 | [x] no findings |
| Medium | `apps/frontend/e2e/ + vite.config.ts, csp.config.ts, playwright.config.ts` | Playwright, CSP, proxy | [x] batch 47 | [x] no findings |
| Medium | `scripts/` | npm runners, process trees, WSL Redis, dependency audit | [x] batch 48 | [x] no findings |
| Medium | `.github/workflows/` | ci.yml, audit.yml (token permissions) | [x] batch 49 | [x] no findings |
| Low | `apps/backend/services/repositories/` | analysis, lifecycle, staleness, backlog, setup | [x] batch 56 | [x] no findings |
| Low | `apps/backend/services/issues/` | labels, classification, technologies | [x] batch 57 | [x] no findings |
| Low | `apps/backend/services/discovery/` | queries, filters, ordering, yield report | [x] batch 59 | [x] no findings |
| Low | `apps/backend/services/matching/` | activity, technologies, features, signals | [x] batch 60 | [x] no findings |
| Low | `apps/backend/services/ranking/` | config, pipeline, score, explain, freshness, activation | [x] batch 63 | [x] no findings |
| Low | `apps/backend/services/evaluation/` | benchmark, metrics, bootstrap, feedback report (offline) | [x] batch 64 | [x] no findings |
| Low | `apps/frontend/src/features/recommendations/` | list, cards, detail, filters | [x] batch 65 | [x] no findings |
| Low | `apps/frontend/src/features/feedback/` | save/dismiss, saved and hidden lists | [x] batch 66 | [x] no findings |
| Low | `apps/frontend/src/features/profile/` | profile, skills | [x] batch 67 | [x] no findings |
| Low | `apps/frontend/src/features/sync/ + discovery/` | onboarding progress | [x] batch 68 | [x] no findings |
| Low | `apps/frontend/src/components/ + src/lib/` | DeadEnd, utilities | [x] batch 69 | [x] no findings |
| Low | `docker-compose.yml, .env.example, package.json` | root config | [x] batch 70 | [x] no findings |

## Open items

The full review sweep above: started 2026-10-30; `config/`, `core/` and `accounts/` reviewed and
fixed (batches 26–28; no security findings); `github/`, `e2e/`, `services/*.py` and `services/github/`
reviewed and fixed (batches 29–32; no security findings); `frontend/src/api/` reviewed and fixed (batch 33;
no security findings); `frontend/src/features/auth/` reviewed and fixed (batch 34; no security
findings); the medium group (`jobs/` … `.github/workflows/`) reviewed as batches 36–49 (no security
findings), batches 36–49 fixed in 0.12.48–0.12.60 (the medium group done); low group started 2026-11-12:
`services/repositories/` reviewed as batch 56 (no security findings), fixed in 0.12.62;
`services/issues/` reviewed as batch 57 (no security findings), fixed in 0.12.63;
`services/discovery/` reviewed as batch 59 (no security findings), fixed in 0.12.64;
`services/matching/` reviewed as batch 60 (no security findings), fixed in 0.12.65; the rest of the
low group reviewed as batches 63–70 (no security findings) and fixed in 0.12.66–0.12.74. The full
review sweep is complete (2026-11-15). Fix-diff review of 0.12.70–0.12.74: batch 72, fixed in
0.12.75.
Batches 44–46 (0.12.55–0.12.57): one `/simplify` (batch 51; SIM2-9…SIM2-12 skipped, SIM2-9 then
fixed as CR-1) and one fix-diff `/code-review` (batch 52, all fixed) over their combined diff.
Batches 26–34 fixed in
0.12.39–0.12.47 (CFG-7, CFG-8, ACC-4, GH-6, SEED-13, SEED-14, SEED-18 and SVC-13…SVC-15,
SVC-17…SVC-19 accepted; batches 32–34: one `/simplify` and one fix-diff `/code-review` over their combined diff, batch 35).
SVC-16 (per-user ETag cache generation, the root fix for SVC-6) fixed in 0.12.76, with batches 73 (`/simplify`) and 74 (fix-diff `/code-review`). Open: PUB-3 (batch 55: the
repository's GitHub settings before it goes public; owner only). Open rows: RT-3, RT-4, RT-5 (batch 24, design-level; renamed from R-3…R-5, which clashed with the
2026-10-19 "R" rows).
Earlier: P-1 accepted; B-6, D-11 and T-11 fixed in 0.12.32; batches 21–23, 25 fixed or closed in
their releases. Known gaps (K) are in the next section. Ranking-visible fixes must win on the selection benchmark and not regress on
a fresh holdout; they no longer wait for K-1 (since 2026-10-28).

## Known gaps (already tracked elsewhere)

| ID | Item | Source | Status |
|---|---|---|---|
| K-1 | Judge `real-a-v2`, build `benchmark-v2`, evaluate v1/v2 (all/persona/real), `--write-baseline`. Optional since 2026-10-28 (owner decision): no longer blocks ranking changes, which are judged on the selection benchmark (`benchmark-v1` until `benchmark-v2` exists) and a fresh holdout. | features.txt:664, CLAUDE.md §7 | open (optional) |
| K-2 | Docker Compose verification from a fresh `.env` (no Docker on dev machine). | features.txt:663 | open |
| K-3 | Issue-level evaluation (benchmark covers repositories only). | features.txt:673 | open |
| K-4 | Docs-style repositories with a code language and no list topic (`system-design-primer`, `developer-roadmap`) pass `not_code`. Since 0.12.7 a suspected list (`awesome-*`, list topic) that declares manifest dependencies (lint or site tooling) passes too. | CHANGELOG 0.12.0, 0.12.7 | open (known limit; `ideas.md` §11) |
| K-5 | Active config v2 is not an improvement over v1 on `benchmark-v1` (NDCG@10 +0.0195, P@5 −0.0333). | CLAUDE.md Phase 8b | open (a later config must win on `benchmark-v1`) |

## Fixed by release

Index only: each row's Status column (in its history section) is the record, and this table
must match it. Newest first. Counts are fixed rows.

| Version | Change | Fixed | In part, accepted or wontfix |
|---|---|---|---|
| 0.12.35 | `labeled-issue-fetch` (with its review) | 5: N-1, N-2, N-3, N-8, N-9 | N-4…N-7 accepted; N-10 accepted |
| 0.12.34 | `dependency-scanning` (with its review) | 6: M-1, M-2, M-3, M-9, M-10, M-11 | M-4, M-5, M-6, M-12…M-15 accepted; M-7, M-8 wontfix |
| 0.12.33 | `json-report-writer` | 1: T-14 | — |
| 0.12.32 | (no OpenSpec change) | 3: B-6, D-11, T-11 | P-1 accepted |
| 0.12.31 | `data-versions-fixes` | 6: U-1, U-2, U-3, U-5, U-6, U-7 | U-4 accepted, U-8 wontfix |
| 0.12.29 | `rank-constraint` | 1: T-12 | — |
| 0.12.27 | `data-versions` | 1: Y-6 | S-8 narrowed |
| 0.12.26 | `post-analysis-pool-cleanup` | 1: X-9 | — |
| 0.12.23 | `dismiss-reasons` (with its review) | 10: T-1, T-2, T-3, T-4, T-5, T-6, T-7, T-8, T-9, T-10 | T-13 wontfix; T-14 accepted (fixed in 0.12.33) |
| 0.12.18 | `activation-command-only` | 1: S-6 | — |
| 0.12.17 | `keyset-paging-links` | 1: S-7 | — |
| 0.12.16 | `signal-explanation-accuracy` | 6: D-8, D-9, D-15, D-16, D-17, D-18 | — |
| 0.12.15 | (no OpenSpec change) | 5: D-12, D-13, S-9, S-10, S-11 | S-7 reclassified (OpenSpec change) |
| 0.12.14 | (no OpenSpec change) | 9: B-14, B-15, B-16, D-7, S-1, S-2, S-3, S-4, S-5 | S-8 accepted |
| 0.12.13 | `config-activation-loose-ends` | 1: P-3 | Q-10 accepted; D-15 in part (activation validates) |
| 0.12.12 | `freshness-paging-seed` | 2: Y-7, Z-1 | Y-6 in part |
| 0.12.11 | `tooling-data-hygiene` | 5: P-2, P-4, P-5, Q-11, Q-12 | P-1 in part (restart; cause unknown; accepted 2026-10-28), Q-10 in part |
| 0.12.10 | `performance-cleanup` | 30: DOC-1, DOC-2, A-16, A-17, A-20, B-17, B-20, C-20, C-21, C-23, D-19, D-20, D-21, E-10, X-11, X-12, Y-9, Y-10, Z-4, Z-5, Z-8, Z-9, Z-10, Q-1, Q-2, Q-4, Q-5, Q-7, Q-8, Q-9 | A-18 wontfix; Q-3, Q-6 accepted |
| 0.12.9 | `dev-scripts-checks` | 17: G-1, G-2, G-3, G-4, G-7, G-8, G-9, G-10, H-7, H-10, H-11, H-19, H-20, Z-2, Z-3, Z-6, Z-7 | — |
| 0.12.8 | `frontend-correctness` | 17: F-1, F-2, F-3, F-5, F-6, F-7, F-8, F-9, H-5, H-17, H-18, Y-1, Y-2, Y-3, Y-4, Y-5, Y-8 | — |
| 0.12.7 | `discovery-repository-data` | 26: R-3, R-4, R-5, R-6, R-9, R-10, R-11, R-12, C-2, C-5, C-7, C-8, C-11, C-12, C-13, C-14, C-15, C-16, C-17, C-18, X-1, X-2, X-3, X-4, X-5, X-6 | X-7, X-8 wontfix (X-9 fixed in 0.12.26); X-10 false positive |
| 0.12.6 | `recommendation-consistency` | 23: D-1, D-2, D-3, D-4, D-5, D-6, D-10, D-14, E-4, E-5, E-6, E-7, F-4, W-1, W-2, W-3, W-4, W-5, W-6, W-7, W-8, W-9, W-10 | — |
| 0.12.5 | `github-error-resilience` | 21: A-2, A-3, A-4, A-5, A-6, A-11, A-13, A-14, B-13, C-1, C-6, C-9, H-1, V-1, V-2, V-3, V-4, V-5, V-6, V-7, V-9 | V-8 wontfix |
| 0.12.4 | `job-claim-fencing` | 17: B-1, B-2, B-3, B-5, B-7, B-8, B-9, B-10, B-11, B-12, B-18, B-19, C-3, C-4, C-10, C-19, C-22 | — |
| 0.12.3 | `evaluation-tooling-integrity` | 10: R-1, R-2, R-7, R-8, R-13, R-14, E-1, E-2, E-8, E-9 | — |
| 0.12.2 | `privacy-deletion-finality` | 10: A-1, A-7, A-8, A-9, A-12, A-19, B-4, E-3, H-8, H-9 | — |
| 0.12.1 | `security-hardening` | 12: A-15, G-5, G-6, H-2, H-3, H-4, H-6, H-12, H-13, H-14, H-15, H-16 | — |

Total fixed: 239. Never in a release: A-10 (false positive, in no batch).

## Fix batches

Each batch fits one OpenSpec change. Numbered in the order planned on 2026-10-19 (12–19 added by
later reviews). Every verified row is in exactly one batch (A-10 dropped). All shipped
(batches 8 and 19 finished in 0.12.32, batch 21 in 0.12.34, batch 22 in 0.12.35).

| # | Batch | Rows | Why together |
|---|---|---|---|
| 1 | **Security hardening** | H-2, H-4, H-3, H-12, H-15, H-16, H-6, H-13, H-14, G-5, G-6, A-15 | Spoofable throttle IP, secrets in logs, settings drift between tiers, deploy defaults. Small, isolated, high value. |
| 2 | **Privacy and deletion finality** | A-1, B-4, A-7, A-8, A-9, A-12, H-8, H-9, E-3, A-19 | "Delete" must mean deleted: running work re-checks before writing; identity leftovers; privacy page matches reality; export anonymization. **E-3 before committing benchmark-v2.** |
| 3 | **Evaluation tooling** | R-1, R-2, E-1, E-2, R-7, R-8, R-13, R-14, E-8, E-9 | `--write-baseline` and sheet import must be trustworthy before K-1 (judging real-a-v2). Offline only, low risk. |
| 4 | **Job lifecycle and claim fencing** | B-1, B-2, B-3, B-5, B-7, B-8, B-9, B-10, B-11, B-12, B-18, B-19, C-3, C-4, C-10, C-19 | One claim-token mechanism for jobs and repositories; zombie PENDING jobs (B-1); one `_start_job` helper; ordered catalog upsert. |
| 5 | **GitHub error handling and resilience** | A-2, A-3, A-4, A-5, A-6, A-11, A-13, A-14, B-13, C-1, C-6, C-9, H-1 | Classify 301, secondary 403, 451 and decryption errors correctly; one bad repository or manifest never fails a whole job; a Redis outage never breaks reads. |
| 6 | **Recommendation consistency** | D-1, D-2, D-3, D-4, D-5, D-6, D-10, D-14, E-4, E-5, E-6, E-7, F-4 | Stale ≠ gone; one lock order and one dismissal check for save, dismiss and persist; freshness sees restores and new candidates. |
| 7 | **Discovery and repository data** | C-2, C-5, C-7, C-8, C-11, C-12, C-13, C-14, C-15, C-16, C-17, C-18, R-3, R-4, R-5, R-6, R-9, R-10, R-11, R-12 | Eligibility re-check via lifecycle, provenance pruning, not_code false positives, search upsert side effects, one shared ordering helper. |
| 8 | **Signal and explanation accuracy** | B-6, B-14, B-15, B-16, D-7, D-8, D-9, D-11, D-12, D-13, D-15, D-16, D-17, D-18 | Wrong experience level, missed README badges, misclassified issues, reasons not backed by scoring. Ranking-visible: evaluate on the benchmark. B-14, B-15, B-16, D-7 shipped in 0.12.14, D-12, D-13 in 0.12.15 (no spec change; baselines unchanged), D-8, D-9, D-15, D-16, D-17, D-18 in 0.12.16 (`signal-explanation-accuracy`; baselines unchanged). B-6 and D-11 fixed in 0.12.32. |
| 9 | **Frontend correctness** | F-1, F-2, F-3, F-5, F-6, F-7, F-8, F-9, H-5, H-17, H-18 | Query invalidation churn, no 4xx retry, pagination gaps, 401 handling; add Playwright for the main flows. |
| 10 | **Dev scripts, checks and migrations** | G-1, G-2, G-3, G-4, G-7, G-8, G-9, G-10, H-7, H-10, H-11, H-19, H-20 | `npm run stop` kills only this repo; config checks for unchecked settings; safe seed migrations; tests for those paths. |
| 11 | **Performance and cleanup** | A-16, A-17, A-18, A-20, B-17, B-20, C-20, C-21, C-22, C-23, D-19, D-20, D-21, E-10, DOC-1, DOC-2, X-11, X-12, Y-9, Y-10, Z-4, Z-5, Z-8, Z-9, Z-10 | No behavior change; do alongside nearby batches or as one sweep. C-22 already fixed in batch 4. |
| 12 | **Batch 5 follow-ups** | V-1, V-2, V-3, V-4, V-5, V-6, V-7, V-8, V-9 | Review of `github-error-resilience`. Fixed in the same release (0.12.5); V-1 and V-3 replace design decisions D7 (client raises `GitHubInvalidResponse`) and D9 (in-memory throttle fallback instead of fail-open). |
| 13 | **Batch 7 follow-ups** | X-1…X-10 | Review of `discovery-repository-data`. X-1…X-6 fixed in the same release (0.12.7); X-7, X-8 accepted, X-9 fixed in 0.12.26, X-10 false positive. X-11 and X-12 went to batch 11. |
| 14 | **Batch 9 follow-ups** | Y-1…Y-10 | Review of `frontend-correctness`. Y-1…Y-5 and Y-8 fixed in the same release (0.12.8); Y-6 (in part) and Y-7 fixed in 0.12.12 (`freshness-paging-seed`), the rest of Y-6 in 0.12.27 (`data-versions`); Y-9 and Y-10 went to batch 11. |
| 15 | **Batch 10 follow-ups** | Z-1…Z-10 | Review and `/simplify` pass of `dev-scripts-checks`. Z-2, Z-3, Z-6, Z-7 fixed in the same release (0.12.9); Z-1 fixed in 0.12.12 (spec change, `freshness-paging-seed`); Z-4, Z-5, Z-8, Z-9, Z-10 went to batch 11. |
| 16 | **Batch 11 follow-ups** | P-1…P-5 | Found while implementing `performance-cleanup` (0.12.10). Shipped with Q-10…Q-12 in 0.12.11 (`tooling-data-hygiene`): P-2, P-4, P-5 fixed, P-1 fixed in part (restart; cause unknown; accepted 2026-10-28), P-3 open (not reproduced; fixed in 0.12.13). |
| 17 | **Batch 11 review** | Q-1…Q-12 | Review and `/simplify` pass of `performance-cleanup`. Q-1, Q-2, Q-4, Q-5, Q-7, Q-8, Q-9 fixed in the same release (0.12.10); Q-3, Q-6 accepted; Q-10…Q-12 went to batch 16 (0.12.11; Q-10 in part). |
| 18 | **0.12.13/0.12.14 review** | S-1…S-11 | Review and `/simplify` pass of `config-activation-loose-ends` and the batch 8 fixes. S-1…S-5 fixed in 0.12.14 before commit, S-9…S-11 in 0.12.15, S-7 in 0.12.17 (`keyset-paging-links`), S-6 in 0.12.18 (`activation-command-only`); S-8 accepted, narrowed in 0.12.27 (`data-versions`). |
| 19 | **0.12.23 review** | T-1…T-14 | `code-review` and `/simplify` pass of the uncommitted 0.12.14–0.12.23 work. T-1…T-10 fixed in 0.12.23 before commit; T-11 fixed in 0.12.32, T-12 fixed in 0.12.29 (`rank-constraint`), T-13 wontfix, T-14 fixed in 0.12.33 (`json-report-writer`). The security review found nothing. |
| 20 | **0.12.24–0.12.30 review** | U-1…U-8 | `code-review` of the uncommitted 0.12.24–0.12.30 work. U-1, U-2, U-3, U-5, U-6, U-7 fixed in 0.12.31 (`data-versions-fixes`) before commit; U-4 accepted, U-8 wontfix. |
| 21 | **0.12.32–0.12.34 review** | M-1…M-15 | `code-review` (M-1…M-8) and `/simplify` (M-9…M-15) of the uncommitted 0.12.32–0.12.34 work. M-1, M-2, M-3, M-9, M-10, M-11 fixed in 0.12.34 before commit; the rest accepted or wontfix. |
| 22 | **0.12.35 review** | N-1…N-10 | `code-review` (N-1…N-7) and `/simplify` (N-8…N-10) of the uncommitted labeled-issue fetch. N-1, N-2, N-3, N-8, N-9 fixed in 0.12.35 before commit; the rest accepted. |
| 23 | **Released-name refresh review** | L-1…L-7 | `code-review` of the uncommitted `released-name-refresh` (plus 0.12.35). L-5 fixed in 0.12.35, L-1, L-2, L-4 in 0.12.36 before commit; L-3, L-6, L-7 accepted. |
| 24 | **Route-id validation review** | RT-1…RT-6 | `code-review` of the uncommitted `route-id-validation` (0.12.37). RT-1, RT-2, RT-6 fixed in 0.12.37 before commit; RT-3, RT-4, RT-5 open. |
| 25 | **E2E production-build review** | E2E-1…E2E-13 | `code-review` (E2E-1…E2E-9) and `/simplify` (E2E-10…E2E-13) of the uncommitted `e2e-production-build` (0.12.38). E2E-1, E2E-2, E2E-5, E2E-7, E2E-10…E2E-12 fixed in 0.12.38 before commit, E2E-6 documented; E2E-3, E2E-4, E2E-8, E2E-9, E2E-13 accepted. |
| 26 | **Sweep: `config/`** | CFG-1…CFG-20 | Full review sweep, 2026-10-30: `/code-review` (high) of `apps/backend/config/`, verified, fixed in 0.12.39 (`config-review-fixes`) except CFG-7, CFG-8 (accepted); its fix-diff review CFG-11…CFG-20 fixed; `/security-review` of the module found nothing. |
| 27 | **Sweep: `core/`** | CORE-1…CORE-10 | Full review sweep, 2026-10-30: `/code-review` (high) of `apps/backend/core/`, verified; fixed in 0.12.40 (`core-review-fixes`). `/security-review` of the module found nothing. |
| 28 | **Sweep: `accounts/`** | ACC-1…ACC-20 | Full review sweep, 2026-10-30: `/code-review` (high) of `apps/backend/accounts/`, verified; fixed in 0.12.41 (`accounts-review-fixes`), ACC-4 accepted; its fix-diff review ACC-11…ACC-20 fixed before commit (ACC-17 in part). `/security-review` of the module found nothing. |
| 29 | **Sweep: `github/`** | GH-1…GH-8 | Full review sweep, 2026-10-30: `/code-review` (high) of `apps/backend/github/`, verified; fixed in 0.12.42 (`github-review-fixes`), GH-6 accepted; its fix-diff review GH-9…GH-15 (GH-10, GH-13 fixed, the rest accepted or wontfix). `/security-review` of the module found nothing. |
| 30 | **Sweep: `e2e/`** | SEED-1…SEED-10 | Full review sweep, 2026-10-31: `/code-review` (high) of `apps/backend/e2e/`, verified; fixed in 0.12.43 (`e2e-seed-review-fixes`); its fix-diff review SEED-11…SEED-19 (SEED-13, SEED-14, SEED-18 accepted, the rest fixed). `/security-review` of the module found nothing. |
| 31 | **Sweep: `services/*.py`** | SVC-1…SVC-10 | Full review sweep, 2026-10-31: `/code-review` (high) of `apps/backend/services/*.py`, verified; fixed in 0.12.44 (`services-review-fixes`); its fix-diff review SVC-11…SVC-20 (SVC-11, SVC-12 fixed, SVC-20 in part, SVC-16 fixed in 0.12.76, the rest accepted). `/security-review` of the module found nothing (validated against the code). |
| 32 | **Sweep: `services/github/`** | GHS-1…GHS-10 | Full review sweep, 2026-10-31: `/code-review` (high) of `apps/backend/services/github/`, verified; GHS-3, GHS-7, GHS-8 partial, the rest confirmed; fixed in 0.12.45 (`github-services-review-fixes`); its fix-diff review is batch 35. `/security-review` of the module found nothing (validated against the code). |
| 33 | **Sweep: `frontend/src/api/`** | API-1…API-9 | Full review sweep, 2026-11-02: `/code-review` (high) of `apps/frontend/src/api/`, verified; API-1, API-4, API-9 confirmed, API-2, API-3, API-5 partial, API-6, API-7 accepted, API-8 false positive; fixed in 0.12.46 (`api-client-review-fixes`); its fix-diff review is batch 35. `/security-review` of the module found nothing. `openapi.json` matches a fresh export. |
| 34 | **Sweep: `frontend/src/features/auth/`** | AUTH-1…AUTH-9 | Full review sweep, 2026-11-02: `/code-review` (high) of `apps/frontend/src/features/auth/`, verified; AUTH-1, AUTH-2, AUTH-5, AUTH-6, AUTH-7, AUTH-9 confirmed, AUTH-3, AUTH-4, AUTH-8 partial; fixed in 0.12.47 (`auth-review-fixes`); its fix-diff review is batch 35. `/security-review` of the module found nothing (no cross-user path for AUTH-4: sign-in is a full-page navigation). |
| 35 | **Fix-diff review of batches 32–34** | FD-1…FD-10 | `/simplify` (4 agents, one combined diff of 0.12.45–0.12.47: `errors.error_for_response`, `client.parse_dt`, `storage.lock_repository` in the sync steps, `src/app/session.ts`, private `csrfToken`, shared test fixtures) then `/code-review` (high) of the result, 2026-11-02, verified; FD-1, FD-8, FD-10 fixed before commit, the rest accepted or wontfix. |
| 36 | **Sweep: `jobs/`** | JOB-1…JOB-10 | Full review sweep, 2026-11-02: `/code-review` (high) of `apps/backend/jobs/`, verified; JOB-1…JOB-7 confirmed, JOB-8 partial, JOB-9, JOB-10 accepted; fixed in 0.12.48 (`jobs-review-fixes`). `/security-review` of the module found nothing. |
| 37 | **Sweep: `developers/`** | DEV-1…DEV-9 | Full review sweep, 2026-11-02: `/code-review` (high) of `apps/backend/developers/`, verified; DEV-1, DEV-2, DEV-8, DEV-9 confirmed, DEV-3, DEV-4, DEV-5, DEV-7 confirmed (minor), DEV-6 accepted with a guard test; fixed in 0.12.49 (`developers-review-fixes`). `/security-review` of the module found nothing. |
| 38 | **Sweep: `repositories/`** | REPO-1…REPO-8 | Full review sweep, 2026-11-02: `/code-review` (high) of `apps/backend/repositories/`, verified; REPO-5, REPO-6, REPO-7 confirmed, REPO-1 confirmed (logging; no retry of database errors), REPO-2, REPO-3, REPO-4 confirmed (minor), REPO-8 accepted; fixed in 0.12.50 (`repositories-review-fixes`). `/security-review` of the module found nothing. |
| 39 | **`/simplify` of batches 36–38** | SIM-1…SIM-16 | `/simplify` (4 agents: reuse, simplification, efficiency, altitude; one combined diff of 0.12.48–0.12.50), 2026-11-02; SIM-1…SIM-7 fixed before commit, the rest open, deferred, accepted or wontfix (two to `ideas.md` §15, SIM-8 to the `recommendations/` sweep). The fix-diff `/code-review` was skipped by the owner. |
| 40 | **Sweep: `issues/`** | ISS-1…ISS-8 | Full review sweep, 2026-11-03: `/code-review` (high) of `apps/backend/issues/`, verified; ISS-1, ISS-2, ISS-5, ISS-7, ISS-8 confirmed, ISS-3, ISS-4, ISS-6 accepted; fixed in 0.12.51 (`issues-review-fixes`). `/security-review` of the module found nothing. |
| 41 | **Sweep: `recommendations/`** | REC-1…REC-10 | Full review sweep, 2026-11-03: `/code-review` (high) of `apps/backend/recommendations/`, verified; REC-1…REC-4, REC-6, REC-8, REC-10 confirmed, REC-7, REC-9 confirmed (minor), REC-5 false positive (specified); fixed in 0.12.52 (`recommendations-review-fixes`), closing SIM-8. `/security-review` of the module found nothing. |
| 42 | **Sweep: `feedback/`** | FB-1…FB-7 | Full review sweep, 2026-11-03: `/code-review` (high) of `apps/backend/feedback/`, verified; FB-1, FB-3, FB-5 fixed in 0.12.53 (`feedback-review-fixes`), FB-2, FB-6 accepted (owner), FB-4 false positive, FB-7 wontfix. `/security-review` found nothing. |
| 43 | **Sweep: `services/profiling/`** | PROF-1…PROF-9 | Full review sweep, 2026-11-03: verified (PROF-1…PROF-8 reproduced); all fixed in 0.12.54 (`profiling-review-fixes`, `skill-detection` delta), PROF-8 by owner decision (forks never count). `/security-review` found nothing. |
| 44 | **Sweep: `frontend/src/app/`** | APP-1…APP-10 | Full review sweep, 2026-11-03: verified; APP-1…APP-6, APP-9, APP-10 fixed in 0.12.55 (`app-review-fixes`), APP-7, APP-8 accepted. `/security-review` found nothing. |
| 45 | **Sweep: `frontend/src/routes/`** | ROUTE-1…ROUTE-10 | Full review sweep, 2026-11-03: verified; fixed in 0.12.56 (`routes-review-fixes`), ROUTE-10 in part (no not-found page). `/security-review` found nothing. |
| 46 | **Sweep: `features/issues/`** | FI-1…FI-10 | Full review sweep, 2026-11-03: verified; FI-1…FI-3, FI-6, FI-7, FI-10 fixed in 0.12.57 (`issue-detail-review-fixes`), FI-4 accepted with a guard, FI-5, FI-8, FI-9 false positive. `/security-review` found nothing. |
| 47 | **Sweep: `frontend/e2e/` + config** | E2EC-1…E2EC-7 | Full review sweep, 2026-11-03: verified; E2EC-1, E2EC-3, E2EC-4, E2EC-6, E2EC-7 fixed in 0.12.58 (`e2e-config-review-fixes`), E2EC-2, E2EC-5 accepted. `/security-review` found nothing. |
| 48 | **Sweep: `scripts/`** | SCR-1…SCR-10 | Full review sweep, 2026-11-03: verified; SCR-1…SCR-4, SCR-6…SCR-10 fixed in 0.12.59 (`scripts-review-fixes`), SCR-5 accepted. `/security-review` found nothing. |
| 49 | **Sweep: `.github/workflows/`** | CI-1…CI-10 | Full review sweep, 2026-11-03: verified; all fixed in 0.12.60 (`ci-review-fixes`, `developer-tooling` delta), CI-4…CI-6 as hardening. `/security-review` found nothing. |
| 50 | **Fix-diff review of 0.12.51–0.12.54** | FD2-1…FD2-9 | `/simplify` (4 agents, one diff, applied) and `/code-review` (high) of the uncommitted 0.12.51–0.12.54 code, 2026-11-03; all fixed before commit (FD2-5, FD2-6 owner decisions). |
| 51 | **`/simplify` of 0.12.55–0.12.57** | SIM2-1…SIM2-12 | `/simplify` (4 agents, one combined diff of the uncommitted 0.12.55–0.12.57 code), 2026-11-03; SIM2-1…SIM2-8 fixed before commit, SIM2-9…SIM2-12 skipped (reasons in its section). |
| 52 | **Fix-diff review of 0.12.55–0.12.57** | CR-1…CR-10 | `/code-review` (high, no verify pass) of the uncommitted 0.12.55–0.12.57 code after batch 51, 2026-11-03; each row checked by reading; CR-1…CR-7, CR-10 fixed before commit (owner: fix all), CR-8 already documented, CR-9 kept (SIM2-11). |
| 53 | **`/simplify` of 0.12.58–0.12.60** | SIM3-1…SIM3-14 | `/simplify` (reuse, simplification, efficiency, altitude; one combined diff of the uncommitted 0.12.58–0.12.60 tooling and CI code), 2026-11-06; SIM3-1…SIM3-8 fixed before commit, SIM3-9 later fixed as CR3-5, SIM3-10…SIM3-14 skipped (reasons in its section). |
| 54 | **Fix-diff review of 0.12.58–0.12.60** | CR3-1…CR3-8 | `/code-review` (high) of the uncommitted 0.12.58–0.12.60 code after batch 53, 2026-11-06; each row checked by reading; all fixed before commit (owner: fix all). |
| 55 | **Public-release check** | PUB-1…PUB-3 | History and repository check before going public, 2026-11-12; PUB-1 fixed in 0.12.61, PUB-2 accepted, PUB-3 open (GitHub settings, owner only). |
| 56 | **Sweep: `services/repositories/`** | RS-1…RS-10 | Full review sweep (low group), 2026-11-12: verified by reading; RS-1…RS-3, RS-5…RS-10 fixed in 0.12.62 (`services-repositories-review-fixes`), RS-4 false positive. `/security-review` found nothing. |
| 57 | **Sweep: `services/issues/`** | ISV-1…ISV-10 | Full review sweep (low group), 2026-11-12: verified (ISV-1…ISV-4 reproduced); ISV-1, ISV-2, ISV-4…ISV-8, ISV-10 fixed and ISV-3 in part in 0.12.63 (`services-issues-review-fixes`), ISV-9 accepted. `/security-review` found nothing. |
| 59 | **Sweep: `services/discovery/`** | DSC-1…DSC-8 | Full review sweep (low group), 2026-11-13: verified by reading; DSC-1, DSC-2, DSC-4…DSC-8 fixed in 0.12.64 (`services-discovery-review-fixes`), DSC-3 false positive. `/simplify` in batch 61, fix-diff `/code-review` in batch 62. `/security-review` found nothing. |
| 60 | **Sweep: `services/matching/`** | MAT-1…MAT-8 | Full review sweep (low group), 2026-11-13: verified by reading; MAT-1…MAT-5, MAT-7, MAT-8 fixed in 0.12.65 (`services-matching-review-fixes`), MAT-6 rejected (ranks restart per band by design). `/simplify` in batch 61, fix-diff `/code-review` in batch 62. `/security-review` found nothing. |
| 61 | **`/simplify` of 0.12.64–0.12.65** | SIM4-1…SIM4-8 | `/simplify` (4 agents: reuse, simplification, efficiency, altitude; one combined diff of the uncommitted 0.12.64–0.12.65 code), 2026-11-14; SIM4-1…SIM4-6 fixed before commit, SIM4-7, SIM4-8 skipped (reasons in its section; later covered by CR5-4, CR5-7). |
| 62 | **Fix-diff review of 0.12.64–0.12.65** | CR5-1…CR5-8 | `/code-review` (high) of the uncommitted 0.12.64–0.12.65 code after batch 61, 2026-11-14; each row checked by reading (CR5-1 by hand); all fixed before commit (owner: fix all), CR5-6 as a test, CR5-5 within what is stored. |
| 63 | **Sweep: `services/ranking/`** | RNK-1…RNK-10 | Full review sweep (low group), 2026-11-14: verified by reading; all fixed in 0.12.66 (`ranking-review-fixes`), RNK-8 and RNK-10 together; baselines unchanged. `/security-review` found nothing. |
| 64 | **Sweep: `services/evaluation/`** | EVL-1…EVL-10 | Full review sweep (low group), 2026-11-14: verified by reading; fixed in 0.12.67 (`services-evaluation-review-fixes`), EVL-8 accepted; baselines unchanged. `/security-review`: one candidate (CSV formula cells, 3/10), fixed as hardening under EVL-6. |
| 65 | **Sweep: `frontend/src/features/recommendations/`** | REC-1…REC-10 | Full review sweep (low group), 2026-11-14: verified by reading; all fixed in 0.12.68 (`recommendations-view-review-fixes`). `/security-review` found nothing. |
| 66 | **Sweep: `frontend/src/features/feedback/`** | FBK-1…FBK-10 | Full review sweep (low group), 2026-11-14: verified by reading; FBK-1…FBK-5, FBK-8…FBK-10 fixed in 0.12.70 (`feedback-ui-review-fixes`), FBK-6, FBK-7 duplicates of REC-2, REC-4. `/security-review` found nothing. |
| 67 | **Sweep: `frontend/src/features/profile/`** | PRF-1…PRF-10 | Full review sweep (low group), 2026-11-14: verified by reading; all fixed in 0.12.71 (`profile-ui-review-fixes`), PRF-2, PRF-4 latent. `/security-review` found nothing. |
| 71 | **Fix-diff review of 0.12.66–0.12.68** | CR6-1…CR6-6 | `/code-review` (high) of the staged 0.12.66–0.12.68 code, 2026-11-14; all fixed in 0.12.69 (owner: fix all; no OpenSpec change), CR6-4 reverts RNK-9. |
| 68 | **Sweep: `frontend/src/features/sync/ + discovery/`** | PIPE-1…PIPE-10 | Full review sweep (low group), 2026-11-14: verified by reading; fixed in 0.12.72 (`pipeline-progress-review-fixes`), PIPE-3 in part. `/security-review` found nothing. |
| 69 | **Sweep: `frontend/src/components/ + src/lib/`** | CMP-1…CMP-10 | Full review sweep (low group), 2026-11-14: verified by reading; fixed in 0.12.73 (`shared-components-review-fixes`), CMP-4 accepted, CMP-6 duplicate of FBK-8. `/security-review` found nothing. |
| 70 | **Sweep: root config** | ROOT-1…ROOT-10 | Full review sweep (low group, last module), 2026-11-14: verified by reading; all fixed in 0.12.74 (`root-config-review-fixes`). `/security-review` found nothing at its bar. |
| 72 | **Fix-diff review of 0.12.70–0.12.74** | CR7-1…CR7-10 | `/code-review` (high) of the uncommitted 0.12.70–0.12.74 code, 2026-11-15; all fixed in 0.12.75 (owner: fix all; no OpenSpec change). |
| 73 | **`/simplify` of 0.12.76** | SIM5-1…SIM5-5 | `/simplify` (4 agents) of the uncommitted 0.12.76 code (cache generation), 2026-11-16; SIM5-1…SIM5-3 fixed before commit (SIM5-1 later reverted by CR8-1), SIM5-4, SIM5-5 skipped (reasons in its section). |
| 74 | **Fix-diff review of 0.12.76** | CR8-1…CR8-8 | `/code-review` (high, no verify pass) of the uncommitted 0.12.76 code after batch 73, 2026-11-16; each row checked by reading; CR8-1…CR8-4, CR8-7, CR8-8 fixed before commit (owner: fix all), CR8-5, CR8-6 rejected (reasons in its section). |

Shipped: batch 1 in 0.12.1, 2 in 0.12.2, 3 in 0.12.3, 4 in 0.12.4, 5 and 12 in 0.12.5, 6 (with
W-1…W-10) in 0.12.6, 7 and 13 in 0.12.7, 9 and 14 in 0.12.8, 10 and 15 in 0.12.9, 11 and 17 in
0.12.10 (A-18 wontfix), 16 with Q-10…Q-12 in 0.12.11 (P-1 and Q-10 in part, P-3 not reproduced),
Y-6 (in part), Y-7 and Z-1 in 0.12.12, P-3 (and Q-10 accepted) in 0.12.13, B-14, B-15, B-16
and D-7 of batch 8 in 0.12.14 (the code follows the existing specs, so no OpenSpec change), with
S-1…S-5 of batch 18; D-12, D-13 and S-9…S-11 in 0.12.15; D-8, D-9, D-15, D-16, D-17, D-18 of
batch 8 in 0.12.16 (`signal-explanation-accuracy`); S-7 of batch 18 in 0.12.17
(`keyset-paging-links`); S-6 in 0.12.18 (`activation-command-only`); T-1…T-10 of batch 19 in 0.12.23; X-9 in 0.12.26 (`post-analysis-pool-cleanup`); Y-6 in 0.12.27 (`data-versions`); T-12 in 0.12.29 (`rank-constraint`); U-1…U-3, U-5…U-7 in 0.12.31 (`data-versions-fixes`); B-6, D-11 (the rest of batch 8) and T-11
in 0.12.32 (no OpenSpec change: B-6 follows its documented rounded mean, the spec does not order
title keywords, and T-11's `issue-matching` spec was edited directly), with P-1 accepted. L-5 of batch 23 in 0.12.35; L-1, L-2, L-4 in 0.12.36
(`released-name-refresh`); RT-1, RT-2, RT-6 of batch 24 in 0.12.37 (`route-id-validation`); E2E-1, E2E-2, E2E-5, E2E-7
(and E2E-6 documented) of batch 25 in 0.12.38 (`e2e-production-build`); batch 26 (CFG-1…CFG-20,
CFG-7 and CFG-8 accepted) in 0.12.39 (`config-review-fixes`); batch 27 (CORE-1…CORE-10) in 0.12.40
(`core-review-fixes`); batch 28 (ACC-1…ACC-10, ACC-4 accepted) in 0.12.41 (`accounts-review-fixes`); batch 32 (GHS-1…GHS-10) in 0.12.45
(`github-services-review-fixes`); batch 33 (API-1…API-5, API-9; API-6, API-7 accepted, API-8 false
positive) in 0.12.46 (`api-client-review-fixes`); batch 34 (AUTH-1…AUTH-9) in 0.12.47
(`auth-review-fixes`); batch 36 (JOB-1…JOB-8; JOB-9, JOB-10 accepted) in 0.12.48
(`jobs-review-fixes`); batch 37 (DEV-1…DEV-9; DEV-6 accepted with a guard) in 0.12.49
(`developers-review-fixes`); batch 38 (REPO-1…REPO-7; REPO-8 accepted) in 0.12.50
(`repositories-review-fixes`); batch 39 (`/simplify`, SIM-1…SIM-7) in 0.12.50; batch 40 (ISS-1, ISS-2, ISS-5, ISS-7, ISS-8; ISS-3, ISS-4, ISS-6
accepted) in 0.12.51 (`issues-review-fixes`); batch 41 (REC-1…REC-4, REC-6…REC-10; REC-5 false
positive) and SIM-8 in 0.12.52 (`recommendations-review-fixes`); batch 42 (FB-1, FB-3, FB-5; FB-2, FB-6 accepted, FB-4 false positive, FB-7 wontfix) in 0.12.53 (`feedback-review-fixes`); batch 43 (PROF-1…PROF-9) in 0.12.54 (`profiling-review-fixes`); batch 50 (fix-diff review of 0.12.51–0.12.54, FD2-1…FD2-9) folded into 0.12.53 and 0.12.54; batch 44 (APP-1…APP-6, APP-9, APP-10; APP-7, APP-8 accepted) in 0.12.55 (`app-review-fixes`); batch 45 (ROUTE-1…ROUTE-10, ROUTE-10 in part) in 0.12.56 (`routes-review-fixes`); batch 46 (FI-1…FI-3, FI-6, FI-7, FI-10; FI-4 guard) in 0.12.57 (`issue-detail-review-fixes`); batch 51 (`/simplify`, SIM2-1…SIM2-8) and batch 52 (fix-diff review, CR-1…CR-7, CR-10) folded into 0.12.55–0.12.57; batch 47 (E2EC-1, E2EC-3, E2EC-4, E2EC-6, E2EC-7; E2EC-2, E2EC-5 accepted) in 0.12.58 (`e2e-config-review-fixes`); batch 48 (SCR-1…SCR-4, SCR-6…SCR-10; SCR-5 accepted) in 0.12.59 (`scripts-review-fixes`); batch 49 (CI-1…CI-10) in 0.12.60 (`ci-review-fixes`); PUB-1 of batch 55 in 0.12.61 (no OpenSpec change, docs only); batch 56 (RS-1…RS-3, RS-5…RS-10; RS-4 false positive) in 0.12.62 (`services-repositories-review-fixes`); batch 57 (ISV-1, ISV-2, ISV-4…ISV-8, ISV-10, ISV-3 in part; ISV-9 accepted) in 0.12.63 (`services-issues-review-fixes`); batch 59 (DSC-1, DSC-2, DSC-4…DSC-8; DSC-3 false positive) in 0.12.64 (`services-discovery-review-fixes`); batch 60 (MAT-1…MAT-5, MAT-7, MAT-8; MAT-6 rejected) in 0.12.65 (`services-matching-review-fixes`); batch 71 (CR6-1…CR6-6, fix-diff review of 0.12.66–0.12.68) in 0.12.69 (no OpenSpec change); batch 66 (FBK-1…FBK-5, FBK-8…FBK-10; FBK-6, FBK-7 duplicates) in 0.12.70 (`feedback-ui-review-fixes`); batch 67 (PRF-1…PRF-10) in 0.12.71 (`profile-ui-review-fixes`); batch 68 (PIPE-1…PIPE-10, PIPE-3 in part) in 0.12.72 (`pipeline-progress-review-fixes`); batch 69 (CMP-1…CMP-3, CMP-5, CMP-7…CMP-10; CMP-4 accepted, CMP-6 duplicate) in 0.12.73 (`shared-components-review-fixes`); batch 70 (ROOT-1…ROOT-10) in 0.12.74 (`root-config-review-fixes`); batch 72 (CR7-1…CR7-10, fix-diff review of 0.12.70–0.12.74) in 0.12.75 (no OpenSpec change).
Next: the full review sweep is complete (2026-11-15; batches 26–72 fixed or closed); RT-3…RT-5 of batch 24 (open, design-level; see its section); the known gaps K-1…K-5 remain.

Not in a batch: K-1…K-5 (roadmap items, tracked elsewhere). K-1's prerequisites (batches 2 and
3, E-3) shipped in 0.12.2 and 0.12.3.

## Summary

Status after verification: `confirmed` = defect exists as described; `partial` = defect exists but
scenario or severity is narrower; `false-positive` = not a defect. The table covers the sweep of
2026-10-19 and the reviews through batch 20; later batches (21–26) give each row's status in their
own sections.

| Section | Rows | Confirmed | Partial | False positive |
|---|---|---|---|---|
| K (known) | 5 | — | — | — |
| DOC | 2 | — | — | — |
| R last-commit review | 14 | 12 | 2 | 0 |
| A auth/GitHub | 20 | 16 | 3 | 1 |
| B jobs/profiling | 20 | 15 | 5 | 0 |
| C repositories/discovery | 23 | 19 | 4 | 0 |
| D recommendations/issues | 21 | 15 | 6 | 0 |
| E feedback/evaluation | 10 | 8 | 2 | 0 |
| F frontend | 9 | 8 | 1 | 0 |
| G scripts/infra | 10 | 6 | 4 | 0 |
| H platform/settings/tests | 20 | 16 | 4 | 0 |
| V batch 5 review | 9 | 6 | 2 | 1 |
| W batch 6 review | 10 | 10 | 0 | 0 |
| X batch 7 review | 12 | 11 | 0 | 1 |
| Y batch 9 review | 10 | 9 | 1 | 0 |
| Z batch 10 review | 10 | 7 | 3 | 0 |
| P batch 11 notes | 5 | 3 | 2 | 0 |
| Q batch 11 review | 12 | 12 | 0 | 0 |
| S 0.12.13/0.12.14 review | 11 | 10 | 1 | 0 |
| T 0.12.23 review | 14 | 12 | 2 | 0 |
| U 0.12.24–0.12.30 review | 8 | 7 | 1 | 0 |
| **Total** | **255** | **202** | **43** | **3** |

## Review history

The sections below are the record, oldest first: the 2026-10-19 sweep (last-commit review,
documentation drift, full-file reviews and their verification), then each fix release's review.
The totals are in "Summary" above.

## Code review findings

Source: `code-review` (high, `apps/`, all findings). **Scope caveat:** the review covered only the
last commit (`HEAD~1..HEAD`, 50acbb8: benchmark tooling and discovery size mix), not the whole
codebase. All rows verified against the code (2026-10-19); see Verification notes. Ranked most
severe first.

| ID | File | Finding | Failure scenario | Status |
|---|---|---|---|---|
| R-1 | `apps/backend/recommendations/management/commands/evaluate_ranking.py:77` | `--write-baseline` without `--dataset` evaluates the selection dataset (benchmark-v2 once present), so the documented baseline fix never rewrites the benchmark-v1 entry that CI checks. | With a local benchmark-v2, `evaluate_ranking --write-baseline` rewrites only `datasets.benchmark-v2`; CI skips v2 and `test_baseline_metrics_unchanged` fails on stale v1. Workaround: `--dataset evaluation/benchmark-v1.json`. | fixed (evaluation-tooling-integrity) |
| R-2 | `apps/backend/services/evaluation/baseline.py:42` | Format 3 keeps other datasets' entries but stores one global `top_n` from the current run. | v1 written at top_n 50, then `--dataset holdout-v2 --write-baseline --top-n 20` sets `top_n: 20` globally; the test re-evaluates v1 at 20 against metrics from 50 and reports a false "Ranking changed". Store `top_n` per dataset. | fixed (evaluation-tooling-integrity) |
| R-3 | `apps/backend/config/settings/base.py:279` | Default `DISCOVERY_STAR_BANDS` hardcodes 20 instead of deriving from `DISCOVERY_MIN_STARS`; system check requires a match. | Set only `DISCOVERY_MIN_STARS=50` → `core.E025` fails, Django refuses to start (runserver, migrate, worker). | fixed (discovery-repository-data) |
| R-4 | `apps/backend/services/discovery/service.py:305` | `_remove_not_code` writes lifecycle and eligibility directly, overwriting existing reasons and racing with an in-progress analysis claim. | (a) FAILED or archived repository loses its real `ineligible_reason`. (b) REFRESHING repository (previous RECOMMENDABLE) is marked ineligible, analysis fails transiently, `lifecycle.release()` restores RECOMMENDABLE → RECOMMENDABLE but ineligible. Move to `services/repositories/lifecycle.py`. | fixed (discovery-repository-data) |
| R-5 | `apps/backend/services/discovery/filters.py:116` | `not_code` treats any `awesome-*` name and generic topics (`list`, `lists`, `books`) as non-code; ineligibility is set on the shared Repository row. | `sindresorhus/awesome-lint` (a linter) is rejected; a linked-list library tagged `list` is rejected; it disappears for every user despite having a primary language. | fixed (discovery-repository-data) |
| R-6 | `apps/backend/services/discovery/queries.py:172` | Provenance `core` includes the star band; a repository crossing a band creates a new CandidateDiscovery row and the old one (with its old search_rank) is never updated or pruned. | Rank #1 at `stars:20..999`, grows to rank #28 at `>=1000`; `Min(search_rank)` stays 1, so the stale rank keeps analysis priority and survives the pool cap. Band qualifier also leaks into user-facing provenance. | fixed (discovery-repository-data) |
| R-7 | `apps/backend/services/evaluation/sheet.py:94` | `read_sheet` drops every physical line starting with `#` before CSV parsing, including continuation lines inside quoted multi-line fields. | Description `"Fast parser\n# Features"` loses its closing line and grade; quoted field swallows the next row → lost or misattributed grade, or a confusing "not a candidate" error. | fixed (evaluation-tooling-integrity) |
| R-8 | `apps/backend/services/evaluation/sheet.py:98` | Duplicate repository rows: last wins silently. Formatted empty rows (`,,,,,,,,,`) become repository `''` and fail the whole import. | Spreadsheet saves trailing blank rows → `Row : not a candidate of this export`, nothing imported. | fixed (evaluation-tooling-integrity) |
| R-9 | `apps/backend/services/discovery/service.py:440` | `_band_counts` assigns stars to the highest band whose low is reached, ignoring that band's high. | Bands `[[20,99],[200,999]]` (allowed by the check): 150 stars → `20..99`; 5000 stars → `200..999`. `pool_bands` metadata wrong. | fixed (discovery-repository-data) |
| R-10 | `apps/backend/services/discovery/queries.py:164` | Request budget floor-divided by band count; remainder silently wasted; check accepts non-multiples. | `DISCOVERY_MAX_QUERIES=25`, 3 bands → 24 requests; 5 with 3 bands → one query. No warning. | fixed (discovery-repository-data) |
| R-11 | `apps/backend/services/discovery/filters.py:126` | `_topics` uses `values_list`, which bypasses prefetch → N+1 in `_step_interactions`; `_remove_not_code` duplicates the topic extraction. | One extra query per contributed repository (up to `GITHUB_CONTRIB_MAX_REPOS`). Fix: `repo.topics.all()` + `prefetch_related('topics')`. Docstring still says "Pure functions". | fixed (discovery-repository-data) |
| R-12 | `apps/backend/services/discovery/service.py:285` | Design: pool step re-checks only `not_code` on stored data; other eligibility rules go stale when settings change. | After changing `DISCOVERY_MAX_PUSH_AGE_DAYS` or license rules, RECOMMENDABLE repositories keep old eligibility until re-analysis. Re-run `eligibility()` via a lifecycle helper (would also fix R-4). | fixed (discovery-repository-data) |
| R-13 | `apps/backend/services/evaluation/build.py:34` | `build` assumes each input is a JSON object; a top-level list raises uncaught `AttributeError`. Differing `format` merged unchecked until final `parse`. | `build_benchmark --input report.json` (array) → raw traceback instead of `CommandError`. | fixed (evaluation-tooling-integrity) |
| R-14 | `apps/backend/recommendations/management/commands/build_benchmark.py:174` | Real developers keep the export description "Add judgments ... by hand before using this developer"; `import_sheet` does not update it. | Committed benchmark-v2 shows judged developers labeled as unjudged. | fixed (evaluation-tooling-integrity) |

## Documentation drift

| ID | Item | Where | Status |
|---|---|---|---|
| DOC-1 | Ctrl+C issue still `[~] carried to Phase 5`; fixed in Phase 8a per CLAUDE.md §6, no `[x]` entry records it. | features.txt:130 | fixed (performance-cleanup) |
| DOC-2 | Carry-over says "real-a exported, 3 of 39 graded"; current target is `real-a-v2` (40 candidates). The 3 grades are likely in the stale `real-a.csv`. | features.txt:261 | fixed (performance-cleanup) |

## Full-file reviews (2026-10-19)

`code-review` at high effort over whole files, all findings reported. All rows verified against
the code by a second, adversarial pass (2026-10-19); see Verification notes. Cited line numbers
are often stale: use the corrected lines there, or search for the symbol. Paths are under `apps/backend/` (areas A-E), `apps/frontend/src/` (F) and
the repository root (G). Within each area, rows are ordered most severe first. Type: bug · gap (spec/rule violation) · perf · cleanup.

### A: Auth, tokens, GitHub client and sync, data deletion

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| A-1 | bug | `services/data_deletion.py:54` | Deletion only flips job status; a sync mid-step keeps the decrypted token and writes GitHubProfile, repositories or DeveloperProfile after the deletion commits → deleted data returns, and GitHub calls run after disconnect. | fixed (privacy-deletion-finality) |
| A-2 | bug | `services/github/client.py:584` | A secondary-rate-limit 403 without Retry-After and with remaining > 0 → `GitHubForbidden`, not `GitHubRateLimited`. `count_contributors` returns None, SKIPPABLE steps drop data, and other paths fail as `github_error`. Rate limit is treated as empty data. | fixed (github-error-resilience) |
| A-3 | bug | `services/github/sync.py:165` | `_step_languages` catches only 404; one owned repository returning 403 or 451 (DMCA) fails every sync permanently → no analysis, discovery or recommendations. | fixed (github-error-resilience) |
| A-4 | bug | `services/github/client.py:524` | Redirects not followed; the 301 for a renamed repository → `GitHubClientError`. Contribution evidence dropped; the languages step fails the whole sync; discovery fails too (see C-1). | fixed (github-error-resilience) |
| A-5 | bug | `services/github/sync.py:117` | `_step_readme` treats only 404 as "no README"; a 403 or 451 on `{login}/{login}` fails the sync. Violates the rule that a README failure degrades gracefully. | fixed (github-error-resilience) |
| A-6 | bug | `services/crypto.py:45` | `TokenDecryptionError` is not a `GitHubError`; after a key rotation drops an old key, syncs fail as `internal_error`, not `github_auth_invalid` → user is never prompted to sign in again. | fixed (github-error-resilience) |
| A-7 | gap | `accounts/views.py:130` | SIGN_IN audit metadata keeps `github_id` and `github_username`; account deletion only nulls the user FK → GitHub identity survives "delete account" (FR-DATA-003). | fixed (privacy-deletion-finality) |
| A-8 | gap | `services/github/accounts.py:31` | `User.display_name` (real name from GitHub) is not cleared by disconnect or delete-data; still served by `/auth/me`. | fixed (privacy-deletion-finality) |
| A-9 | gap | `services/github/accounts.py:35` | Re-sign-in stores the new token without revoking the old one → orphaned valid tokens until disconnect. | fixed (privacy-deletion-finality) |
| A-10 | bug | `services/github/storage.py:26` | `upsert_repository` (`update_or_create` on github_id) races on concurrent create → IntegrityError → `internal_error`, not retried; the user's job fails. | false-positive |
| A-11 | bug | `services/github/sync.py:178` | `_step_topics` inserts for repository pks saved earlier in metadata; if the row was deleted in between (full_name conflict, orphan cleanup) → FK IntegrityError → sync fails permanently. | fixed (github-error-resilience) |
| A-12 | bug | `accounts/views.py:214` | Disconnect logs out only the current session; other sessions stay valid up to 14 days with no GitHub account. | fixed (privacy-deletion-finality) |
| A-13 | bug | `services/github/sync.py:96` | Sync refreshes `GitHubProfile.login/avatar_url` but not `GitHubAccount.username/avatar_url` (what `/auth/me` serves) → stale login after a GitHub rename until the next sign-in. | fixed (github-error-resilience) |
| A-14 | bug | `services/github/oauth.py:107` | `fetch_identity` does not guard `response.json()` or `data['id'/'login']` → malformed 200 gives a JSON 500 instead of an `auth_error=failed` redirect plus audit entry. | fixed (github-error-resilience) |
| A-15 | bug | `accounts/views.py:75` | One OAuth state per session; signing in from a second tab overwrites it → first tab's callback fails `invalid_state`. | fixed (security-hardening) |
| A-16 | perf | `services/github/client.py:530` | `github:ratelimit:{scope}` written on every response but never read; keyed per scope, not per credential (user `PUBLIC_SCOPE` overwrites the app's). | fixed (performance-cleanup) |
| A-17 | perf | `services/github/client.py:511` | A 304 does not refresh the ETag cache TTL → valid entries expire at `GITHUB_ETAG_TTL`, forcing a counted 200 refetch. Use `cache.touch`. | fixed (performance-cleanup) |
| A-18 | perf | `services/github/sync.py:79` | Profile sync caches public repository endpoints in the per-user scope, not `PUBLIC_SCOPE` → data duplicated per user, fewer 304 hits. | wontfix (performance-cleanup: the user-scope cache is purged on "delete my data"; a shared scope would let the user's repository responses outlive it, for few extra 304s) |
| A-19 | cleanup | `accounts/views.py:183` | `cancel_active_syncs` runs twice on disconnect and account deletion (`_revoke_and_unlink` + `delete_github_data`). | fixed (privacy-deletion-finality) |
| A-20 | perf | `core/health.py:31` | `check_redis` creates a new Redis client and pool on every health request. | fixed (performance-cleanup) |

### B: Jobs, developer profiling

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| B-1 | bug | `services/jobs.py:150` | PENDING and RETRYING jobs never expire or recover (only RUNNING does). A lost Redis message → zombie job, blocked by the unique constraint → user can never sync, discover or regenerate again. | fixed (job-claim-fencing) |
| B-2 | bug | `services/jobs.py:44` | `claim_job` reclaims a stale RUNNING job without fencing; `heartbeat`/`finish_job` don't check ownership → a slow (not dead) worker and the new one both write; first to finish fires `on_completed`. Needs a claim token. | fixed (job-claim-fencing) |
| B-3 | bug | `services/profiling/analysis.py:218` | Shared Skill and Interest rows upserted (`ON CONFLICT DO UPDATE`) in confidence order inside per-user transactions → concurrent analyses deadlock → `analysis_failed`, not retried. Sort slugs, or upsert outside the transaction. | fixed (job-claim-fencing) |
| B-4 | bug | `services/profiling/analysis.py:257` | `_persist` uses `get_or_create`; an analysis running during delete-data recreates DeveloperProfile and README evidence (see A-1). | fixed (privacy-deletion-finality) |
| B-5 | bug | `services/profiling/analysis.py:249` | Input snapshot read without a lock and `_persist` overwrites unconditionally → overlapping sync analysis and standalone `profile_analysis` can let the older snapshot win. | fixed (job-claim-fencing) |
| B-6 | bug | `services/profiling/experience.py:58` | Cutoffs 0.67/1.34 are not the documented rounded mean: (1,1,0) mean 0.667 → beginner (should be intermediate); 1.4 → experienced. Feeds `difficulty_fit`. | fixed (0.12.32; no spec change: the level is the rounded mean with halves up, computed in integers (`2·total < n` beginner, `2·total < 3n` intermediate). Benchmarks store each developer's level, so baselines cannot move; stored profiles change on their next analysis or `reanalyze_profiles`) |
| B-7 | bug | `services/jobs.py:250` | `start_profile_analysis` treats stale RUNNING jobs as active (no stale exclusion or `_expire_stale`, unlike the other start_*) → `reanalyze_profiles` skips users for up to about 15 min after a crash. | fixed (job-claim-fencing) |
| B-8 | bug | `services/jobs.py:240` | IntegrityError fallback re-queries the active job, which may have finished meanwhile → `.get()` raises DoesNotExist (500 on POST /profile/sync); `.first()` returns None, read as "no profile". | fixed (job-claim-fencing) |
| B-9 | bug | `services/jobs.py:119` | Eager mode (`REDIS_URL` empty): `task.retry(countdown)` re-runs inline, ignoring the countdown → 5 back-to-back GitHub calls on 5xx or 429, a hot loop. | fixed (job-claim-fencing) |
| B-10 | bug | `services/jobs.py:50` | `claim_job` ignores `attempts` → broker redelivery can exceed `SYNC_MAX_ATTEMPTS` (crash loop continues). | fixed (job-claim-fencing) |
| B-11 | bug | `services/jobs.py:183` | Recovery, expiry and cancel don't update `steps` → a FAILED or CANCELLED job still shows a step `running` (UI spinner on a dead job). | fixed (job-claim-fencing) |
| B-12 | bug | `services/jobs.py:174` | `recover_stale_jobs` re-sends `.delay` every beat without changing status → duplicate messages in a busy queue, repeated misleading log. | fixed (job-claim-fencing) |
| B-13 | bug | `services/profiling/manifests.py:161` | `parse_manifest` doesn't catch RecursionError or MemoryError → a deeply nested package.json fails the dependencies step. | fixed (github-error-resilience) |
| B-14 | bug | `services/profiling/readme.py:32` | `_URLS` keeps `&amp;` → `parse_qs` keys like `amp;logo`; second and later badge params lost (e.g. Go not detected). | fixed (0.12.14, no spec change) |
| B-15 | bug | `services/profiling/readme.py:93` | shields.io parser reads only the first dash segment; `/badge/-Python-...` or `/badge/language-Rust-...` without `logo=` → no evidence. | fixed (0.12.14, no spec change) |
| B-16 | bug | `services/profiling/interests.py:33` | Contribution interest evidence uses `repo.pushed_at`, not `last_contributed_at` → "last observed" overstates recency. | fixed (0.12.14, no spec change) |
| B-17 | perf | `developers/api.py:44` | Two `Count(distinct=True)` over skills and interests joins → cross product (150×40 = 6,000 rows) per profile read. | fixed (performance-cleanup) |
| B-18 | cleanup | `developers/tasks.py:15` | `extract_developer_skills` re-implements `run_tracked_job` by hand; lifecycle fixes (B-2, B-11) must be made twice; task isn't a thin wrapper. | fixed (job-claim-fencing) |
| B-19 | cleanup | `services/jobs.py:277` | Four copy-pasted start_* functions have drifted (causes B-7 and B-8). Extract `_start_job`. | fixed (job-claim-fencing) |
| B-20 | cleanup | `services/profiling/summary.py:28` | Docstring says languages are "by bytes"; callers pass them by confidence on purpose. | fixed (performance-cleanup) |

### C: Repositories, discovery

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| C-1 | bug | `services/repositories/analysis.py:142` | A non-permanent, non-transient client error (301 rename) re-raises → the whole discovery job fails, no lifecycle error recorded; every user whose pool holds the repository fails; backlog requeues forever. The "follows renames" comment (l.161) is wrong. | fixed (github-error-resilience) |
| C-2 | bug | `services/discovery/service.py:364` | `upsert_repository` deletes any other row with the same full_name → a live renamed repository is wiped, cascading to every user's candidates, recommendations, saves and dismissals. | fixed (discovery-repository-data) |
| C-3 | bug | `services/repositories/lifecycle.py:363` | `release/fail/complete` don't check claim ownership → a reclaimed-stale worker overwrites lifecycle while another analyzes; final state = last writer. | fixed (job-claim-fencing) |
| C-4 | bug | `services/repositories/analysis.py:136` | Repository claim never renewed during `_fetch` → analyses longer than 10 min are reclaimed while running (duplicate work, plus C-3). | fixed (job-claim-fencing) |
| C-5 | bug | `services/repositories/analysis.py:129` | Explicit `parts` skip the FAILED→recheck-all rule, and `complete()` sets INDEXED before `eligibility()` → a deleted (404) repository returns as RECOMMENDABLE, eligible. | fixed (discovery-repository-data) |
| C-6 | bug | `services/repositories/analysis.py:56` | `GitHubForbidden` treated as permanent; a secondary-limit 403 (see A-2) marks shared repositories FAILED and ineligible for all users for 24 h. | fixed (github-error-resilience) |
| C-7 | bug | `services/discovery/service.py:137` | Each query's results are upserted in one transaction; concurrent jobs lock the same rows in different orders → deadlock → `internal_error`, job fails. | fixed (discovery-repository-data) |
| C-8 | bug | `services/discovery/service.py:364` | Search upserts set `synced_at=now` → `metadata` never stale for frequently found repositories → languages never refreshed. | fixed (discovery-repository-data) |
| C-9 | bug | `repositories/tasks.py:384` | Non-retryable refresh failure only logged; repository restored with no `lifecycle_error` → breaks "failures are state"; backlog retries forever. | fixed (github-error-resilience) |
| C-10 | bug | `services/repositories/lifecycle.py:371` | `release()` sets `lifecycle_changed_at=now` → a transient error restarts the FAILED 24 h clock and the DISCOVERED grace period. | fixed (job-claim-fencing) |
| C-11 | bug | `services/discovery/service.py:61` | Analysis step runs before the pool step → budget spent on candidates the pool deletes; ordering also differs (pool adds `last_seen_at`). | fixed (discovery-repository-data) |
| C-12 | bug | `services/discovery/service.py:180` | On resume `pending` excludes already analyzed repositories, so `pending[:cap]` takes new ones → more than `DISCOVERY_MAX_ANALYSES_PER_RUN` per run; `analysis_total` overwritten. | fixed (discovery-repository-data) |
| C-13 | bug | `services/discovery/service.py:262` | CandidateDiscovery rows from queries that no longer match are never pruned → stale best rank drives analysis order and eviction (generalizes R-6). | fixed (discovery-repository-data) |
| C-14 | bug | `services/repositories/lifecycle.py:396` | Without a metadata fetch, `complete()` computes eligibility from the in-memory row loaded at claim, ignoring concurrent upserts. | fixed (discovery-repository-data) |
| C-15 | perf | `repositories/tasks.py:357` | Backlog requeues STALE repositories every 15 min even when a task is queued or retrying; explicit-part tasks don't intersect with current stale parts → duplicate fetches. | fixed (discovery-repository-data) |
| C-16 | gap | `repositories/tasks.py:313` | Staleness and backlog selection logic lives in Celery tasks, not services (CLAUDE.md §5). | fixed (discovery-repository-data) |
| C-17 | cleanup | `repositories/api.py:112` | Candidate ordering written three times (API, `_pool_repositories`, `_step_pool`) and drifted. | fixed (discovery-repository-data) |
| C-18 | cleanup | `services/discovery/service.py:366` | Null `lifecycle_changed_at` patched in two places; give the field a default. | fixed (discovery-repository-data) |
| C-19 | bug | `services/repositories/lifecycle.py:365` | `release()` is read-then-update (not atomic); can restore a stale `previous_lifecycle`. | fixed (job-claim-fencing) |
| C-20 | perf | `services/discovery/service.py:184` | Full metadata JSON rewritten after each analysis → quadratic write volume. | fixed (performance-cleanup) |
| C-21 | cleanup | `repositories/serializers.py:58` | `ineligible_reason` not `read_only=True` → OpenAPI marks it writable and required. | fixed (performance-cleanup) |
| C-22 | perf | `services/repositories/lifecycle.py:393` | `complete()` saves ANALYZED and INDEXED separately (unobservable) → 2 wasted UPDATEs per analysis. | fixed (job-claim-fencing) |
| C-23 | cleanup | `repositories/tasks.py:309` | `_has_app_credentials` duplicates `GitHubClient.for_app()`'s check. | fixed (performance-cleanup) |

### D: Recommendations, ranking, matching, issues

Two runs, merged.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| D-1 | bug | `services/matching/features.py:85` | `load_candidates` scores only RECOMMENDABLE; the 6 h stale sweep moves repositories to STALE and bumps `lifecycle_changed_at`, which triggers regeneration → `_persist` deletes their recommendations, which return later with new ids (or never, without app credentials). Breaks "ids survive regenerations"; saved items vanish. | fixed (recommendation-consistency) |
| D-2 | bug | `services/ranking/service.py:151` | `_persist` reads dismissals before locking Recommendation rows → a dismiss committing in between is missed → dismissed repository recreated. | fixed (recommendation-consistency) |
| D-3 | bug | `services/ranking/service.py:215` | Dismiss (cascade deletes children first) and persist (locks parent first) lock in opposite orders → deadlock; dismiss 500 or generation fails. | fixed (recommendation-consistency) |
| D-4 | bug | `services/ranking/service.py:159` | Persist locks Issue rows then deletes RecommendedIssue; issue refresh deletes RecommendedIssue then Issue → deadlock. | fixed (recommendation-consistency) |
| D-5 | bug | `services/ranking/freshness.py:45` | Restore reuses a running generation that already loaded candidates; freshness ignores dismissals and new pool members → restored or newly found repositories missing until an unrelated change. | fixed (recommendation-consistency) |
| D-6 | bug | `services/ranking/service.py:164` | Concurrently deleted issues are dropped from rows and snapshot, but score, signals, label and reason text ("3 open issues…") still count them → explanation not backed by stored data. | fixed (recommendation-consistency) |
| D-7 | gap | `services/ranking/explain.py:188` | Reasons emitted for signals > 0 even when weight 0 → explanations for signals scoring didn't use (FR-REC-003). Filter on contribution > 0. | fixed (0.12.14, no spec change) |
| D-8 | bug | `services/ranking/score.py:99` | Relevance gate checks raw signal values, not weights → a weight-0 relevance signal still admits a candidate. | fixed (signal-explanation-accuracy: the gate needs value and weight above 0, also for issue preselection) |
| D-9 | bug | `services/matching/issues.py:193` | Issue with only technologies the developer lacks still counts via approachability + difficulty (score 0.40 ≥ 0.3) → "matches your profile" for a Rust issue shown to a Python dev. | fixed (signal-explanation-accuracy: the text says whether issues matched by technology, by label only, or both) |
| D-10 | bug | `services/ranking/service.py:156` | Dismissals during a run removed after the `top_n` cut → fewer than N stored although next candidates exist. | fixed (recommendation-consistency) |
| D-11 | bug | `services/issues/classify.py:336` | Title keyword order puts docs, test and CI before bug → "[Bug]: docs build crashes" becomes documentation → beginner vote. Undoes the `[Bug]:` fix. | fixed (0.12.32; no spec change: the keyword earliest in the title wins, list order breaks a tie at the same position; `ISSUE_TAXONOMY_VERSION` 2026.10.4. Trade-off: "Fix broken link in README" now reads bug_fix (was documentation), since `broken` comes first. Benchmarks store each issue's type and difficulty, so baselines cannot move; stored issues change on their next fetch) |
| D-12 | bug | `services/issues/classify.py:412` | `body_length` vote uses raw markdown (template HTML comments included) → wrong or unknown difficulty. | fixed (0.12.15: HTML comments, which issue templates leave as instructions, are dropped before measuring) |
| D-13 | bug | `services/issues/labels.py:110` | `[Type] Bug`-style labels never normalized (`_EDGES` strips only `[`) → no category, filter misses, documentation vote lost. | fixed (0.12.15: `_SCOPE` also takes a `[type]` prefix; `ISSUE_TAXONOMY_VERSION` 2026.10.3) |
| D-14 | bug | `services/ranking/freshness.py:34` | `due_profiles` requires candidates → profile with an emptied pool keeps old recommendations forever. | fixed (recommendation-consistency) |
| D-15 | gap | `recommendations/admin.py:25` | ScoringConfig editable once no Recommendation references it → past versions' numbers can change (feedback snapshots, baselines). Activate action doesn't validate (`stored=True`). | fixed (signal-explanation-accuracy: version, weights and params read-only in the admin for every stored row; `ScoringConfig.save` refuses a change) |
| D-16 | bug | `services/matching/issues.py:136` | Difficulty-fit part of an unknown-difficulty issue's score has no reason → unexplained score. | fixed (signal-explanation-accuracy: "Difficulty not estimated (too few signals)" reason; scores unchanged) |
| D-17 | gap | `services/ranking/config.py:354` | Openness points not validated to sum ≤ 1; silently capped → saturated signal. | fixed (signal-explanation-accuracy: openness points must sum to at most 1) |
| D-18 | gap | `services/issues/classify.py:423` | `technology_count >= 2` and `MIN_VOTES = 2` hard-coded (rule: weights are config). | fixed (signal-explanation-accuracy: `ISSUE_DIFFICULTY` `several_technologies`, `min_votes`, same defaults) |
| D-19 | cleanup | `services/matching/issues.py:105` | `_join` copied three times; GOOD_FIRST_ISSUE/HELP_WANTED re-declared from `labels.py`. | fixed (performance-cleanup) |
| D-20 | cleanup | `services/ranking/score.py:65` | `weighted_score` used only by tests; `score_candidate` duplicates the formula. | fixed (performance-cleanup) |
| D-21 | perf | `services/ranking/freshness.py:43` | `due_profiles` loads every profile into Python every 30 min; express as SQL filter. | fixed (performance-cleanup) |

### E: Feedback, evaluation services, benchmark commands

Excludes what R-1, R-2, R-7, R-8, R-13 and R-14 already cover.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| E-1 | bug | `services/evaluation/baseline.py:333` | `write` replaces the whole dataset entry with only the configs evaluated in this run. `evaluate_ranking --write-baseline --config v2-deterministic` drops v1 from `benchmark-v1`; `test_baseline_metrics_unchanged` asserts both v1 and v2 are present → CI fails. Merge into the existing entry instead. | fixed (evaluation-tooling-integrity) |
| E-2 | bug | `recommendations/management/commands/evaluate_ranking.py:170` | `--write-baseline --min-score X` records the override as every config's `min_score` (and metrics at X), but the test re-evaluates without override at `baseline.MIN_SCORE` → permanent "Ranking changed" mismatch. Reject `--min-score` with `--write-baseline` (as `--config-file` is). | fixed (evaluation-tooling-integrity) |
| E-3 | gap | `services/evaluation/export.py:36` | Export claims anonymized output, but the pool includes `previously_interacted` candidates (repositories the user contributed to) by full name → a committed `benchmark-v2` lets anyone re-identify the developer from their contribution set. | fixed (privacy-deletion-finality) |
| E-4 | bug | `services/evaluation/export.py:36` | Export reuses `load_candidates`, which drops dismissed and non-RECOMMENDABLE (STALE, FETCHING, see D-1) repositories → the judged pool depends on when the beat sweep last ran and omits the user's clearest "not relevant" examples. | fixed (recommendation-consistency) |
| E-5 | bug | `services/feedback.py:86` | `save` does not check for a dismissal; a save from a second tab with a stale recommendation racing `dismiss` leaves a SavedRepository for a hidden repository (shown in Saved while hidden; `dismiss` deleted the save first). Lock or re-check `DismissedRepository` inside the transaction. | fixed (recommendation-consistency) |
| E-6 | bug | `services/feedback.py:117` | `dismiss` deletes the SavedRepository without recording an `unsaved` event → the append-only event log shows the repository as still saved; save analytics overcount. | fixed (recommendation-consistency) |
| E-7 | bug | `services/feedback.py:73` | `viewed` de-duplication is check-then-insert without a lock → two concurrent views (StrictMode double effect, two tabs) both store an event. | fixed (recommendation-consistency) |
| E-8 | bug | `recommendations/management/commands/evaluate_ranking.py:183` | `--json` writes without creating the parent folder or catching `OSError` → raw traceback for `--json ../../judging/new/report.json`; the other commands create output folders (CLAUDE.md §7). | fixed (evaluation-tooling-integrity) |
| E-9 | bug | `services/evaluation/sheet.py:155` | `_languages` sums byte counts, but the dataset format allows `null` bytes (`_count`) → `TypeError` in `benchmark_sheet`, not caught (only OSError/ValueError/KeyError/SheetError) → traceback. | fixed (evaluation-tooling-integrity) |
| E-10 | perf | `feedback/api.py:252` | Saved list prefetches every snapshot of each repository (up to `REPO_SNAPSHOT_HISTORY`) to read only the newest. | fixed (performance-cleanup) |

### F: Frontend (`apps/frontend/src`)

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| F-1 | bug | `features/sync/api.ts:24` | `useSyncStatus` invalidates every `['profile']` query on each status fetch whose latest job is COMPLETED, which is the steady state. Window focus or remounting `/app` (back from a detail page) refetches skills, interests, repositories, recommendations, discovery and saved lists every time, and can refetch the list mid-dismiss so the card flickers back. Invalidate only when the job id or status changes, as `useRecommendationStatus` does. | fixed (frontend-correctness) |
| F-2 | bug | `features/feedback/api.ts:259` | Saved and hidden lists fetch one page of `page_size=100` with no pagination → a user with more than 100 saved or hidden projects silently cannot see or restore the rest. | fixed (frontend-correctness) |
| F-3 | bug | `features/recommendations/RecommendationList.tsx:134` | `?page=N` past the last page (after dismissals or a regeneration shrinks the list, or a shared link) gets a DRF 404 → "Could not load recommendations. Please refresh the page."; refreshing keeps the page in the URL, so it never recovers. Dismissing the only card on the last page shows the empty-state text although earlier pages exist. | fixed (frontend-correctness) |
| F-4 | bug | `features/feedback/RecommendationActions.tsx:287` | Save button is not disabled while pending; a fast double click sends POST and DELETE concurrently with no ordering guarantee, and the first mutation's rollback restores a snapshot taken before the second → UI shows Saved while the server has it unsaved (or the reverse). | fixed (recommendation-consistency) |
| F-5 | bug | `features/recommendations/RecommendationCard.tsx:332` | "N relevant issues" links to `#relevant-issues`, but client-side navigation does not scroll to hashes and the target renders only after the detail query loads → user lands at the top of the page. | fixed (frontend-correctness) |
| F-6 | bug | `features/recommendations/RecommendationDetailPage.tsx:98` | Non-numeric or zero `:id` (also `IssueDetailPage.tsx:33`) disables the query, so `isPending` stays true → "Loading…" forever instead of a not-found message. | fixed (frontend-correctness) |
| F-7 | bug | `features/auth/RequireAuth.tsx:245` | Only `/auth/me` 401s redirect; with `staleTime` 60 s an expired session shows "Could not load ... Please refresh the page" on every panel instead of returning to sign-in. Handle 401 globally (QueryCache `onError`). | fixed (frontend-correctness) |
| F-8 | bug | `features/recommendations/RecommendationList.tsx:61` | `closeUndo` depends on `location`, so any filter change (new location) re-runs the `DismissUndo` effect and restarts the 10 s Undo timer. | fixed (frontend-correctness) |
| F-9 | perf | `features/recommendations/api.ts:235` | The invalidation effect runs in every observer of `useRecommendationStatus`, including the passive one in `usePipelineStage` → two invalidations per finished generation; the second cancels the first list fetch and restarts it. | fixed (frontend-correctness) |

### G: Scripts, compose, CI, Dockerfiles, `.env.example`

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| G-1 | bug | `scripts/stop.mjs:151` | Node runners match `scripts/(start\|backend\|worker\|beat\|redis).mjs` without checking the repository path (their command lines are relative) → `npm run stop` kills `node scripts/start.mjs` and friends of any other project on the machine. CLAUDE.md §6 promises "kills this repo's stack only". Check the process's cwd or pass a marker (`CF_STACK_PID`/repo path) on the runner command line. | fixed (dev-scripts-checks) |
| G-2 | bug | `scripts/redis.mjs:81` | No SIGHUP handler; closing the console ends the runner without killing the detached `wsl.exe sleep infinity`, and `npm run stop` never matches `wsl.exe` → the distro and Redis stay awake indefinitely. | fixed (dev-scripts-checks) |
| G-3 | bug | `scripts/child.mjs:58` | POSIX `process.kill(-child.pid, signal)` throws ESRCH if the group already exited → uncaught exception inside the signal handler, and the `killTree` fallback is never scheduled. Spawn `error` (bad `UV_BIN` path) is also unhandled → crash with a stack trace instead of a message. | fixed (dev-scripts-checks) |
| G-4 | bug | `scripts/wait-port.mjs:128` | `net.connect` has no timeout; against a host that drops packets (remote `REDIS_URL`, firewalled WSL IP) one attempt waits the OS TCP timeout (21 s to 2 min) → the documented `timeoutMs` deadline is overshot several times over. | fixed (dev-scripts-checks) |
| G-5 | gap | `docker-compose.yml:68` | Frontend service loads the whole `.env` (`GITHUB_CLIENT_SECRET`, `TOKEN_ENCRYPTION_KEYS`, `DJANGO_SECRET_KEY`) though it needs only `VITE_*` → secrets present in the frontend container's environment, contrary to the least-exposure rule for secrets (CLAUDE.md §3). | fixed (security-hardening) |
| G-6 | bug | `docker-compose.yml:43` | Redis published on host port 6379 (all interfaces, no auth) collides with the WSL Redis that `npm start` uses on this machine and exposes the broker to the LAN. Bind `127.0.0.1:` or drop the port mapping. | fixed (security-hardening) |
| G-7 | bug | `scripts/beat.mjs:146` | Beat schedule file has a fixed name in the OS temp dir → two checkouts (or a worktree) share and overwrite one schedule state file. Include a hash of `root`. | fixed (dev-scripts-checks) |
| G-8 | gap | `.github/workflows/ci.yml:88` | `cancel-in-progress: true` also applies to pushes to `main` → a quick second push cancels the first commit's run, so a broken commit on `main` can go unchecked. Limit cancellation to pull requests. | fixed (dev-scripts-checks) |
| G-9 | gap | `scripts/check-version.mjs:170` | Checks only the top-level `version` of each `package-lock.json`, not `packages[""].version`, which `npm ci` also compares → a half-updated lock passes the check. | fixed (dev-scripts-checks) |
| G-10 | cleanup | `scripts/setup.mjs:35` | Setup runs `npm install` in `apps/frontend` (can rewrite the lockfile) where CI uses `npm ci` → a local setup can leave an uncommitted lockfile diff that CI does not reproduce. | fixed (dev-scripts-checks) |

### H: Platform, settings, migrations, remaining frontend, test gaps

Paths under `apps/backend/` unless they start with `apps/frontend/`. `makemigrations --check` is clean.
H-2 and H-4 confirmed by the reviewer (DRF `get_ident` source; `redact()` probes).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| H-1 | bug | `config/settings/base.py:157` | DRF throttles count in the Redis cache → Redis down = every API request (health included) 500s after the 5 s socket timeout, twice per request. Breaks "reads come from PostgreSQL" and degrade-gracefully. Tests use LocMemCache, so it's never exercised. | fixed (github-error-resilience) |
| H-2 | bug | `config/settings/base.py:148` | `NUM_PROXIES` unset → DRF keys throttles on raw `X-Forwarded-For` → a random XFF per request bypasses anon (60/min) and auth (10/min) limits. | fixed (security-hardening) |
| H-3 | bug | `core/logging.py:41` | `RedactSecretsFilter` calls `record.getMessage()` outside logging's error guard → a bad log call (missing arg) raises into the caller, crashing a task step or turning a handled error into a 500. | fixed (security-hardening) |
| H-4 | gap | `core/logging.py:15` | Redaction misses `key='value'` reprs, `'state'` in dict/JSON, and `Authorization: token <non-gh>` → client secret or OAuth state can reach logs. Tests cover only unquoted and `gh*_` cases. | fixed (security-hardening) |
| H-5 | bug | `apps/frontend/src/main.tsx:9` | Production QueryClient keeps default `retry: 3` for 4xx → normal `404 not_analyzed` shows "Loading…" about 7 s over 4 requests; 401s and 429s retried too. Tests set `retry: false`, which hides it. | fixed (frontend-correctness) |
| H-6 | gap | `config/settings/production.py:7` | System checks (token keys, weights) never run under gunicorn or the Celery worker → misconfigured deploy starts and fails per request (empty `TOKEN_ENCRYPTION_KEYS` → 500 on sign-in). | fixed (security-hardening) |
| H-7 | gap | `core/checks.py:52` | No checks for `EXPERIENCE_THRESHOLDS`, `SYNC_MAX_ATTEMPTS`, `SYNC_STALE_AFTER_SECONDS`, `JOB_RECOVERY_INTERVAL_SECONDS`, GitHub caps, etc. → e.g. interval 0 = `recover_stale_jobs` hot loop; scalar threshold = every analysis fails. | fixed (dev-scripts-checks) |
| H-8 | gap | `apps/frontend/src/routes/PrivacyPage.tsx:15` | Says the GitHub identifier is kept until disconnect, but `User.username = gh_<github_id>` survives disconnect. | fixed (privacy-deletion-finality) |
| H-9 | gap | `apps/frontend/src/routes/PrivacyPage.tsx:11` | "What we store" omits SyncJob history, candidates and search queries, `AuditEvent.ip_hash` (kept after account deletion), session rows. | fixed (privacy-deletion-finality) |
| H-10 | bug | `recommendations/migrations/0003_seed_v2_deterministic.py:59` | v2 seed deactivates whatever config is active, not just v1 → an operator-chosen config silently replaced by v2 on upgrade. | fixed (dev-scripts-checks) |
| H-11 | bug | `recommendations/migrations/0002_seed_v1_deterministic.py:40` | Re-applying 0002 after unseed checks `exists(active)` including v1 itself → v1 deactivated, no active config, generation fails. Unseed paths untested. | fixed (dev-scripts-checks) |
| H-12 | gap | `config/celery.py:5` | Celery and `manage.py` default to development settings, `wsgi.py` to production → with the variable unset, worker and beat run `DEBUG=True` without the `REDIS_URL` guard. | fixed (security-hardening) |
| H-13 | gap | `config/urls.py:25` | Only `handler404`/`handler500` set → Django-level 400/403 (DisallowedHost, RequestDataTooBig, PermissionDenied) return HTML, breaking the error envelope. | fixed (security-hardening) |
| H-14 | bug | `core/api.py:11` | `HealthView` is throttled (60/min per IP) → load balancer probes get 429 and mark a healthy instance down. | fixed (security-hardening) |
| H-15 | bug | `config/settings/production.py:13` | `SECURE_SSL_REDIRECT` without health exemption → plain-HTTP probes get 301. `SECURE_PROXY_SSL_HEADER` trusted unconditionally. | fixed (security-hardening) |
| H-16 | gap | `config/settings/production.py:15` | HSTS `includeSubDomains` + `preload` hard-coded, 1-year max-age → irreversible on a shared parent domain. Make opt-in. | fixed (security-hardening) |
| H-17 | bug | `apps/frontend/src/features/profile/languages.ts:13` | "Other" summed from shares pre-rounded to 2 decimals → many small languages become 0, "Other" disappears, rows show "0%". | fixed (frontend-correctness) |
| H-18 | gap | `apps/frontend/package.json:1` | No Playwright config, specs or CI job despite CLAUDE.md §4; OAuth → onboarding → dashboard, dismiss/undo, delete flows covered only by mocked unit tests. | fixed (frontend-correctness) |
| H-19 | gap | `tests/test_api_platform.py:82` | No tests for: failing cache backend, migration unseed, malformed log call or quoted redaction, Django-level 400, privacy page vs `data_deletion`. | fixed (dev-scripts-checks) |
| H-20 | perf | `config/settings/base.py:182` | `CELERY_RESULT_BACKEND` stores every task result in Redis, never read. Set `CELERY_TASK_IGNORE_RESULT`. | fixed (dev-scripts-checks) |

### Not yet reviewed

Nothing major. Every area has had one unverified review pass.

### Cross-cutting themes

All twelve closed by 0.12.10 (A-10 a false positive).

1. **No ownership fencing** for claims (B-2, B-10, C-3, C-4, C-19): one claim-token mechanism fixes jobs and repositories.
2. **Deletion not final** (A-1, B-4): running work must re-check existence or cancellation before writing.
3. **Lock ordering and deadlocks** (B-3, C-7, D-3, D-4, A-10).
4. **GitHub status mapping** (A-2, A-3, A-4, A-5, C-1, C-6): 301, secondary 403 and 451 are mis-classified, so one repository fails a whole job.
5. **Stale ≠ gone** (D-1, D-14, C-8, E-4): staleness changes what users see and what gets exported.
6. **Baseline tooling** (R-1, R-2, E-1, E-2): `--write-baseline` can write a baseline CI then rejects. Fix together in `baseline.py` + `evaluate_ranking`, before K-1.
7. **Save/dismiss consistency** (D-2, D-3, D-10, E-5, E-6, F-4): one lock order and one "is dismissed" check for save, dismiss and persist.
8. **Privacy of deleted or exported data** (A-7, A-8, E-3, G-5): GitHub identity survives deletion; benchmark export re-identifiable. **Settle E-3 before committing benchmark-v2.**
9. **Frontend cache churn** (F-1, F-9, H-5): invalidate on job transitions only; no retry on 4xx.
10. **Redis as hidden hard dependency** (H-1, H-14, H-20, A-16): throttles and results make Redis required for plain reads.
11. **Production hardening** (H-2, H-6, H-12, H-13, H-15, H-16, G-5, G-6): settings drift between tiers, spoofable client IP, unchecked config.
12. **Secrets in logs** (H-3, H-4): redaction gaps plus a filter that can crash its caller.

## Verification notes

**False positive**
- A-10: `update_or_create` goes through `get_or_create`, which catches the IntegrityError and re-gets on `github_id`. Only a full_name clash with a different github_id still raises (a rename race, already covered by C-2).

**Partial: real defect, narrower scope**
- A-4: dropped contribution evidence is real. The languages step only fails if a rename happens between listing and the languages call.
- A-11: needs this user's repository renamed away and the name re-created mid-sync. Not permanent: the next sync re-plans.
- A-12: other sessions see only an unconnected, empty account. Low severity.
- B-4: recreation only succeeds when all evidence is README-only or on surviving shared repositories (deferred FKs abort otherwise).
- B-7: stale jobs are requeued by recovery, so the user does get re-analyzed. Only the "already active" report is misleading.
- B-8: millisecond window. The `.first()`→None half is harmless because callers ignore the return value.
- B-10: needs beat down, or a redelivery that lands before recovery.
- B-11: a cancel with a live worker self-heals. Only dead-worker jobs keep a spinner.
- C-3, C-4, C-19: only reachable when an analysis takes more than 10 min (pathological latency).
- C-5: needs a queued readme task to run after the repository was marked FAILED (race).
- D-1: saved items do **not** vanish (the Saved list is keyed on repository). The rest holds: recommendations drop out on the hourly stale sweep and come back with new ids, or never without app credentials.
- D-7, D-8: latent. Reachable only with a config that gives a weight of 0; no seeded config does. D-7 fixed in 0.12.14.
- D-9: spec-mandated (issue-matching spec: "technology match or an approachability label"). The real defect is the wording "matches your profile".
- D-14: discovery's pool-step completion starts a generation that empties the list. Stuck only when D-5 reuse or a failed generation interferes.
- D-15: the edit part holds; activation already re-validates, so an invalid config fails loudly.
- E-5: a concurrent race rolls back with a 500 (FK), no orphan. The orphan window is two lines wide.
- E-9: exports never hold null bytes. Needs a hand-made `--export`.
- F-7: the redirect happens on the next `/auth/me` refetch (after 60 s stale, on focus or mount), not never.
- G-3: the ESRCH race is narrow; the spawn-error half is unreachable (`uv.mjs` probes candidates).
- G-4: overshoot is one OS connect timeout (about 21 s on Windows), not "several times over".
- G-8: the surviving run tests the tip, which includes the earlier commit. Only per-commit attribution is lost.
- G-9: the gap is real, but `npm ci` doesn't compare the root version.
- H-6: `migrate` runs system checks, so a deploy that migrates first catches them.
- H-13: only the 400 part holds; DRF already turns PermissionDenied into the envelope.
- H-14: normal probe rates (every 5–30 s) stay under 60/min.
- H-16: max-age is configurable (0 disables); preload does nothing until the domain is submitted.
- R-10: documented design ("a query is planned in all bands or not at all"); waste is at most bands−1 requests.
- R-12: refreshes re-run `eligibility()` within hours (6 h issues staleness), unless app credentials are missing.

**Worse than reported**
- B-13: repository analysis re-raises any exception, so one deeply nested manifest in a discovered repository fails every discovery run that touches it, for every user.

**Corrected locations** (cited lines were stale)
- R-14 `services/evaluation/export.py:80` + `sheet.py:118`; E-1 `baseline.py:32-41`; E-10 `feedback/api.py:119-123`.
- C-3 `lifecycle.py:46-95`; C-9 `repositories/tasks.py:111`; C-15 `tasks.py:71-90`; C-16 `tasks.py:40-92`; C-22 `lifecycle.py:76-78`.
- D-11 `classify.py:38-46`; D-12 `classify.py:114`; D-17 `config.py:171`; D-18 `classify.py:65,125`.
- G-1 `scripts/stop.mjs:10,43`; G-2 `redis.mjs:60-62`; G-4 `wait-port.mjs:10,17`; G-7 `beat.mjs:22`; G-8 `ci.yml:8-10`.
- H-11 `0002_seed_v1_deterministic.py:40,46`; H-13 `urls.py:55-56`.

**Found during verification, not yet rows**
- G-6 extra: Postgres published on `5433` with password `contribfinder` in compose.
- H-1 extra: `cached_db` sessions also hit Redis. Fixed with H-1 (sessions now use the database backend).
- G-10 extra: `uv sync` in setup is not `--frozen` either.

## Batch 5 review (2026-10-21)

Source: `code-review` over the uncommitted `github-error-resilience` diff (v0.12.5), plus the
`/simplify` altitude pass (V-1 overlap). Verified against the code 2026-10-21 (V-5, V-6 partial: narrow windows; V-8 matches the metadata convention) and fixed in 0.12.5 before commit. Paths under
`apps/backend/`. Ranked most severe first. Type: bug · gap · design · cleanup.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| V-1 | design | `services/repositories/analysis.py:69` | `ERROR_CODES` maps bare `KeyError`/`ValueError`/`TypeError`/`IndexError` → FAILED `invalid_response`. Also catches transient bad bodies (truncated/HTML 200 → `JSONDecodeError`), corrupt ETag cache entries and programming bugs → every analyzed repository FAILED and ineligible for `REPO_FAILED_RETRY_HOURS`, logged at INFO. Deeper fix: raise typed `GitHubInvalidResponse(GitHubClientError)` at the `.json()`/`from_api` boundary in `services/github`; sync's `SKIPPABLE` and `oauth.fetch_identity` then get it for free. Module docstring also outdated. | fixed (github-error-resilience) |
| V-2 | bug | `services/github/client.py:545` | Redirect guard in `_send` compares host only, not scheme/port. `Location: http://api.github.com/...` passes → bearer token sent in cleartext. Compare origin (scheme, host, port) with `GITHUB_API_BASE_URL`. | fixed (github-error-resilience) |
| V-3 | design | `core/throttling.py:55` | Fail-open applies to every throttle, incl. anon throttle on `/auth/github` and scoped `/profile/sync`. Redis down (or induced cache errors) → no rate limiting per process for `THROTTLE_CACHE_BACKOFF_SECONDS`, renewed each error → OAuth-state churn, sync flooding into GitHub. Sensitive scopes: fail closed or in-process fallback counter. Revisits design D9. | fixed (github-error-resilience) |
| V-4 | gap | `repositories/tasks.py:98` | `_refresh`'s app-credentials `GitHubAuthError` branch stays log-only (task 5.3), so `refresh_failed_at` stays null → rejected/rotated `GITHUB_CLIENT_SECRET` requeues the same `REPO_REFRESH_BATCH` every beat, the loop C-9 fixed for other errors. | fixed (github-error-resilience) |
| V-5 | bug | `services/repositories/lifecycle.py:116` | `record_refresh_failure` runs as a separate UPDATE after `release()`. Another analysis can claim + complete in between → stale `lifecycle_error` and `refresh_failed_at` land on fresh RECOMMENDABLE data, next refresh delayed up to 60 min. Record inside `release()` under the held claim token. | fixed (github-error-resilience) |
| V-6 | bug | `repositories/tasks.py:81` | `.exclude(refresh_failed_at__gte=...)` applies to the whole backlog query → also hides abandoned claims (dead worker, stuck FETCHING/REFRESHING) and DISCOVERED rows for up to `REPO_REFRESH_RETRY_MINUTES`. Scope it to the STALE branch. | fixed (github-error-resilience) |
| V-7 | bug | `services/github/oauth.py:113` | `str(data["login"])` turns JSON `null` into `"None"`, passing the non-empty check → account upserted with username `"None"`. Check `isinstance(login, str)` and non-empty before converting. | fixed (github-error-resilience) |
| V-8 | cleanup | `services/github/sync.py:187` | `languages_skipped` written to job metadata, never read (no code, API or UI). Spec-required (task 2.1), so: surface it (step detail or warning) or drop it from the spec. | wontfix (internal diagnostics, like `repos_capped`; spec-required) |
| V-9 | cleanup | `services/github/sync.py:190` | `/simplify` altitude: `_step_topics` re-checks existing pks to work around topics being written a step later from `job.metadata["repo_topics"]`. Writing topics in `_step_repositories`' `job_write` removes the race (and rename re-points) and the metadata copy; `_step_topics` stays as a no-op step. Design accepted A-11 as partial. | fixed (github-error-resilience) |

## Batch 6 review (2026-10-21)

Source: `code-review` over the uncommitted `recommendation-consistency` diff (v0.12.6). Paths
under `apps/backend/`. All fixed in 0.12.6 before commit.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| W-1 | bug | `services/feedback.py` (`dismiss`) | Events referenced a recommendation a concurrent generation deleted → deferred FK fails at commit → dismiss 500. | fixed (recommendation-consistency) |
| W-2 | bug | `services/feedback.py` (`record`) | Same for `viewed` (and other events), with the profile lock widening the window. | fixed (recommendation-consistency) |
| W-3 | bug | `services/repositories/analysis.py` (`_store_issues`) | Only deleted issues were locked by pk; the unordered `bulk_update` of open issues could deadlock with persist's pk-ordered lock. | fixed (recommendation-consistency) |
| W-4 | perf | `services/ranking/freshness.py` | The sweep flagged running generations as due → `rerun_requested` → a redundant generation after every overlap. | fixed (recommendation-consistency) |
| W-5 | gap | `services/jobs.py` | A retry reloads its inputs but kept the rerun flag (extra run). A flag lost on permanent failure stays an accepted risk (design). | fixed (recommendation-consistency) |
| W-6 | gap | `services/ranking/freshness.py` | A staleness mark overwrote the completion time of an analysis newer than the last generation → missed regeneration. | fixed (recommendation-consistency) |
| W-7 | gap | `services/ranking/freshness.py` | A generation that keeps failing was restarted every sweep (30 min) forever. | fixed (recommendation-consistency) |
| W-8 | bug | `services/ranking/service.py` | An issue re-analyzed (not deleted) between ranking and storing passed the check → reasons from stale analysis. | fixed (recommendation-consistency) |
| W-9 | gap | `services/feedback.py` (`save`) | Dismissal enforced only through the recommendation's deletion. | fixed (recommendation-consistency) |
| W-10 | perf | `services/feedback.py` (`record`) | View de-duplication waited on the profile lock held by a whole persist. | fixed (recommendation-consistency) |

## Batch 7 review (2026-10-21)

Source: `code-review` over the uncommitted `discovery-repository-data` diff (v0.12.7). Paths
under `apps/backend/`. Verified against the code; fixed in 0.12.7 before commit unless noted.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| X-1 | bug | `services/repositories/lifecycle.py` (`release_name`) | A holder that gave up its name stayed eligible: recommended as `a/b~5` with a URL that now opens another repository. Now ineligible `name_released` (INDEXED) until resolved. | fixed (discovery-repository-data) |
| X-2 | bug | `services/discovery/service.py` (`_prune_discoveries`) | A run with no search (empty plan) or a query rejected with 422 pruned valid records, leaving candidates with no provenance. | fixed (discovery-repository-data) |
| X-3 | gap | `services/discovery/service.py` (`_step_pool`) | Pool writes (prune, not_code, re-check, eviction) ran outside `job_write`: a cancelled or reclaimed run kept writing. | fixed (discovery-repository-data) |
| X-4 | perf | `services/repositories/analysis.py` (`run`) | A queued refresh with nothing stale left still completed and stamped a transition → needless regenerations for every developer. Now released, SKIPPED. | fixed (discovery-repository-data) |
| X-5 | bug | `services/discovery/service.py` (`_record`) | One query matching a repository in both bands in one run kept the later band's rank. Now the better rank within a run. | fixed (discovery-repository-data) |
| X-6 | bug | `services/repositories/backlog.py` (`queue_batch`) | Overlapping backlog runs could queue the same rows. Now selected `skip_locked` and stamped in one transaction. | fixed (discovery-repository-data) |
| X-7 | design | `services/github/storage.py` (`upsert_repository`) | `release_name` locks a second row outside GitHub ID order; deadlock needs a rename race plus two concurrent runs (accepted in design D3; the old delete had the same shape). | wontfix (accepted) |
| X-8 | cleanup | `services/discovery/service.py` (`_step_pool`) | `_remove_not_code` and `recheck_eligibility` both load the pool with topics and dependencies. Not one pass: they cover different lifecycles. | wontfix (batch 11 if it matters) |
| X-9 | design | `services/discovery/service.py` (steps) | A suspected list found `not_code` by this run's analysis keeps its pool slot until the next run (pool runs before analysis, D7). | fixed (post-analysis-pool-cleanup, 0.12.26: the analysis step ends by removing the lists it found) |
| X-10 | — | `core/checks.py` | "W003 when the budget is below the band count": E025 already errors there and W003 is skipped. | false-positive |
| X-11 | perf | `services/repositories/lifecycle.py` (`complete`) | Eligibility re-reads the topics and dependencies the analysis just wrote: 1–2 queries per analysis. Passing them in needs an annotation set by hand (skipped in the `/simplify` pass). | fixed (performance-cleanup) |
| X-12 | cleanup | `tests/` | `developer`, `single_band` and `client` fixtures are copied across `test_discovery_service.py`, `test_discovery_repository_data.py`, `test_repository_analysis.py` and `test_issue_ingestion.py`; move them to `conftest.py` (`fresh_repo` and `analyze` already moved to `repo_fixtures.py`). | fixed (performance-cleanup) |

## Batch 9 review (2026-10-21)

Source: `code-review` over the uncommitted `frontend-correctness` diff (v0.12.8). Paths under
`apps/frontend/src/` unless noted. Y-1…Y-5 and Y-8 fixed in 0.12.8 before commit, each with a
test that fails without the fix (Y-8 checked by `npm run e2e`).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| Y-1 | bug | `app/queryClient.ts` (401 handler) | Log out, disconnect or delete account while a poll is in flight: its 401 called `endSession` → "Your session ended" after a deliberate sign-out. Sign-out mutations now carry `meta.endsSession` (`features/auth/api.ts`), which suspends the handler until it fails or `/auth/me` succeeds again. | fixed (frontend-correctness) |
| Y-2 | bug | `app/jobTransitions.ts` (`fetchStatusAndRefresh`) | The status `queryFn` awaited the whole refresh cascade (which includes other status queries); one slow or hung derived request froze the status and its polling. Refresh is now started, not awaited. | fixed (frontend-correctness) |
| Y-3 | bug | `lib/useScrollToHash.ts` | `decodeURIComponent` threw on a malformed hash (`#%E0`) inside an effect → blank page. Falls back to the raw hash. | fixed (frontend-correctness) |
| Y-4 | bug | `features/recommendations/RecommendationList.tsx` (page recovery) | Dismissing the last card on page N moved to page N−1 from the optimistic cache; a failed dismissal restored the card on a page no longer shown. Recovery now waits for pending dismissals (`dismissMutationKey`). | fixed (frontend-correctness) |
| Y-5 | bug | `lib/utils.ts` (`positiveId`) | `Number()` accepted `0x1f`, `1e2`, ` 7` → `/app/recommendations/0x1f` fetched id 31. Now decimal digits only. | fixed (frontend-correctness) |
| Y-6 | design | `app/queryClient.ts` (`DERIVED_STALE_TIME_MS`) | Data changed by jobs no status query watches (a standalone `profile_analysis` from `reanalyze_profiles`, a backend repository refresh) stays cached up to 5 min where it used to refetch on mount. Intended trade-off of F-1; fix if it shows in use (watch the analysis job too, or a shorter stale time for profile and detail; `ideas.md` §14). | fixed (0.12.27, `data-versions`: `GET /api/v1/sync/versions` returns when the GitHub data, the profile and the recommendations last changed; the SPA asks on mount, focus, route change and after a finished job, and refetches only the areas that changed) |
| Y-7 | bug | `features/feedback/api.ts` (`usePagedList`) | Saved and hidden lists page by number: a save or unsave in another tab between "Show more" clicks shifts the pages → a duplicated entry (duplicate React key) or a skipped one. Needs cursor or `saved_at`-keyset pagination in the API, or de-duplication by `repository_id` (`ideas.md` §14). | fixed (freshness-paging-seed: keyset `cursor` on `/saved` and `/dismissed`) |
| Y-8 | bug | `apps/backend/config/settings/e2e.py` | Claimed self-contained but `base.py` read the whole local `.env` (`NUM_PROXIES`, `ALLOWED_HOSTS`, `DISCOVERY_MAX_POOL`, ranking settings used by the seed): local e2e differed from CI. The runner (`scripts/e2e-backend.mjs`) passes only `DATABASE_URL` from `.env` and sets `DJANGO_READ_DOTENV=0`, which `base.py` honors. | fixed (frontend-correctness) |
| Y-9 | cleanup | `apps/backend/e2e/management/commands/e2e_seed.py` | An installed app's command imports `tests.repo_fixtures`; a test-helper refactor breaks `npm run e2e` while pytest stays green. Move the shared seeding helpers to a module both use. | fixed (performance-cleanup) |
| Y-10 | cleanup | `app/app.test.tsx` (`count`) | Reimplements `callsTo` from `features/feedback/feedback.test.tsx`; move one helper to `test/render.tsx`. | fixed (performance-cleanup) |

## Batch 10 review (2026-10-21)

Source: `code-review` over the uncommitted `dev-scripts-checks` diff (v0.12.9). Z-2, Z-3, Z-6 and
Z-7 fixed in 0.12.9 before commit, each with a test where one can run locally (Z-2 is CI config).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| Z-1 | design | `recommendations/migrations/0003_seed_v2_deterministic.py` (`seed`) | `operator_choice` ignores v1, so re-applying 0003 after a rollback activates v2 over an operator who deliberately chose v1 (for example because the benchmark does not favour v2). Matches the spec ("while no configuration or only `v1-deterministic` is active", design D8); changing it needs a spec change, and it only happens on a rollback. | fixed (freshness-paging-seed: the seed leaves activation alone when v2 is already stored; spec changed) |
| Z-2 | gap | `.github/workflows/ci.yml` (`concurrency`) | A group holds one pending run, and a newer one replaces it even with `cancel-in-progress: false` → three quick pushes to `main` skipped the middle commit (G-8 fixed only half). Pushes now group by `github.sha`; pull requests by ref, with cancellation. | fixed (dev-scripts-checks) |
| Z-3 | bug | `scripts/check-version.mjs`, `scripts/wait-port.mjs` (main guard) | `process.argv[1] === fileURLToPath(import.meta.url)` is false when the repository is reached through a symlink or junction (Node resolves `import.meta.url`, not `argv[1]`) → `npm run check:version` printed nothing and exited 0 with mismatched versions. Both use `isMain(import.meta.url)` (`env.mjs`, compares real paths). | fixed (dev-scripts-checks) |
| Z-4 | bug | `scripts/stop.mjs` | The process list is read before the records: a runner that starts in between has a record but no listed process → its record is deleted as stale, and a later stop cannot find it. Needs `npm run stop` during `npm start`'s spawn (milliseconds). Read records first. | fixed (performance-cleanup) |
| Z-5 | cleanup | `scripts/redis.mjs` (keep-alive record) | The comment says the detached `wsl.exe` is outside the runner's tree; on Windows its parent is still the runner, so `taskkill /T` reaches it too. A failed spawn (`pid` undefined) writes `redis-undefined.json`, later dropped as stale. Fix the comment; record only a real pid. | fixed (performance-cleanup) |
| Z-6 | bug | `recommendations/migrations/0002_seed_v1_deterministic.py` (`unseed`) | v2 with recommendations survives 0003's unseed (inactive, v1 activated); 0002's unseed then deleted v1 → v2 stored, nothing active, generation fails. v1 unseed now keeps an active v1 while any other configuration is stored. | fixed (dev-scripts-checks) |
| Z-7 | test | `scripts/env.test.mjs` | `'C:\work\contribfinder'` written with single backslashes is `C:workcontribfinder` (`\w` is no escape) → the schedule-name test never saw a Windows path. Uses `String.raw` now. | fixed (dev-scripts-checks) |
| Z-8 | bug | `scripts/stack.mjs` (`ownedByPath`, `recordMatches`) | Matching needs `proc.name === 'node'`; on Linux `ps comm=` may report a newer Node's main thread name (`MainThread`) → `npm run stop` finds nothing there. Unverified; Windows (CIM `Name`) unaffected. Take the executable from `args=`. | fixed (performance-cleanup) |
| Z-9 | perf | `scripts/stop.mjs` (kill loop) | Every matched process gets its own `taskkill /T /F` (`killTree`, `spawnSync`), though killing `start` already ends its descendants → about 50–150 ms per mostly dead pid. Skip descendants of chosen pids (needs parent pids from CIM/`ps`) or pass all pids to one `taskkill`. Skipped in the `/simplify` pass (shared `killTree`). | fixed (performance-cleanup) |
| Z-10 | cleanup | `tests/test_config_checks.py` | `EXPERIENCE_THRESHOLDS` tests live in a new file instead of `test_profiling_config.py` (whose `test_default_config_is_valid` overlaps `test_defaults_pass`), and `ids()` is now defined in five test modules. Move the tests; share `ids` from one helper. Skipped in the `/simplify` pass (outside the diff). | fixed (performance-cleanup) |

## Batch 11 review (2026-10-22)

Source: `code-review` over the uncommitted `performance-cleanup` diff (v0.12.10). Q-1, Q-2, Q-4,
Q-5, Q-7, Q-8 and Q-9 fixed in 0.12.10 before commit; Q-3 and Q-6 accepted. Q-10…Q-12 are the
`/simplify` pass's skips (the pass's fixes, such as one `GREATEST` in the freshness filter and
`Backoff.call`, shipped in 0.12.10); they shipped in 0.12.11 (Q-10 in part).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| Q-1 | bug | `services/github/sync.py` (`_update_metadata`) | Still wrote the whole metadata (`{**job.metadata, **values}` + `save_progress`) → a key another writer stored meanwhile was dropped; C-20 changed discovery only. Uses `merge_metadata`. | fixed (performance-cleanup) |
| Q-2 | bug | `services/ranking/service.py` (summary) | Same pattern for the generation summary. `merge_metadata(job, values, **fields)` now also stores `steps` in the same write. | fixed (performance-cleanup) |
| Q-3 | design | `services/repositories/analysis.py` (`_store`) | Completion checks eligibility with the fetched topics, not the stored rows → would drift from `recheck_eligibility` if storage ever normalized topics. Today `replace_topics` only de-duplicates, as the returned list does. | wontfix (accepted: same values; revisit if topic storage changes) |
| Q-4 | perf | `services/ranking/score.py` (`score_candidate`) | D-20 made it call `contributions()` twice per candidate (once for parts, again in `weighted_score`). Both now sum through `_total(parts)`. | fixed (performance-cleanup) |
| Q-5 | cleanup | `services/ranking/explain.py` (`join`) | Third copy of the name-joining helper, missed by D-19. Uses `services.text.join_names`. | fixed (performance-cleanup) |
| Q-6 | design | `services/github/client.py` (304 `touch`) | One more Redis call per 304, and an entry confirmed by 304s never ages out. Intended: spec `github-data-sync` (A-17); the call goes through the cache backoff. | wontfix (by design) |
| Q-7 | privacy | `services/data_deletion.py` | The `github:ratelimit:{pk}` purge was dropped with the writer → keys from before the upgrade survived deletion for up to an hour. Purge kept for one release. | fixed (performance-cleanup) |
| Q-8 | bug | `scripts/stack.mjs` (`parsePs`) | Name from the first word of `args` → a node or python path with a space (`/home/a b/...`) named `a`, so `npm run stop` found nothing. Linux reads `/proc/<pid>/exe`; macOS keeps the first word (limit). | fixed (performance-cleanup) |
| Q-9 | docs | `CLAUDE.md` | Said no `github:ratelimit:*` key remains at all; now says it is no longer written and still purged for one release. ("rate-limit state in Redis" was already removed.) | fixed (performance-cleanup) |
| Q-10 | perf | `repositories/queries.py` (`latest_snapshot`) | The sliced prefetch sends one row per repository but Postgres still window-sorts every snapshot of them (`ROW_NUMBER()`; the index lacks the `-pk` tie-break). Grows with `REPO_SNAPSHOT_HISTORY`. Skipped in the `/simplify` pass: needs a migration (`ideas.md` §16). | accepted (bounded; config-activation-loose-ends: on PostgreSQL 18 a `DISTINCT ON` rewrite still plans an incremental sort (0.4 ms for 40 repositories, 336 snapshots, seq/bitmap scans off); the window prefetch is bounded by `REPO_SNAPSHOT_HISTORY`. Stored activity stays `ideas.md` §16) |
| Q-11 | cleanup | `services/repositories/analysis.py`, `repositories/api.py` | The "newest snapshot" order `("-captured_at", "-pk")` is still written by hand in a filter and a subquery outside `latest_snapshot`. A shared ordering constant keeps the three equal. Skipped in the `/simplify` pass (outside the diff). | fixed (tooling-data-hygiene) |
| Q-12 | cleanup | `services/github/sync.py`, `services/discovery/service.py`, `tests/repo_fixtures.py` | One-line `_update_metadata` wrappers around `merge_metadata`, and a re-export shim of `e2e.builders` for 16 test imports. Skipped in the `/simplify` pass (churn, no behavior; `ideas.md` §16). | fixed (tooling-data-hygiene) |

## Batch 11 notes (2026-10-22)

Source: problems seen while implementing and verifying `performance-cleanup` (v0.12.10). None
fixed there: outside the batch's rows.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| P-1 | bug | `scripts/redis.mjs` (WSL keep-alive) | First `npm start` from Claude Code's Git Bash: keep-alive `wsl.exe` exited `3221225786` (`0xC000013A`, Ctrl+C exit) ~8 s after start → `concurrently` stopped the whole stack ("WSL keep-alive session ended … Redis may stop"). Second run stayed up 90 s; not reproduced. Maybe the shell's inherited Ctrl+C handling (CLAUDE.md §6 testing note), maybe a real stray console event. Check in an interactive console; decide whether a keep-alive exit must end the stack or be restarted. | accepted (2026-10-28). Fixed in part in tooling-data-hygiene: the runner restarts the keep-alive and logs the code in hex. Cause unknown: `0xC000013A` is the default handler's exit for Ctrl+C, Ctrl+Break or console close, and the new process group stops only Ctrl+C. Retest on 2026-10-28 (distro stopped, spawned as `redis.mjs` does from Claude Code's Git Bash) stayed up 60 s; the keep-alive `wsl.exe` starts a second `wsl.exe` and neither has a `conhost.exe`. Reopen if the restart message shows in use, then probe which event reaches either `wsl.exe` (CLAUDE.md §6 testing note). |
| P-2 | tooling | `apps/frontend` (`format:check`), `.gitattributes` | With `core.autocrlf=true` (Windows default) files check out CRLF; prettier wants LF → `npm run format:check` fails on untouched files (HEAD too). CI (Linux) unaffected. `prettier --check --end-of-line auto` passes. Fix: `.gitattributes` `* text=auto eol=lf`, or `endOfLine: "auto"`. | fixed (tooling-data-hygiene) |
| P-3 | test | `src/app/app.test.tsx`, `src/features/feedback/feedback.test.tsx` | Under load (other suites running, 82 s duration) 2 of 35 tests failed; rerun alone passed in 12 s. Likely `waitFor` default timeout. Flaky locally; not seen in CI. Find the two tests, raise their timeout or wait on the right signal. | fixed (config-activation-loose-ends: cause was AppShell's lazy `LanguageChart` (Recharts), whose first import blocks the event loop ~1 s inside whichever test is running; the test setup now preloads it. `does not retry a 429` 1.2–1.3 s → ~0.36 s; both files 5/5 under backend-suite load) |
| P-4 | tooling | `apps/frontend/package.json` (`api:export`) | Runs bare `uv`, not `scripts/uv.mjs` → `npm run api:sync` fails ("'uv' is not recognized") where uv is not on PATH, though `npm run manage` etc. find it. Route through `scripts/uv.mjs`. | fixed (tooling-data-hygiene) |
| P-5 | cleanup | `scripts/*.mjs` | Not prettier-clean (and unlinted); runner edits cannot follow a checked style. Same as `ideas.md` round 5 "lint `scripts/`". | fixed (tooling-data-hygiene) |

## 0.12.13/0.12.14 review (2026-10-23)

Source: `code-review` over the uncommitted 0.12.13 (`config-activation-loose-ends`) and 0.12.14
(batch 8 fixes) diff. S-1…S-5 fixed in 0.12.14 before commit; S-8 accepted; S-6 and S-7 open. S-9…S-11 are the
`/simplify` pass's skips (its fixes shipped in 0.12.14).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| S-1 | bug | `services/ranking/activation.py` | The active config was loaded and the judge run before the force check; a `ConfigError` or `DatasetError` raised `ActivationError` even with `--force`, so a broken benchmark or active config blocked the emergency rollback. Forced, a failed comparison is now recorded in `failures` (`not compared: ...`). | fixed (0.12.14) |
| S-2 | bug | `services/ranking/activation.py` | Active config and verdict read outside the transaction; two activations judged against the same active config could both commit, the last one unjudged against its real predecessor and audited with the wrong `previous_version`. The active row is re-read under the lock: a change is an `ActivationError` (try again), the target already active a no-op. | fixed (0.12.14) |
| S-3 | bug | `services/ranking/activation.py` (`benchmark_judge`) | Used `RECOMMENDATION_MIN_SCORE`/`RECOMMENDATIONS_TOP_N` from settings, so a local `.env` could change the verdict. Uses `baseline.MIN_SCORE`/`TOP_N`, as the baseline does. | fixed (0.12.14) |
| S-4 | bug | `services/ranking/activation.py` (audit) | `forced` was the flag, not whether the rule was bypassed: `--force` on an improvement audited `forced=True`. Now `forced` only when the verdict was not an improvement or not computed. | fixed (0.12.14) |
| S-5 | bug | `services/profiling/readme.py` (shields badges) | B-15 matched every segment but the color against the catalog → free-text messages (`code style-black`, `platform-linux`, `docs-go to site`) became README skills; `unquote` before the split made `%2D` a separator. The message now counts only with no label or a tech label (section-title words, `built/made/powered/written`); segments are split before decoding. | fixed (0.12.14) |
| S-6 | design | `recommendations/admin.py` (activate action) | The action runs `benchmark_judge` (`rank_pool` per developer, twice) inside the request, against CLAUDE.md §3.3 "long-running work runs in Celery"; an unexpected judge exception (not `DatasetError`/`ConfigError`) is a 500. Small today (benchmark-v1: 6 personas); grows with `benchmark-v2`. Options: a tracked job, or admin points to the command. | fixed (activation-command-only: no admin action; the change page names the command) |
| S-7 | bug | `feedback/api.py` (`KeysetPagination`) | Page mode (`?page=2`) rewrites `next` to a cursor but leaves DRF's page-based `previous` (`?page=1`); a client alternating them repeats or skips rows under concurrent saves. `cursor` plus `page` silently ignores `page`. Make page-mode `previous` null (as cursor mode), or reject the mix. API-visible: spec `recommendation-feedback`. | fixed (keyset-paging-links: `previous` always null; `cursor` with `page` is 400 `cursor_with_page`) |
| S-8 | perf | `src/features/recommendations/api.ts` | Every finished generation (freshness sweep, reruns) invalidates profile, skills and interests, refetching three unchanged queries; after a sync the profile is fetched twice. Intended by 0.12.12 (Y-6: every analysis ends in a generation); narrowing needs a status flag (`ideas.md` round 4 data versions). | narrowed (0.12.27, `data-versions`: a finished generation refetches the profile, skills and interests only when the `profile` data version changed; after a sync they are fetched once) |
| S-9 | design | `src/features/recommendations/api.ts`, status keys | Status keys live under `['profile']`, so a finished generation invalidates seven profile keys by hand; a new profile query left off the list stays stale up to 5 min. Move status keys to a `['jobs', ...]` namespace and invalidate the prefix. Skipped in the `/simplify` pass: outside the diff (`ideas.md` §17). | fixed (0.12.15: status keys `['jobs', 'recommendations']`, `['jobs', 'discovery']`; a finished generation invalidates `['profile']`, a finished sync `['profile']` and `['jobs']`) |
| S-10 | test | `src/test/setup.ts` | Only `LanguageChart` is preloaded; the next lazy component brings back P-3. The preload also costs ~1 s in every test file. One registry of lazy loaders (AppShell exports them), preloaded where AppShell renders. Skipped in the `/simplify` pass: would weaken the P-3 fix as written (`ideas.md` §17). | fixed (0.12.15: `src/app/lazyLoaders.ts` registry; AppShell lazy-loads through it, setup preloads every entry) |
| S-11 | perf | `feedback/api.py` (`KeysetPagination`) | No index covers `(user, saved_at, id)` / `(user, dismissed_at, id)`; a cursor page sorts all the user's rows. Small lists today. Skipped in the `/simplify` pass: needs a migration (`ideas.md` §17). | fixed (0.12.15: `saved_keyset_idx`, `dismissed_keyset_idx`, migration `feedback.0003`) |

## 0.12.23 review (2026-10-26)

Source: `code-review` (T-1…T-10) and the `/simplify` pass (its skips T-11…T-14) over the
uncommitted 0.12.14–0.12.23 diff. T-1…T-10 fixed in 0.12.23 before commit, with tests; the
`/simplify` fixes shipped too (CHANGELOG 0.12.23 "Changed (internal)"). `evaluate_ranking`
intervals and `baselines.json` did not move. A security review of the same diff found nothing.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| T-1 | bug | `RecommendationActions.tsx` (`DismissReasonMenu`) | While a dismiss was in flight only the toggle was disabled; items of an already open menu could send a second `POST /dismiss` (its reason dropped by `get_or_create`, a second Undo notice). The menu is closed while a dismiss is pending. | fixed (0.12.23) |
| T-2 | bug | `services/evaluation/feedback_report.py` | Dismissals without a recommendation snapshot went to `unattributed` before their reason was read, so their reasons were missing from the report. Now listed on the unattributed line (JSON `unattributed_dismiss_reasons`). | fixed (0.12.23) |
| T-3 | bug | `services/matching/issues.py` | The unknown-difficulty reason said "too few signals", but unknown also comes from signals that disagree: a reason not backed by what was computed. Now "Difficulty not estimated". | fixed (0.12.23) |
| T-4 | bug | `services/matching/issues.py` | An issue part with weight 0 still produced a reason (contribution 0); repository reasons skip those since 0.12.14. Reasons now need a contribution above 0 (spec `issue-matching`). | fixed (0.12.23) |
| T-5 | bug | `recommendations/models.py` (`ScoringConfig.save`) | Compared stored JSON with in-memory values: a tuple in `params` looked changed, so a description-only edit raised `ImmutableConfig`. Compared as stored JSON now. | fixed (0.12.23) |
| T-6 | bug | `services/evaluation/feedback_report.py` (`_bucket`) | Rank 0 (allowed by `PositiveIntegerField`) fell into `21+`. Counted as unattributed now; the schema side is T-12. | fixed (0.12.23) |
| T-7 | bug | `core/checks.py` (`core.E040`) | `min_votes` had no upper bound: above the most votes a level can get, every issue was unknown and difficulty filters stopped working. Bounded by `classify.MAX_LEVEL_VOTES` (from `LEVEL_VOTERS`); `core.W004` warns when a level becomes unreachable. | fixed (0.12.23) |
| T-8 | cleanup | `services/matching/issues.py` | A `by_technology` id set kept beside the relevant issues to recount `technology_count`. `MatchedIssue.mentions_technology` instead. | fixed (0.12.23) |
| T-9 | cleanup | `services/ranking/score.py` | `has_relevance` ran twice per candidate. The `/simplify` pass kept the second call (a `relevant=` override was a second way to set one field) and removed `is_relevant`. | fixed (0.12.23) |
| T-10 | cleanup | `services/evaluation/feedback_report.py` | The adjusted share filtered `share is not None` twice. Sums `(bucket, share)` pairs. | fixed (0.12.23) |
| T-11 | bug | `services/matching/issues.py` (`match_issues`) | Relevance still reads raw values (`tech > 0 or approach > 0`): with a technology weight of 0 an issue counts as relevant (and in `technology_count`) through a part that adds nothing, while its reasons skip that part. Changes `issue_fit`, so it must win on the benchmark (waited for K-1 until 2026-10-28). | fixed (0.12.32: `MatchedIssue.relevant` and `mentions_technology` come from the per-part contributions, as the reasons do; `issue-matching` spec "Issue relevance" edited directly, scenario "Part with weight 0". Every stored config has issue weights and approachability values above 0, so baselines did not move) |
| T-12 | design | `recommendations/models.py`, `feedback/models.py` (`rank`) | `PositiveIntegerField` stores 0; only the feedback report knows 0 is no rank. Add `CheckConstraint(rank__gte=1)` (null allowed on events). No rank 0 is written today. | fixed (0.12.29, `rank-constraint`: check constraints `recommendation_rank_positive`, `recommended_issue_rank_positive`, `feedback_rank_positive`; the migrations shift a group with a rank 0 up by one and empty an event's rank 0) |
| T-13 | design | `RecommendationActions.tsx` | Hand-built dropdown (~100 lines of focus and keyboard handling) instead of shadcn `dropdown-menu`. Design D3 of `dismiss-reasons` chose no new dependency for one menu. | wontfix (design D3; revisit with a second menu) |
| T-14 | cleanup | management commands | The "write JSON report" block (`mkdir`, `json.dumps`, `OSError` → `CommandError`) is copied in seven commands. Outside the diff. | fixed (0.12.33, `json-report-writer`: `core/reports.write_json`) |

## 0.12.24–0.12.30 review (2026-10-27)

Source: `code-review` over the then-uncommitted 0.12.24–0.12.30 diff (setup readiness through the
Content Security Policy), all committed with 0.12.31 in `43d3458`. U-1, U-2, U-3, U-5, U-6, U-7 fixed in 0.12.31 (`data-versions-fixes`)
before commit, with tests; `baselines.json` did not move. A `/simplify` pass of the same diff
followed (CHANGELOG 0.12.31 "Changed (internal)"; U-6 now fixed by a pure `queryFn`), and a
security review of the result found nothing (versions endpoint scoped per user, CSP only adds
headers, GitHub listings at fixed paths on the API origin, discovery metadata internal).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| U-1 | bug | `services/data_versions.py` (`github`) | Only completed syncs counted, so a sync that failed after storing repositories refreshed nothing (before 0.12.27 every finished job refreshed `['profile']`). | fixed (0.12.31: last finished sync, completed or failed; cancelled ignored) |
| U-2 | bug | `src/app/dataVersions.ts` (`AREA_KEYS`) | The hidden list was in no area, so a background refresh (rename, new description) never reached it. | fixed (0.12.31: in `recommendations`) |
| U-3 | bug | `services/discovery/service.py` (`_remove_not_code`) | Returned the flagged count, not the candidates deleted; its log counted cascaded discovery records. `pool_not_code` / `analysis_not_code` over-counted on a resumed step. | fixed (0.12.31: `RepositoryCandidate` count from `delete()`) |
| U-4 | perf | `routes/SignedInLayout.tsx` | Every route change and focus fetches `/sync/versions` (four queries, one aggregate). | accepted (by design: spec "Refresh derived data by data versions") |
| U-5 | perf | `features/discovery/api.ts` | A finished discovery refetched the data versions, which it cannot change. | fixed (0.12.31: generation status only) |
| U-6 | bug | `src/app/dataVersions.ts` (`refreshDataVersions`) | Two jobs finishing together cancelled the first versions fetch after it had started its invalidations; the second repeated them, so each area was fetched twice. | fixed (0.12.31: pure `queryFn`, comparison in an effect on the cached value; a test covers it) |
| U-7 | bug | `features/auth/api.ts` (`useDeleteGitHubData`) | `removeQueries` on the versions query while the signed-in layout still observed it. | fixed (0.12.31: `resetQueries`) |
| U-8 | design | `recommendations/migrations/0005_rank_positive.py` | The rank repair shifts a developer's ranks but not the feedback snapshots taken at them. | wontfix (no rank 0 was ever written, so nothing is shifted in practice) |

## 0.12.32–0.12.34 review (2026-10-28)

Source: `code-review` (M-1…M-8) and a `/simplify` pass (M-9…M-15, four reviewers on one diff)
over the then-uncommitted 0.12.32–0.12.34 diff (signal fixes, JSON report writer, dependency
audit). Fixes went into 0.12.34 before commit, with tests; `baselines.json` did not move. A
security review of the result found nothing (audit spawns fixed arguments, the workflow runs on
`pull_request` with a read-only token, report paths come from command flags only).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| M-1 | bug | `scripts/audit.mjs` (`auditPython`) | pip-audit drops a requirement whose environment marker is false on the host (verified: `requests==2.0.0 ; sys_platform == 'linux'` vanished on Windows), so Linux CI never audited Windows-only packages (`colorama`). | fixed (0.12.34: `withoutMarkers` strips markers from the export) |
| M-2 | bug | `scripts/audit.mjs` (`pythonFindings`, `failing`) | A package pip-audit skipped had no `fails`, so an unaudited dependency passed with exit 0. | fixed (0.12.34: skipped fails, printed `FAIL skipped`) |
| M-3 | bug | `scripts/audit.mjs` (`auditPython`) | `uvCommand()` throws a plain `Error`, so a missing uv printed a stack instead of uv.mjs's install advice. | fixed (0.12.34: wrapped as `AuditError`) |
| M-4 | design | `services/issues/classify.py` (`contribution_type`) | Earliest keyword wins: "Error in README example" is `bug_fix`, not `documentation`. | accepted (the D-11 trade-off, recorded with D-11) |
| M-5 | design | `core/reports.py` | `write_json` raises `CommandError`, so service code (`baseline.write`) cannot use it. | accepted (design D1 of `json-report-writer`) |
| M-6 | cleanup | `export_benchmark_developer`, `import_judgments`, `build_benchmark` | Write-error wording changed ("Cannot write the export" → "Export not written to …"). | accepted (intended; nothing quotes the old text) |
| M-7 | cleanup | four report commands | `out = options[...]` temporary before `write_json`; `/simplify` suggested returning the path. | wontfix (the name is used twice; returning it only moves the call into a print) |
| M-8 | design | `services/matching/issues.py` (`MatchedIssue`) | `relevant` and `mentions_technology` default to False, so one built outside `score_issue` is silently irrelevant. | wontfix (only `score_issue` builds one) |
| M-9 | cleanup | `scripts/audit.mjs` | A malformed npm report became an `AuditError`, a malformed pip-audit report a stack trace. | fixed (0.12.34: one `asAuditError` for both) |
| M-10 | cleanup | `services/issues/classify.py` | The enumerate index only broke ties that `min` already breaks by list order. | fixed (0.12.34: removed) |
| M-11 | cleanup | `import_judgments.py` | `Path()` around a path `write_json` takes as a string. | fixed (0.12.34) |
| M-12 | perf | `scripts/audit.mjs` (main) | The three audits run one after another. | accepted (seconds per CI run; would need an async runner) |
| M-13 | perf | `services/issues/classify.py` | Every keyword pattern runs on each title (about 6 searches per issue fetch). | accepted (negligible) |
| M-14 | reuse | `services/evaluation/baseline.py:69` | Writes JSON by hand without `ensure_ascii=False`. | accepted (`baselines.json` out of scope, design of `json-report-writer`) |
| M-15 | reuse | `scripts/audit.mjs` (`run`) | Second way to start the npm `.cmd` shim on Windows (`setup.mjs` is the first). | accepted (two call sites) |

## 0.12.35 review (2026-10-28)

Source: `code-review` (N-1…N-7) and a `/simplify` pass (N-8…N-10, four reviewers on one diff)
over the then-uncommitted labeled-issue fetch (0.12.35). N-1…N-3, N-8, N-9 fixed in 0.12.35
before commit, with tests; `baselines.json` did not move. A security review found nothing (labels
are `urlencode`d into the query; the host is fixed).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| N-1 | bug | `config/settings/base.py` (`ISSUES_ENTRY_LABELS`) | `env.list` keeps spaces after commas (verified), so `good first issue, help wanted` requested `labels= help wanted`, matched nothing, and `core.E041` passed. | fixed (0.12.35: names trimmed; E041 refuses surrounding spaces) |
| N-2 | bug | `services/repositories/analysis.py` (`_fetch`, `issues`) | The labeled listings ran without `_between_parts`, so a slow GitHub could miss a cancel or outlive the claim (result thrown away). | fixed (0.12.35: before each labeled listing) |
| N-3 | cleanup | `services/repositories/analysis.py` (`__all__`) | `merge_issue_pages` missing from the public names. | fixed (0.12.35) |
| N-4 | process | CLAUDE.md §7 ranking rule | A † idea shipped without a benchmark win or holdout. | accepted (design D6: the benchmark stores issues as data and cannot measure it; a read-only measurement is recorded instead) |
| N-5 | design | `services/github/client.py` (`label=`) | Exact label names only: `good-first-issue`, `E-easy` gain nothing. | accepted (non-goal; per-repository label discovery is a later idea) |
| N-6 | design | `services/repositories/analysis.py` | One failed labeled listing fails the whole issues part. | accepted (design D4: a partial set would delete the labeled issues stored last time) |
| N-7 | observability | `merge_issue_pages` | A labeled page that hits its cap is not recorded as truncated. | accepted (coverage only; `issues_truncated` describes the recent listing by spec) |
| N-8 | altitude | `config/settings/base.py` | N-1's trim covered one setting; `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS` and `TOKEN_ENCRYPTION_KEYS` kept the space in `a, b` too. | fixed (0.12.35: one `env_list` helper trims and drops empty items for every list setting) |
| N-9 | cleanup | `analysis.py`, `tests/test_issue_ingestion.py` | Condition inside the loop's iterable; a one-line `labeled()` test helper. | fixed (0.12.35: plain `if`; params inline) |
| N-10 | reuse | tests | The "next page" `Link` header is written in four tests across two files. | accepted (test-only) |

## Released-name refresh review (2026-10-29)

Source: `code-review` over the uncommitted `released-name-refresh` change (archived
2026-10-29) together with the uncommitted 0.12.35. L-1, L-2, L-4, L-5 fixed before commit, with
tests; the `repository-analysis` spec ("Background refresh") was edited directly (the archived
delta predates the fixes).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| L-1 | bug | `services/repositories/backlog.py` (`queue_released`) | A holder under analysis is skipped, and that analysis ends in `ClaimLost` without queuing it again (its own stamp still set): it waited about 75 minutes, the delay the change removes. | fixed (`lifecycle.NameChanged`; the analysis releases and calls `queue_released(..., requeue=True)`) |
| L-2 | design | `queue_released` | Ignored the refresh-failure delay, so rejected app credentials sent one doomed task per released name. | fixed (held back only for `github_auth_invalid` within `REPO_REFRESH_RETRY_MINUTES`; `backlog.AUTH_INVALID`) |
| L-3 | altitude | `services/github/storage.py` | The storage helper now queues tasks as a side effect; an autocommit caller would send at once. | accepted (design D1; marking STALE instead would still wait for the 15-minute backlog; every caller owns a transaction) |
| L-4 | reuse | `backlog.py` | `queue_released` copied part of `queue_batch`'s selection, without the `skip_locked` pick. | fixed (`_pick`, `_not_queued`, `_refresh_failed` shared) |
| L-5 | bug | `core/checks.py` (`core.E041`) | A label name with a comma passed; `labels=a,b` asks for issues with both. | fixed (E041 refuses commas) |
| L-6 | design | `analysis.py` labeled listings | Exact names only; `good-first-issue` variants missed. | accepted (same as N-5) |
| L-7 | cost | `analysis.py` labeled listings | Two more requests per capped repository every 6 hours. | accepted (measured in 0.12.35; revisit if rate limits show) |

## Route-id validation review (2026-10-30)

Source: `code-review` over the uncommitted `route-id-validation` change (archived 2026-10-30).
RT-1, RT-2, RT-6 fixed before commit; RT-3, RT-4, RT-5 open (kept for a later look; R-3 and R-5
go against design decisions D3 and D1, so fixing them means revisiting the design).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| RT-1 | test | `feedback.test.tsx` (one view per id) | The page's `viewed` ref already records one view per id, so the test passed without `key={id}`: nothing guarded the remount per id. | fixed (`RouteId.test.tsx` navigates 1 → 2 and asserts two mounts; fails without the key) |
| RT-2 | docs | CHANGELOG, `features.txt`, CLAUDE.md, `ideas.md` | "No behavior change", but keying by id remounts the page on an id change (design D2): scroll-to-hash and local state reset, a pending mutation's per-call callbacks are skipped. | fixed (release notes say the page remounts per id) |
| RT-3 | design | `useRecommendation`, `useIssue` | Without the `enabled` guard a future unchecked caller sends `/recommendations/NaN`. | open (design D3 chose no guard: it would hide the caller bug as a page that loads forever; a 404 shows a dead end) |
| RT-4 | cleanup | `RecommendationDetailPage.tsx` (`viewed` ref) | The id comparison is redundant with the remount. | open (the ref still stops StrictMode's double effect; could become a boolean) |
| RT-5 | altitude | `RouteId.tsx` render prop | `page={Component}` would be shorter in `routes.tsx`. | open (design D1 chose the render prop: page props type-checked, message beside the route) |
| RT-6 | docs | CHANGELOG, `RouteId.test.tsx` | CHANGELOG lists ` 7`; the test passes `%207`. | fixed (both say `%207`, decoded to ` 7`) |

## E2E production-build review (2026-10-30)

Source: `code-review` (E2E-1…E2E-9) and `/simplify` (E2E-10…E2E-13) over the uncommitted
`e2e-production-build` change (archived 2026-10-30). Unverified recall findings, checked
against Vite and Playwright behavior before fixing.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| E2E-1 | test | `e2e/fixtures.ts` | The check matches Chromium's "Content Security Policy" wording, proven only once by hand: a wording change would silence every policy check. | fixed (`policyViolations` yields `{ seen, take() }`; canary `e2e/policy.spec.ts` blocks a foreign image and asserts it is recorded; fails when the match breaks) |
| E2E-2 | test | `e2e/fixtures.ts` | Listened on the test's `page` only: a popup or second tab could break the policy unseen. | fixed (`context.on('console')`) |
| E2E-3 | test | `e2e/fixtures.ts` | A violation after the test's last awaited step arrives after the check. | accepted (waiting for network idle after every test costs every test) |
| E2E-4 | cleanup | `vite.config.ts` | `preview.proxy` repeats Vite's fallback to `server.proxy`. | accepted (design D3: explicit, one shared constant) |
| E2E-5 | security | `vite.config.ts` | `vite preview` inherits `server.host: true`: the e2e preview (proxying to the seeded backend) listened on every interface. | fixed (`--host localhost` on the e2e preview command; E2E-11) |
| E2E-6 | config | `playwright.config.ts` | `vite build` reads `apps/frontend/.env*`, so local `VITE_*` values reach the e2e build; the README said local runs match CI. | documented (README "End-to-end tests") |
| E2E-7 | ops | `playwright.config.ts` | The frontend server's stdout was ignored: a slow or hung build showed nothing before the timeout. | fixed (`stdout: 'pipe'`) |
| E2E-8 | cost | `e2e/fixtures.ts` | The auto fixture gives every test a browser context, even an API-only one. | accepted (no API-only spec exists) |
| E2E-9 | test | `csp.config.test.ts` | Reads `dist/`, not `dist-e2e/`. | accepted (the browser now checks the policy of the build that runs) |
| E2E-10 | cleanup | `playwright.config.ts` | Port 5174 three times and `dist-e2e` twice: a change in one place leaves the URL and the server out of step. | fixed (`PORT`, `BASE_URL`, `SERVE`, `OUT`; comment says why not `npm run build`) |
| E2E-11 | altitude | `vite.config.ts` | `preview.host` (an e2e concern) sat in config every `vite preview` reads. | fixed (`--host localhost` on the e2e preview command; E2E-11) |
| E2E-12 | altitude | `e2e/policy.spec.ts` | The canary emptied the fixture's array (`length = 0`) and hard-coded `img-src 'self'`. | fixed (fixture yields `{ seen, take() }`; directive from `CONTENT_SECURITY_POLICY`) |
| E2E-13 | cleanup | `playwright.config.ts`, `policy.spec.ts` | `E2E_DEV_SERVER === '1'` read twice; a full build on every local run. | accepted (two reads, no shared module; design D1: no stale-build skip) |

## Sweep: `config/` (2026-10-30)

Source: full review sweep, `/code-review` (high, no verify pass) of every file in
`apps/backend/config/`. Each row checked against the code; verdicts: `confirmed`, `partial`
(real but narrower than reported), `accepted`. Fixed in 0.12.39 by the OpenSpec change `config-review-fixes`; CFG-7 and CFG-8 accepted. `/security-review` of the whole
module found no high- or medium-confidence vulnerability (secrets without defaults, e2e app only
in `e2e.py`, production `DEBUG = False`, Secure/HttpOnly/SameSite cookies, CSRF on, CORS closed
by default, proxy headers trusted only with `NUM_PROXIES > 0`, JSON-only Celery, redacted logs).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| CFG-1 | config | `settings/test.py` | `base.py` reads the repo-root `.env` (`DJANGO_READ_DOTENV` defaults on) and `test.py` resets none of `REDIS_URL`, `NUM_PROXIES`, `DISCOVERY_*`, `GITHUB_OAUTH_SCOPES`: local pytest runs with other settings than CI; tests with `CELERY_TASK_ALWAYS_EAGER=False` (`test_github_resilience.py`, `test_github_sync.py`) can reach the dev broker. | fixed (0.12.39, `config-review-fixes`: `DJANGO_READ_DOTENV=DATABASE_URL` in `test.py`; `base.py` takes only that key from `.env`) |
| CFG-2 | bug | `settings/base.py:229` | `CELERY_BROKER_TRANSPORT_OPTIONS` has `socket_connect_timeout` only: a publish on a stalled open Redis connection has no read/write timeout, so `.delay()` in a request can hang (invariant 3). The cache sets both. | fixed (0.12.39, `config-review-fixes`) |
| CFG-3 | resilience | `settings/base.py:91` | `CONN_MAX_AGE` 60 without `CONN_HEALTH_CHECKS`: a connection dropped by a PostgreSQL restart fails the next query with `OperationalError`. | fixed (0.12.39, `config-review-fixes`) |
| CFG-4 | config | `settings/base.py:279…425` | Eight `{**defaults, **env.json(NAME, default={})}` merges: a JSON value that is not an object (`'[1,4]'`) crashes settings import with a nameless `TypeError` before the system checks run. | fixed (0.12.39, `config-review-fixes`: `env_json`, `env_mapping`; also `DISCOVERY_STAR_BANDS`, `DISCOVERY_EXCLUDED_TOPICS`) |
| CFG-5 | config | `settings/base.py:227` | `CELERY_TASK_ACKS_LATE` on Redis without `visibility_timeout` (kombu 3600 s): a task or ETA held over an hour is redelivered. | fixed in part (0.12.39, `config-review-fixes`: `visibility_timeout = max(3600, 2 * GITHUB_MAX_RETRY_DELAY)`; a task running longer is still redelivered, claim fencing cancels the copy) |
| CFG-6 | bug | `exceptions.py:68` | Non-validation errors use `str(exc.detail)`: a dict or list detail becomes a Python repr in `message`. | fixed (0.12.39, `config-review-fixes`: default message, detail in `details`) |
| CFG-7 | ops | `exceptions.py:57` | Unhandled errors become a 500 inside DRF's handler, so `got_request_exception` never fires (future error tracking, DEBUG pages, test client re-raise). | accepted for now (revisit with observability, `ideas.md` §5) |
| CFG-8 | cleanup | `settings/production.py:7` | Re-reads `REDIS_URL` from the environment instead of `base.REDIS_URL` (what cache and broker use). | accepted (tried and reverted: base and production read the same environment at startup, and the production-settings tests set `REDIS_URL` after `base` is imported) |
| CFG-9 | config | `settings/base.py:469` | The `django` logger is fixed at INFO; `LOG_LEVEL` reaches only the root logger. | fixed (0.12.39, `config-review-fixes`) |
| CFG-10 | config | `settings/base.py:242` | `GITHUB_OAUTH_SCOPES` splits on whitespace while every other list setting is comma-separated (`env_list`): `read:user, user:email` yields `read:user,`. | fixed (0.12.39, `config-review-fixes`: `env_words`) |

Review of the fix diff (`/code-review`, workflow step 7), recorded as CFG-11…CFG-20:

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| CFG-11 | test | `tests/test_config_settings.py` | Asserted `settings.REDIS_URL == ""`, but CI's backend job sets `REDIS_URL`: CI would fail. | fixed (assertion dropped; the `.env` behavior is tested on a temporary file; suite also run with CI's `REDIS_URL`) |
| CFG-12 | process | `.gitignore` | Ignoring the SRS files does not untrack them; the docs say they are untracked. | fixed (owner ran `git rm --cached`; files kept locally, gitignored) |
| CFG-13 | security | `settings/base.py` LOGGING | With `django` at `LOG_LEVEL`, `LOG_LEVEL=DEBUG` plus `DEBUG=True` would log every SQL statement with parameters (session keys, encrypted tokens). | fixed (`django.db.backends` pinned at INFO) |
| CFG-14 | config | `settings/base.py` | `DJANGO_READ_DOTENV=database_url` (other case, spaces) silently read nothing. | fixed (compared trimmed, case-insensitively) |
| CFG-15 | test | `tests/test_config_settings.py` | Asserted `DJANGO_READ_DOTENV == "DATABASE_URL"`, contradicting "an explicit environment wins". | fixed (dropped with CFG-11) |
| CFG-16 | bug | `settings/base.py` `env_json` | A blank value (`EVIDENCE_WEIGHTS=`) failed as invalid JSON while `DISCOVERY_STAR_BANDS=` passed. | fixed (blank means the default) |
| CFG-17 | config | `settings/base.py` broker | A sub-second `REDIS_SOCKET_TIMEOUT` would time out the worker's 1 s BRPOP. | fixed (broker `socket_timeout` at least 2 s) |
| CFG-18 | docs | change `tasks.md` | Task 1.1 said `DJANGO_READ_DOTENV=0`. | fixed |
| CFG-19 | api | `config/exceptions.py` | A list detail went to `details`, documented as an object; untested. | fixed (a list becomes the message; tested) |
| CFG-20 | cleanup | `settings/base.py` | `_DotenvValues` kept a process-global class dict. | fixed (`_dotenv_value(path, key)` builds a local class per call) |

## Sweep: `core/` (2026-10-30)

Source: full review sweep, `/code-review` (high, no verify pass) of every file in
`apps/backend/core/`. Each row checked against the code. Fixed in 0.12.40 by the OpenSpec change `core-review-fixes` (`/simplify` and the fix-diff
`/code-review` skipped on the owner's decision). `/security-review` of the whole module found no high- or
medium-confidence vulnerability (401 without CSRF changes, no `csrf_exempt`, OAuth state
session-bound and single-use, health returns status words only, fixed error bodies, deny-all CSP
on JSON, no code path logs a token, secret or session id, report paths only from CLI flags).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| CORE-1 | bug | `startup.py:22` | `run_startup_checks` collects every serious message, silenced or not (Django's `check` drops silenced ones at every level): an id in `SILENCED_SYSTEM_CHECKS` still stops gunicorn and Celery in production while `manage.py check` passes. | confirmed (skip `is_silenced()` before `is_serious()`); fixed (0.12.40, `core-review-fixes`) |
| CORE-2 | config | `checks.py:46` | `NUM_PROXIES` has no check; W002 tests only `== 0`. A negative value makes DRF's `get_ident` index wrongly: one forwarded entry → `IndexError` (500 on throttled and audited requests), two → a client-chosen IP. | confirmed (operator setting; add to `NON_NEGATIVE_INT_SETTINGS`); fixed (0.12.40, `core-review-fixes`) |
| CORE-3 | security | `logging.py:12` | Redaction keys are anchored with ``, so `GITHUB_CLIENT_SECRET=…`, `encrypted_access_token=…` or `oauth_state=…` pass (no boundary after `_`); cookies (`sessionid`, `csrftoken`), `password` and `TOKEN_ENCRYPTION_KEYS` are not covered. | confirmed (backstop gap; primary rule is never logging secrets); fixed (0.12.40, `core-review-fixes`) |
| CORE-4 | config | `checks.py:247` | `DISCOVERY_QUERY_SHARES` with every share 0 passes; `allocate` then returns zero quotas, so discovery never searches. | confirmed (require a positive total); fixed (0.12.40, `core-review-fixes`) |
| CORE-5 | config | `startup.py:21` | The production gate runs checks without `include_deployment_checks=True`, so Django's `--deploy` checks (`SECRET_KEY` strength, …) never run at startup. | partial (production settings already force `DEBUG = False` and secure cookies; `SECRET_KEY` strength is unchecked); fixed (0.12.40, `core-review-fixes`) |
| CORE-6 | config | `checks.py:64` | E060 accepts a CSP containing a newline or control character; Django then raises `BadHeaderError` on every response. | confirmed; fixed (0.12.40, `core-review-fixes`) |
| CORE-7 | bug | `checks.py:239`, `97`, `100`, `243`, `299` | Numeric comparisons run after a non-numeric value was reported, so the check crashes with `TypeError` instead of returning its errors. | partial (only through a settings override: `env.int`/`env.float` already type them); fixed (0.12.40, `core-review-fixes`) |
| CORE-8 | config | `checks.py:271` | `REPO_STALE_AFTER` values may be 0, making every part stale on fetch: every sweep re-queues every repository. | confirmed (positive-integer rule); fixed (0.12.40, `core-review-fixes`) |
| CORE-9 | robustness | `reports.py:21` | `write_json` overwrites in place and converts only `OSError`: an interrupted write truncates the target (e.g. `benchmark-v2.json`); unserializable data raises after folders are created. | partial (committed files are recoverable from git; atomic temp file + `os.replace` is cheap); fixed (0.12.40, `core-review-fixes`) |
| CORE-10 | reuse | `checks.py:127` | `QUERY_STRATEGIES`, `STALE_PARTS` copy `queries.STRATEGIES` and `staleness.PARTS`; a new strategy or part means two edits. | confirmed (import lazily inside the check, as `configured_star_bands` already is); fixed (0.12.40, `core-review-fixes`) |

## Sweep: `accounts/` (2026-10-30)

Source: full review sweep, `/code-review` (high, no verify pass) of `apps/backend/accounts/`
(migrations skipped), reading `services/audit.py`, `services/github/accounts.py`, the OAuth
helpers, `services/data_deletion.py` and `core/authentication.py` for context. Each row checked
against the code. Fixed in 0.12.41 by the OpenSpec change `accounts-review-fixes` (ACC-9 queued on the
owner's decision; `/simplify` applied while writing, fix-diff `/code-review` skipped), ACC-4 accepted. `/security-review` of the whole module found no high- or
medium-confidence vulnerability (256-bit single-use session-bound OAuth state, users keyed by
immutable GitHub id, fixed redirect destinations, session key cycled on login and flushed on
logout, no id parameters on account endpoints, CSRF enforced on POST/DELETE, no token in any
response, allowlisted audit metadata with HMAC-hashed IPs).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| ACC-1 | bug | `views.py:135` | The callback signs in a deactivated user (`is_active=False`): it stores a fresh token, audits `SIGN_IN` success and queues a sync; the next request is 401 (`ModelBackend` refuses inactive users), so the user lands signed out with no error. | confirmed (`link_github_account` never checks `is_active`; refuse before storing the token, audit a failure); fixed (0.12.41, `accounts-review-fixes`) |
| ACC-2 | bug | `views.py:134` | Only `OAuthError` is caught: a failure in `link_github_account` (bad `TOKEN_ENCRYPTION_KEYS`, DB or lock error) or `login()` shows the raw JSON 500 on the browser's callback navigation, with no redirect and no `SIGN_IN_FAILED` audit. | confirmed; fixed (0.12.41, `accounts-review-fixes`) |
| ACC-3 | bug | `views.py:243` | Account deletion records `ACCOUNT_DELETED` and anonymizes the audit trail before `user.delete()`, outside one transaction: a failing delete leaves a "deleted" entry for an account that still exists, session already flushed. | partial (needs `user.delete()` to fail; one transaction for audit, anonymize and delete fixes it); fixed (0.12.41, `accounts-review-fixes`) |
| ACC-4 | race | `views.py:216` | Disconnect deletes the `GitHubAccount` outside a lock; a sign-in callback finishing in another tab afterwards re-creates it with a live, unrevoked token and queues a sync. | accepted (a sign-in the user completes on GitHub after a disconnect is a new sign-in; spec "Sign in again after disconnect") |
| ACC-5 | security | `admin.py:9` | `AuditEventAdmin` keeps add and delete permissions: staff can delete audit rows (bulk action) or add blank ones. | confirmed (`has_add_permission`, `has_delete_permission` → False); fixed (0.12.41, `accounts-review-fixes`) |
| ACC-6 | ux | `views.py:95` | The callback shares the 10/min `auth` throttle with the sign-in start and is checked before the view: a throttled callback shows raw 429 JSON on a browser navigation. | partial (NAT or many tabs; redirect to `auth_error=throttled` instead); fixed (0.12.41, `accounts-review-fixes`) |
| ACC-7 | ops | `views.py:88` | Every anonymous `GET /auth/github` writes a session row, and expired sessions are never purged (no `clearsessions` task anywhere). | confirmed (beat task running `clearsessions`); fixed (0.12.41, `accounts-review-fixes`) |
| ACC-8 | convention | `views.py:190` | Disconnect and account-deletion logic (revoke, unlink, delete data, audit, password rotation, logout order) lives in views and is copied between two views (CLAUDE.md §5). | confirmed (one service, e.g. `services/accounts.py`, used by both); fixed (0.12.41, `accounts-review-fixes`) |
| ACC-9 | convention | `views.py:198` | Disconnect and account deletion call GitHub (`oauth.revoke_grant`) inside the request, against invariant 3; the replaced-token revoke at sign-in is queued. | partial (the disconnect response reported the revocation outcome; owner chose to queue it, the response now says `queued`); fixed (0.12.41, `accounts-review-fixes`) |
| ACC-10 | efficiency | `admin.py:11` | The audit changelist shows `user` without `list_select_related` (one query per row), and no index on `-created_at` alone for its default order. | confirmed (minor); fixed (0.12.41, `accounts-review-fixes`) |

Review of the fix diff (`/code-review high apps/backend/github` on 2026-10-30 reviewed only the
uncommitted 0.12.41 changes in that folder and their callers; it is batch 28's skipped fix-diff
review, not the `github/` module review), recorded as ACC-11…ACC-20. Each checked against the
code. Fixed before the 0.12.41 commit (ACC-17 accepted in part).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| ACC-11 | bug | `github/tasks.py` `revoke_grant` | The queued task revokes the whole grant later; a user who disconnects and signs straight back in gets a token on the same grant, which the late revocation then kills (every sync fails with `GitHubAuthError`). The task is not given the GitHub ID, so it cannot see the re-link. | fixed (0.12.41: `revoke` sees a re-linked account and revokes only the old token) |
| ACC-12 | bug | `services/accounts.py` `_unlink` | No transaction around it, so `on_commit` dispatches at once; with the broker down `.delay` raises after `account.delete()`: data deletion, audit, password rotation and logout never run (500), and the ciphertext is lost. | fixed (0.12.41: services are `@transaction.atomic`; `queue_revocation` uses `on_commit(robust=True)`) |
| ACC-13 | bug | `accounts/views.py:138` | `queue_unused_token_revocation` runs outside the new `try`: a broker error on the deactivated-user path shows a raw 500 on the browser's navigation. | fixed (0.12.41: `refuse_token` queues through the same robust `on_commit`) |
| ACC-14 | convention | `github/tasks.py` | `autoretry_for=(OAuthError,)` retries permanent errors too (401, 422), ignores `Retry-After`, and bypasses the pure retry policy (`services/github/retry.py`, CLAUDE.md §5). | fixed (0.12.41: `revoke_later` uses `decide_retry`; `_revoke` raises `GitHubTransientError` for network, 5xx and 429) |
| ACC-15 | spec | `github/tasks.py` | A final failure after the retries is only Celery's log; the spec says it "SHALL be recorded without the token", and the audit entry stays `queued`. | fixed (0.12.41: audit `github_revocation_failed`, reason only) |
| ACC-16 | bug | `services/github/accounts.py` `queue_unused_token_revocation` | Reuses `revoke_replaced_token`, which skips when the token equals the stored one and never retries: a refused sign-in's token may never be revoked. | fixed (0.12.41: a refused sign-in revokes the deactivated user's whole grant, no stored-token check) |
| ACC-17 | config | `github/tasks.py` | Without Redis (eager), revocation runs inside the request and autoretry repeats it inline up to 4 times, against "GitHub is slow". | partial; accepted (without Redis one attempt runs inline; the retry is scheduled and the robust `on_commit` logs it, never fails the request); superseded by GH-5 (0.12.42: eager mode decides as the last attempt, no inline retry) |
| ACC-18 | bug | `services/github/accounts.py:54` | The replaced-token dispatch in `link_github_account`'s `on_commit` can raise into the view's new `except Exception` after the token is stored: `failed` redirect with a stored token, old token never revoked. | fixed (0.12.41: the replaced-token dispatch is robust too) |
| ACC-19 | robustness | `services/github/accounts.py:77` | `revoke_encrypted_grant` skips a token under a removed key silently. | fixed (0.12.41: logged) |
| ACC-20 | cleanup | `github/tasks.py` | Task `revoke_grant` shares its name with `oauth.revoke_grant` (plaintext): a wrong import sends ciphertext to GitHub or plaintext to the broker. | fixed (0.12.41: task renamed `github.revoke_later`) |

`/simplify` of the uncommitted 0.12.40–0.12.41 backend diff (2026-10-30): the deactivated-user
check moved into `link_github_account` (`AccountInactive`), disconnect and deletion share `_leave`,
tests reuse `_assert_auth_error_redirect`, `encrypt_token` and `UserFactory`. Skipped: one
after-commit dispatch helper and a navigation-view error wrapper (both `ideas.md` §15), a pure
grant/token decision function, a direct call in the `revoke_replaced_token` forwarder, a
redaction pre-check and a `strict` flag on `_between`.

## Sweep: `github/` (2026-10-30)

Source: full review sweep, `/code-review` (high, no verify pass) of `apps/backend/github/`
(migrations skipped), reading `services/github/accounts.py`, `services/github/retry.py`,
`services/jobs.py`, `services/data_deletion.py` and `features/sync/api.ts` for context. Each row
checked against the code. `/security-review` of the whole module found no high- or
medium-confidence vulnerability (every view filters by `current_user`, no id parameters, CSRF on
DELETE, explicit read-only serializers with no `GitHubAccount` field, token excluded from the
admin and every `__repr__`, task arguments are job ids or ciphertext, ETag cache scoped per user
except public repository data).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| GH-1 | robustness | `tasks.py:37` | `revoke_later` maps every non-GitHub exception (database error, code bug) to a final `internal_error` with no traceback logged: the token stays live and nobody can see why. | partial (jobs fail `internal_error` the same way, by policy; the defect is the missing traceback: `logger.exception` before recording the failure); fixed (0.12.42, `github-review-fixes`) |
| GH-2 | security | `admin.py:6` | `GitHubAccountAdmin` and `GitHubProfileAdmin` keep add and delete: an admin delete skips revocation and `delete_github_data` (grant stays live, derived data orphaned); the add form (`user`, `github_id` read-only, token excluded) fails with an IntegrityError 500. | confirmed (`has_add_permission`, `has_delete_permission` → False, as `AuditEventAdmin`); fixed (0.12.42, `github-review-fixes`) |
| GH-3 | bug | `api.py:116` | `GitHubDataView.delete` commits `delete_github_data`, then writes the audit entry outside its transaction, in the view: a failing audit write returns 500 with the data already gone and no `github_data_deleted` entry (CLAUDE.md §5; account deletion is atomic since 0.12.41). | confirmed (one `@transaction.atomic` service in `services/accounts.py`; spec delta: deletion and its audit entry together or not at all); fixed (0.12.42, `github-review-fixes`) |
| GH-4 | bug | `api.py:134` | `max_page_size = 100` is hard-coded to the default `GITHUB_SYNC_MAX_REPOS`, and the SPA fetches one page (`page_size=100`, never `next`): with the cap raised, repositories past 100 never show. | partial (only with a non-default setting; page cap from the setting, SPA asks for it or follows `next`); fixed (0.12.42, `github-review-fixes`) |
| GH-5 | config | `tasks.py:45` | `revoke_later` calls `self.retry` in eager mode (no `REDIS_URL`): up to 4 inline attempts with no backoff inside the request's `on_commit`. `run_tracked_job` decides as on the last attempt (D4). | confirmed (pass `REVOCATION_ATTEMPTS` as the attempt count when `CELERY_TASK_ALWAYS_EAGER`; supersedes ACC-17's acceptance); fixed (0.12.42, `github-review-fixes`) |
| GH-6 | race | `services/github/accounts.py:78` | Between `revoke` reading the stored token (none) and `revoke_grant` reaching GitHub, a completed re-sign-in gets its new token killed with the grant. | accepted (window is one GitHub call; a lock cannot be held across it (no I/O under a lock) and the account row is gone after disconnect; the user signs in again; as ACC-4) |
| GH-7 | efficiency | `api.py:153` | `.distinct()` in `RepositoryListView` is redundant: `unique_user_repository_relation` plus the user and OWNER filter give one row per repository; every page and count runs `SELECT DISTINCT`. | confirmed (remove); fixed (0.12.42, `github-review-fixes`) |
| GH-8 | efficiency | `admin.py:8` | Both admins list `user` without `list_select_related`: one query per row. | confirmed (minor; `list_select_related = ("user",)`); fixed (0.12.42, `github-review-fixes`) |

`/simplify` of the fix diff (2026-10-31): `core/admin.py` `NoAddDeleteAdmin` shared by the GitHub
admins and `AuditEventAdmin`; `services/github/retry.attempt_number(executed, max_attempts,
eager=)` is the one eager rule (`run_tracked_job`, `revoke_later`); the traceback follows the
decision (`internal_error`); the SPA fetches `next`'s own query; tests bulk-create. Skipped: one
huge `page_size` from the SPA (design D2), merging the three `ReadOnlyAdmin` copies (outside the
diff).

Review of the fix diff (`/code-review medium`, 2026-10-31), recorded as GH-9…GH-15, each checked
against the code.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| GH-9 | behavior | `github/admin.py` | No delete permission on the GitHub admins also stops the admin deleting a User who has a GitHub account or profile (cascade). | accepted (intended: an admin user delete would drop the account without revoking, GH-2's hole; `delete_account` is the path; design Risks) |
| GH-10 | robustness | `github/tasks.py` | `OAuthError` (GitHub refusing, 401/422) maps to `internal_error`, so it would log a traceback as "unexpected". | fixed (no traceback for `OAuthError`; the audit reason stays `internal_error`, as before) |
| GH-11 | design | `features/sync/api.ts` | The SPA asks for 100 per page although the server cap follows the setting: a large cap takes several requests. | wontfix (design D2: the SPA never depends on the server cap) |
| GH-12 | race | `features/sync/api.ts` | Page-number paging across requests can repeat or skip a row if a sync stores repositories between pages. | accepted (the dashboard refetches when the sync finishes; one page under the default cap) |
| GH-13 | robustness | `features/sync/api.ts` | The page loop ignored the query's `AbortSignal`: a cancelled query kept fetching. | fixed (`signal` passed to every request) |
| GH-14 | locking | `services/accounts.py` | The outer transaction makes the job cancel a savepoint, so job rows stay locked for the whole deletion. | accepted (design D1 and Risks; as disconnect since 0.12.41) |
| GH-15 | naming | `services/accounts.py` | `accounts.delete_github_data` shadows `data_deletion.delete_github_data`. | accepted (design D1: callers import the module) |

## Sweep: `e2e/` (2026-10-31)

Source: full review sweep, `/code-review` (high) of `apps/backend/e2e/` (seed command,
`builders.py`), reading `config/settings/e2e.py`, `services/jobs.py`, `tests/test_e2e_seed.py`,
`apps/frontend/e2e/*.spec.ts` and `playwright.config.ts` for context. Each row checked against the
code.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| SEED-1 | safety | `e2e_seed.py:54` | The destructive `_reset` is guarded only by "`e2e` in `INSTALLED_APPS`", never by the database: a settings module that ever installs the app would wipe its real database. | confirmed (latent: only `config.settings.e2e` installs the app today, and it pins `NAME` to `contribfinder_e2e`; also refuse unless the database name is the e2e one); fixed (0.12.43, `e2e-seed-review-fixes`) |
| SEED-2 | test isolation | `e2e_seed.py:36` | Seeded once per run, but CI retries once: `save` and `dismiss` both mutate `e2e-dashboard` (which `auth.spec` reads too), so a retried save finds "Saved"; a retried `data.spec` finds no data. Against "Mutating specs each own a seeded user". | confirmed (own users for save and dismiss; a retried delete-data cannot recover by design, accept or reseed that user per attempt); fixed (0.12.43, `e2e-seed-review-fixes`) |
| SEED-3 | test fidelity | `builders.py:48` | `add_candidate` on an existing candidate never advances its `last_seen_at`, and `discovery_seen` can leave the candidate older than its own record: states `DiscoveryService` never writes. | partial (test builder only; no current test reads the stale value; advance `last_seen_at` to the latest record time); fixed (0.12.43, `e2e-seed-review-fixes`) |
| SEED-4 | robustness | `e2e_seed.py:74` | `CREATE DATABASE "{name}"` by f-string, not `connection.ops.quote_name`; uses private `_nodb_cursor()`. | partial (name is the constant `contribfinder_e2e`; use `quote_name`; `_nodb_cursor` kept, Django has no public no-database cursor); fixed (0.12.43, `e2e-seed-review-fixes`) |
| SEED-5 | hygiene | `e2e_seed.py:77` | `_reset` keeps `django_session` and `AuditEvent` rows (no FK cascade), so a reused e2e database grows every run and keeps sessions of deleted users. | confirmed (minor; delete both in `_reset`); fixed (0.12.43, `e2e-seed-review-fixes`) |
| SEED-6 | test gap | `tests/test_e2e_seed.py:41` | The suite never runs `_reset` on seeded data or the sessions JSON: a new PROTECT FK breaks only the CI e2e job. | confirmed (test: seed, `_reset`, seed again; check the written keys); fixed (0.12.43, `e2e-seed-review-fixes`) |
| SEED-7 | convention | `e2e_seed.py:211` | `_run` saves steps unguarded, then `finish_job` writes again, and its False return is ignored (a seeded job could stay RUNNING silently). | confirmed (`finish_job(job, COMPLETED, steps=...)` once; raise `CommandError` on False); fixed (0.12.43, `e2e-seed-review-fixes`) |
| SEED-8 | duplication | `e2e_seed.py:195` | `_new_job` copies the job construction in `services.jobs._start_job`. | confirmed (minor; one `jobs.new_job(user, job_type)` for both); fixed (0.12.43, `e2e-seed-review-fixes`) |
| SEED-9 | typing | `builders.py:64` | `make_issue` returns `Any` (function-level import), so call sites lose strict mypy. | confirmed (top-level `Issue` import, `-> Issue`); fixed (0.12.43, `e2e-seed-review-fixes`) |
| SEED-10 | test data | `e2e_seed.py:110` | Snapshot `days_since_push=2` while `pushed_at` is 3 days ago (`make_candidate_repo`). | confirmed (cosmetic; derive from `repo.pushed_at`); fixed (0.12.43, `e2e-seed-review-fixes`) |

`/simplify` of the fix diff (2026-10-31): the seed's sessions file is the one contract (users
that tests change map to one session per attempt, the rest to one id), so `e2e/fixtures.ts` keeps
no user list or naming rule; the attempt count comes from `playwright.config.ts` `RETRIES` through
`scripts/e2e-backend.mjs` (`--attempts`); the seed-twice test stubs the pipeline (52 s → 9.5 s);
`PUSHED_DAYS_AGO`, the sessions file read once. Skipped: inlining the dashboard sign-in helper,
cloning pipeline rows between seeded users (only if the seed gets slow).

Review of the fix diff (`/code-review medium`, 2026-10-31), recorded as SEED-11…SEED-19, each
checked against the code.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| SEED-11 | bug | `e2e_seed.py` `seed` | Retry copies named `<user>~n`: `~` is `staleness.RELEASED_MARK`, so their repositories (`e2e-save~1/own-0`) read as released names, and `~` is no GitHub login character. | fixed (`<user>-retry<n>`; test: no seeded name holds the mark) |
| SEED-12 | test isolation | `e2e/fixtures.ts` | The fixture told shared from per-attempt users by list length: a mutating user seeded for one attempt and retried (`--retries` on the command line) reused its changed data. | fixed (shared users map to one id, per-attempt users to a list; a missing attempt fails naming it) |
| SEED-13 | config | `playwright.config.ts` | A command-line `--retries` override is not passed to the seed. | accepted (with SEED-12 it fails loudly on the missing attempt) |
| SEED-14 | test coverage | `builders.py` | Raising the candidate's `last_seen_at` to `discovery_seen` makes `seen` set only `first_discovered_at` in tests that pass both. | accepted (design D5: discovery stamps both with the run time; expiry and pool-order tests pass unchanged) |
| SEED-15 | test data | `builders.py` | `first_discovered_at` could be later than its own record's `last_seen_at`. | fixed (the earlier of `seen` and `discovery_seen`) |
| SEED-16 | robustness | `e2e_seed.py` | `--attempts < 1` was refused only after creating and migrating the database. | fixed (argparse type, before any side effect) |
| SEED-17 | efficiency | `builders.py` | A filtered UPDATE ran after every create. | fixed (saves only an existing, older candidate) |
| SEED-18 | efficiency | `e2e_seed.py` | One full pipeline per retry copy: 3 more in CI. | accepted (design Risks; CI e2e startup unchanged in practice) |
| SEED-19 | docs | `services/jobs.py` `new_job` | Public `new_job` skips `_start_job`'s stale expiry and conflict handling, undocumented. | fixed (docstring: no checks; real jobs start through `start_*`) |

## Sweep: `services/*.py` (2026-10-31)

Source: full review sweep, `/code-review` (high, no verify pass) of the top-level
`apps/backend/services/*.py` (accounts, audit, crypto, data_deletion, data_versions, errors,
feedback, job_guard, jobs, locks, text). Each row checked against the code.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| SVC-1 | privacy | `data_deletion.py:80` | The cache purge reads `user.pk` at commit; account deletion has already run `user.delete()` (pk None), so it purges `github:etag:None:*` and the deleted user's cached GitHub responses stay until their TTL. | confirmed (capture `user_id = user.pk` before `on_commit`; test the purge after account deletion); fixed (0.12.44, `services-review-fixes`) |
| SVC-2 | race | `feedback.py:79` | `record` locks the recommendation but not the issue of an `opened_issue` event: an issue refresh deleting it meanwhile makes one commit fail its deferred FK (500). | confirmed (rare; lock the issue by pk after the recommendation, per `services/locks.py` order; gone → no event); fixed (0.12.44, `services-review-fixes`) |
| SVC-3 | race | `data_deletion.py:97` | `_delete_orphans` decides orphans with NOT EXISTS and locks nothing: another user's discovery linking the repository at the same moment fails one transaction's deferred FK at commit. | partial (rare, fails loudly, no data lost; lock the candidate orphans in pk order, then re-check); fixed (0.12.44, `services-review-fixes`) |
| SVC-4 | deadlock | `jobs.py:86` | `_end_jobs` locks rows in no fixed order; recovery, cancel and expiry can lock overlapping jobs in opposite orders. | confirmed (`.order_by("pk")` before `select_for_update()`); fixed (0.12.44, `services-review-fixes`) |
| SVC-5 | bug | `jobs.py:379` | A rerun requested on a RUNNING generation is dropped when that run ends FAILED (`rerun_recommendations_if_requested` is only `on_completed`); a restored repository stays away up to `RECOMMENDATION_FAILED_RETRY_MINUTES`. | confirmed (also run the hook after a final failure; check `recommendation-engine` spec wording); fixed (0.12.44, `services-review-fixes`) |
| SVC-6 | privacy | `data_deletion.py:103` | The purge runs once at commit: a cancelled sync's in-flight GitHub request can write its ETag entry afterwards, which then outlives "delete my data" for `GITHUB_ETAG_TTL`. | partial (window is one request; a second purge queued with a countdown past `GITHUB_HTTP_TIMEOUT`); narrowed (0.12.44, `services-review-fixes`: second purge); fixed (0.12.76, `etag-cache-generation`: root fix SVC-16) |
| SVC-7 | data | `feedback.py:63` | Event snapshots (rank, label, config version) come from the object loaded before the lock, so a regeneration in between stores the old values. | confirmed (minor; snapshot from the row re-read under the lock); fixed (0.12.44, `services-review-fixes`) |
| SVC-8 | robustness | `jobs.py:74` | `claim_job` reloads with `.get()`: a job deleted by data deletion right after the claim raises `DoesNotExist` outside `run_tracked_job`'s try. | confirmed (`.first()`, None); fixed (0.12.44, `services-review-fixes`) |
| SVC-9 | freshness | `data_versions.py:59` | Save, unsave, dismiss and restore without generation never move the `recommendations` version, so another tab keeps a stale saved/hidden list up to the stale time. | partial (matches the "Data versions endpoint" spec; a fix includes the user's latest save/dismiss feedback event time and needs a spec delta); fixed (0.12.44, `services-review-fixes`) |
| SVC-10 | efficiency | `data_deletion.py:98` | `orphans.count()` then `orphans.delete()`: the anti-join runs twice and the audited count can differ from what was deleted. | confirmed (count from `delete()`'s per-model result); fixed (0.12.44, `services-review-fixes`) |

`/simplify` of the fix diff (2026-10-31): `feedback.LIST_ACTIONS` and a partial index
`feedback_list_change_idx (user, -created_at)` for the four list actions (`feedback.0006`): the
versions read runs on every route change and would otherwise scan the user's `viewed` events;
`services/feedback._current(recommendation, lock=)` is the one re-read for `record` and `save`;
test cleanups. Skipped: the `list(...)` lock form (commented), a mypy-only local.

Review of the fix diff (`/code-review medium`, 2026-10-31), recorded as SVC-11…SVC-20, each
checked against the code.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| SVC-11 | deadlock | `data_deletion.py` `_delete_orphans` | The new orphan lock took rows in pk order; discovery's bulk repository locks go in GitHub ID order, so a deletion and another user's search could deadlock. | fixed (GitHub ID order) |
| SVC-12 | docs | `data_deletion.py` `_delete_orphans` | The comment said every linking writer holds the row lock; with deferred FKs an insert-only writer locks nothing until commit. | fixed (comment narrowed; that case stays a loud FK failure, design D4) |
| SVC-13 | behavior | `services/jobs.py` `on_failed` | A requested rerun follows any final failure, also a permanent one, outside the freshness sweep's failure backoff. | accepted (one extra run per request at most, design D2) |
| SVC-14 | efficiency | `data_deletion.py` `_purge_later` | The delayed purge also clears the ETag cache of a sync started right after a delete-data. | accepted (the cache only saves requests: one unconditional round) |
| SVC-15 | privacy | `data_deletion.py` `_purge_later` | A worker slower than `SYNC_STALE_AFTER_SECONDS` can still write after the second purge. | accepted (window bounded by `GITHUB_ETAG_TTL`; root fix SVC-16); fixed (0.12.76, `etag-cache-generation`) |
| SVC-16 | design | `data_deletion.py` | The timed second purge is a stopgap: the root fix scopes user ETag keys to a generation that deletion bumps (or checks the claim before a cache write). | open (follow-up; non-goal of `services-review-fixes`); fixed (0.12.76, `etag-cache-generation`: `User.github_cache_generation` bumped by deletion; a user-scope client re-reads it after each ETag write and deletes the entry when it changed or the user is gone; the timed second purge is retired) |
| SVC-17 | convention | `github/tasks.py` `purge_user_cache` | The task creates no `SyncJob` and does not retry. | accepted (best-effort cache cleanup, logged; entries expire within the TTL; as `revoke_later`, no job) |
| SVC-18 | efficiency | `data_versions.py` | Every save or dismiss moves the version, so the next route change or focus refetches the recommendation area. | accepted (the purpose of SVC-9; at most one refetch per route change or focus) |
| SVC-19 | freshness | `data_versions.py` | Event `created_at` is stamped at insert, not commit: a change committed after a newer generation time is not seen. | accepted (same clock basis as every version time) |
| SVC-20 | migration | `feedback/0006` | Generated dependencies on unrelated apps; non-concurrent `AddIndex`. | fixed in part (dependencies trimmed to `feedback.0005` and the user model); plain `AddIndex` kept, as `feedback.0003` |

## Sweep: `services/github/` (2026-10-31)

Source: full review sweep, `/code-review` (high, no verify pass) of `apps/backend/services/github/`
(client, sync, oauth, accounts, storage, retry, errors), reading discovery's lock order,
`lifecycle.release_name`, `backlog.queue_released`, the analysis writers, `job_guard` and
`revoke_later` for context. Each row checked against the code.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| GHS-1 | deadlock | `sync.py:142` | The repositories step upserts shared repository rows in one transaction in `pushed_at` order; discovery and orphan cleanup lock them in GitHub ID order, so a sync and another user's discovery can deadlock. | confirmed (upsert in GitHub ID order; selection by push time unchanged); fixed (0.12.45: upsert sorted by `github_id`) |
| GHS-2 | race | `sync.py:189`, `:215` | Languages and dependencies are replaced (delete, insert) without the repository row lock; an analysis of the same shared row writes them under the lock, so the sync's insert can hit `unique_repo_language`/`unique_repo_dependency` and the sync fails `internal_error`. | confirmed (lock the row inside `job_write` before replacing); fixed (0.12.45: `storage._lock` in `replace_languages`/`replace_dependencies`) |
| GHS-3 | security | `client.py:636` | `_next_link` checks only the host of a pagination link; redirects check scheme, host and port, so an `http://` or other-port `next` link would carry the Authorization header. | partial (needs a tampered GitHub response over TLS; same origin check as `_send`); fixed (0.12.45: `_api_origin`, `_link`) |
| GHS-4 | bug | `oauth.py:158` | `_revoke` treats only 5xx/429 as transient: a 403 rate limit (shared app credentials with the background refresh) is a final `revocation_failed`, the grant stays valid. | confirmed (map the response through the client's rate-limit rules); fixed (0.12.45: 403/429 through `_error_for`; `GitHubRateLimited` retried) |
| GHS-5 | data | `sync.py:251` | Two plan entries resolving to one repository (rename, transfer redirect) collapse in `by_pk`: only the last one's PR and push counts are kept. | confirmed (rare; sum counts, latest time per pk); fixed (0.12.45: `_merge_by_repository`) |
| GHS-6 | data | `sync.py:258` | A contributed repository that hits a `SKIPPABLE` error is stored as None, so the final delete drops its existing contributor link and evidence; languages and dependencies keep what they knew. | confirmed (keep links of skipped repositories; drop only gone or now-owned ones); fixed (0.12.45: `contrib_skipped`; 404 and now-owned still drop the link) |
| GHS-7 | robustness | `client.py:596` | `_send` catches only `httpx.TransportError`: `DecodingError` and `InvalidURL` (bad Location or Link) escape as non-GitHub errors, so a step fails `internal_error` instead of retrying or skipping. | partial (rare; map `httpx.HTTPError`/`InvalidURL` to transient or client errors, as `oauth` does); fixed (0.12.45: `httpx.HTTPError` transient, `InvalidURL` and a bad Link URL client errors; a malformed Location is httpx's `RemoteProtocolError`, transient) |
| GHS-8 | memory | `client.py:578` | The ETag cache stores every 200 body with no size cap (READMEs, 100-item pages) for `GITHUB_ETAG_TTL`; large READMEs grow Redis, which also holds the broker. | partial (no measurement; skip caching bodies above a byte cap); fixed (0.12.45: `GITHUB_ETAG_MAX_BYTES`, default 256 KiB, `core.E020`) |
| GHS-9 | consistency | `sync.py:205` | A retried dependencies step re-picks the capped set by live `pushed_at`, so it can read outside the first attempt's set and the stored totals stop describing what was read. | confirmed (minor; freeze the chosen ids in metadata, as `contrib_plan`); fixed (0.12.45: `dependencies_ids` in metadata) |
| GHS-10 | duplication | `sync.py:335`, `oauth.py:15`, `client.py:620` | `sync._parse_dt` = `client._dt`; `oauth.API_VERSION` repeats `client.API_VERSION`; two Link-header parsers. | confirmed (one of each; GHS-3 fixes both parsers at once); fixed (0.12.45: `client._dt`, `client.API_VERSION`, one `_link`) |

## Sweep: `frontend/src/api/` (2026-11-02)

Source: full review sweep, `/code-review` (high, no verify pass) of `apps/frontend/src/api/`
(`client.ts`, `types.ts`; generated `schema.d.ts`/`openapi.json` matched a fresh export). Each row
checked against the code, its callers (`app/queryClient.ts`, `RequireAuth`, the detail pages,
`AppShell`, `features/feedback/api.ts`) and the backend (`accounts.views.CsrfView`, CSRF and
throttle settings).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| API-1 | bug | `client.ts:74`, `:82` | `apiFetch` does not always throw `ApiError`: a rejected `fetch` (`TypeError`), a non-JSON 2xx body (`SyntaxError`, e.g. an HTML 200 for `/api/...`) and a rejected CSRF prelude escape as other types, though every hook types its error as `ApiError`. Readers of `error.status`/`error.code` (`RequireAuth`, detail-page 404, `RecommendationList`) see `undefined`; `isRetryable` treats any non-`ApiError` as network, so a deterministic `SyntaxError` is retried twice. | confirmed (generic error shown, no wrong redirect; wrap as `ApiError(0, 'network_error')` / `ApiError(status, 'invalid_response')`, retry only the former); fixed (0.12.46: `send` and `invalid_response`; `isRetryable` only `ApiError` 0/5xx) |
| API-2 | bug | `client.ts:59` | The fallback error for a body without the `{error}` envelope drops the parsed `retryAfter` and any details. | partial (the only reader, `AppShell`, needs code `sync_cooldown`, which only an envelope carries; pass `retryAfter` anyway); fixed (0.12.46: fallback passes `retryAfter`) |
| API-3 | bug | `client.ts:41` | `ensureCsrfToken` ignores the `/auth/csrf/` status: a 429 (anon throttle applies to `CsrfView`) or 500 becomes `ApiError(0, 'csrf_unavailable')`. | partial (mutations never retry, so no retry loop; the user sees "Could not obtain a CSRF token" instead of the throttle or server error; raise `toApiError` on a non-ok response); fixed (0.12.46: non-ok token response → `toApiError`) |
| API-4 | efficiency | `client.ts:38` | No shared in-flight promise: concurrent mutations with no cookie each send `GET /auth/csrf/`, each counting toward the anon throttle. | confirmed (minor; one module-level pending promise, cleared when settled); fixed (0.12.46: `pendingCsrf`) |
| API-5 | data | `client.ts:71`, `features/feedback/api.ts:40` | A `keepalive` request awaits the CSRF prelude without `keepalive`; if the cookie is missing and the page unloads, the prelude is aborted and the `opened_repository` event is lost (the `.catch` swallows it). | partial (rare: `login()` rotates and sets the cookie, valid a year; only a cleared cookie hits it; pass `keepalive` to the prelude); fixed (0.12.46: `ensureCsrfToken({ keepalive })`) |
| API-6 | robustness | `client.ts:81` | Only 204 counts as an empty success; a 200/202/205 with no body throws `SyntaxError`. | accepted (every empty success in the backend is 204; revisit if a view changes) |
| API-7 | robustness | `client.ts:48` | `Retry-After` in HTTP-date form becomes `NaN` and is dropped. | accepted (DRF throttles send seconds; no proxy in front adds dates) |
| API-8 | robustness | `client.ts:70` | No refresh-and-retry once on `csrf_failed` after a stale or overwritten cookie. | false positive (`CSRF_USE_SESSIONS` off: double-submit reads header and cookie from the same cookie at send time, so any well-formed cookie, including one set by the e2e backend on `localhost`, passes) |
| API-9 | cleanup | `client.ts:66`, `features/feedback/api.ts:38`, `:113` | No JSON-body option: callers repeat `Content-Type` and `JSON.stringify`; a caller forgetting the header gets 415. | confirmed (a `json` init option in `apiFetch`); fixed (0.12.46: `ApiInit` `json` option) |

## Sweep: `frontend/src/features/auth/` (2026-11-02)

Source: full review sweep, `/code-review` (high, no verify pass) of `apps/frontend/src/features/auth/`
(`api.ts`, `authErrors.ts`, `RequireAuth.tsx`, `DataSection.tsx`, `DisconnectSection.tsx`), with
`app/queryClient.ts`, `routes/LandingPage.tsx` and `routes/AppShell.tsx` (both sections render
there, under its `/onboarding` redirect). Each row checked against the code and TanStack Query v5
behavior.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| AUTH-1 | bug | `authErrors.ts:14` | `MESSAGES[code]` on a plain object: `?auth_error=__proto__` returns `Object.prototype`, rendered as a React child, so the landing page throws; `constructor`/`toString` show an empty alert. Anyone with a link can break the sign-in page for the visitor. | confirmed (`Object.hasOwn(MESSAGES, code)`; client-side only, no script runs); fixed (0.12.47: `Object.hasOwn`) |
| AUTH-2 | bug | `RequireAuth.tsx:30` | `me.isError` wins over cached data: a failed `/auth/me` refetch (focus after the 60 s stale time, network or 5xx after two retries) replaces every signed-in page with "Something went wrong loading your account". | confirmed (keep rendering while `me.data` exists; the error page only without data); fixed (0.12.47: `RequireAuth` renders the `Outlet` while `me.data` exists) |
| AUTH-3 | bug | `RequireAuth.tsx:31`, `queryClient.ts` `isMe` | A 401 on the `/auth/me` refetch is ignored by the query cache, and `RequireAuth` sends the user to `/` without the session-ended notice or cache cleanup. | partial (the versions and sync status queries, `staleTime: 0`, usually 401 at the same focus or route change and run `endSession`; a 401 on `/auth/me` after a success should do the same); fixed (0.12.47: a `/auth/me` 401 with data runs `endSession`) |
| AUTH-4 | privacy | `api.ts:68` | Log out and disconnect remove only `['auth', 'me']`; profile, recommendations, saved lists, jobs, versions and sync status stay in the query cache (disconnect has deleted them on the server). | partial (no cross-user path: signing in is a full-page navigation that reloads the app; still kept until reload in the tab; clean up as `clearSignedInData` does); fixed (0.12.47: `leaveSignedIn`) |
| AUTH-5 | bug | `api.ts:108` | `useDeleteAccount` runs `queryClient.clear()` while `RequireAuth`, the layout and `AppShell` observe their queries: they rebuild and refetch against a deleted account (401s, hidden by `signedOut`), `RequireAuth` shows "Loading…", unmounting `DataSection`, so its per-call `navigate('/')` never runs; the 401 on `/auth/me` reaches `/` instead. | confirmed (navigate first, then drop the data, in the hook); fixed (0.12.47: `useDeleteAccount` through `leaveSignedIn`, no `clear()`) |
| AUTH-6 | bug | `api.ts:89` | `useDeleteGitHubData` removes `['profile']` and `['jobs']` while the dashboard observes them, without cancelling: observers rebuild and refetch deleted data until `AppShell` redirects. | confirmed (minor; leave the dashboard first, then remove); fixed (0.12.47: cancel, refetch sync, navigate, then remove) |
| AUTH-7 | dead code | `DataSection.tsx:85` | The per-call `navigate('/onboarding')` never runs: the hook's `onSuccess` awaits the `['sync']` refetch, `AppShell` redirects to `/onboarding` and unmounts `DataSection` first (per-call callbacks are skipped after unmount, CLAUDE.md Phase 8a). Works only through the redirect. | confirmed (navigate in the hook's `onSuccess`); fixed (0.12.47: navigation in the hooks) |
| AUTH-8 | race | `DataSection.tsx:64`, `DisconnectSection.tsx:32` | The two sections lock only their own actions: Delete account and Disconnect can both be pending; whichever the server handles second answers 401/403, its `onError` resets the shared `signedOut` flag, and the user can land on "session ended" with the account not deleted. | partial (needs a second confirmation dialog within one request's time; one pending state for every account action); fixed (0.12.47: `accountMutationKey`, `useAccountActionPending`) |
| AUTH-9 | test | `auth.test.tsx:122` | The disconnect test mocks `revocation: 'revoked'`, which the backend no longer sends (since 0.12.41: `queued` or `not_connected`). | confirmed (mock `queued`); fixed (0.12.47: mock `queued`) |

## Fix-diff review of batches 32–34 (2026-11-02)

Source: `/code-review` (high, no verify pass) of the uncommitted 0.12.45–0.12.47 diff after one
combined `/simplify`. Each row checked against the code.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| FD-1 | bug | `oauth.py` `_revoke`, `github/tasks.py` `revoke_later` | A primary-limit 429/403 on revocation is now `GitHubRateLimited`; `decide_retry` fails a wait above `GITHUB_MAX_RETRY_DELAY` at once, so a reset 30 minutes away ends the revocation on the first try (before: four backoff tries, also inside the reset window). | partial (both lose it; fixed: `revoke_later` retries after `min(wait, GITHUB_MAX_RETRY_DELAY)` until the attempts run out; docstrings name `GitHubRateLimited`) |
| FD-2 | deadlock | `sync.py` repositories step | `upsert_repository` calls `release_name`, which locks the name holder (another GitHub ID) out of ID order inside the sorted upserts. | accepted here (the same pattern in discovery's upserts); fixed (0.12.63, CR4-8): `storage.lock_for_upsert` before the batch |
| FD-3 | data | `sync.py` contributions | A skipped name is the plan's; after a redirect the stored row has the new name, so its link is not kept. | accepted (design Risks: needs a rename and a 403 in one run; the next readable sync restores it) |
| FD-4 | data | `client.ts` `csrfToken` | A keepalive call joining a non-keepalive pending CSRF request loses its event on unload. | accepted (design D3 Risks; one request's window, fire-and-forget event) |
| FD-5 | robustness | `client.py` `_count_from_single_item_page` | A `rel="last"` outside the API origin now fails the count. | accepted (only a tampered or misconfigured response; a base URL with a port matches its own origin) |
| FD-6 | robustness | `client.py` `_send` | A malformed Location is httpx's `RemoteProtocolError`, so transient. | accepted (recorded as the D5 deviation of `github-services-review-fixes`) |
| FD-7 | altitude | `storage.py` `replace_*` | The row-lock precondition lives in docstrings; locking inside `replace_*` would remove it. | wontfix (`/simplify` moved it out: inside, it cost a query per analysis where the row is already held) |
| FD-8 | logging | `errors.py` `error_for_response` | Messages say `GET` for the revocation's DELETE. | fixed (`method` parameter, default `GET`; revocation passes `DELETE`) |
| FD-9 | efficiency | `features/auth/api.ts` `useDeleteGitHubData` | After `AppShell` already redirected, the hook's `replace('/onboarding')` adds a location key: one more `/sync/versions` request and an onboarding remount. | accepted (navigating first is not possible: onboarding sends a cached synced status back to `/app`; design D4 keeps the hook's navigation as the guarantee) |
| FD-10 | test | `tests/test_github_sync.py` `new_job` | The test helper shares its name with `services.jobs.new_job` (PENDING vs RUNNING). | fixed (renamed `running_sync_job`) |

## Sweep: `jobs/` (2026-11-02)

Source: full review sweep, `/code-review` (high, no verify pass) of `apps/backend/jobs/`
(`admin.py`, `api.py`, `models.py`, `serializers.py`, `tasks.py`), with `services/jobs.py` and
`services/job_guard.py`. Each row checked against the code. `/security-review`: nothing
(every query scoped to the user, no client-supplied ids, `error_detail`/`metadata`/`claim_token`
never serialized).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| JOB-1 | bug | `admin.py:7` | Every field read-only on a plain `ModelAdmin`: Add saves a job with no user (IntegrityError, 500); Delete removes jobs behind the app's cancel and finish flows. | confirmed; fixed (0.12.48: `NoAddDeleteAdmin`) |
| JOB-2 | race | `admin.py:10` | Save on the change page writes every column: overwrites a worker's status, claim or metadata written meanwhile, and `auto_now` bumps the heartbeat, so a dead job looks alive. | confirmed; fixed (0.12.48: no change permission, view only) |
| JOB-3 | bug | `api.py:61` | `/sync/status` returns a dead worker's job as RUNNING for up to `SYNC_STALE_AFTER_SECONDS` plus one recovery interval; the UI spins with Refresh disabled while `start_profile_sync` would replace it. | confirmed; fixed (0.12.48: `stalled` on every returned job, `job_guard.is_stalled`; the SPA keeps polling, says work stopped, enables Refresh / Try again) |
| JOB-4 | dead code | `models.py:85` | `SyncJob.is_active` is unused and counts dead RUNNING jobs, unlike `active_jobs()`. | confirmed; fixed (0.12.48: removed) |
| JOB-5 | efficiency | `admin.py:8` | No `list_select_related`: one user query per changelist row. | confirmed; fixed (0.12.48) |
| JOB-6 | consistency | `models.py:77` | The partial unique constraint repeats the active statuses next to `ACTIVE_STATUSES`. | confirmed; fixed (0.12.48: module-level `JobStatus`, `ACTIVE_STATUSES`; same stored values, no migration) |
| JOB-7 | consistency | `serializers.py:34` | Missing steps filled with the literal `"pending"`. | confirmed; fixed (0.12.48: `StepState.PENDING`) |
| JOB-8 | efficiency | `tasks.py:8` | Jobs are never pruned; the recovery scan by status and `updated_at` has no index; beat runs piled up while the worker was down all run. | partial (pruning is a retention decision, not taken); fixed (0.12.48: partial index `syncjob_active_updated_idx`, `jobs.0007`; `expires` on `recover-stale-jobs`) |
| JOB-9 | abuse | `api.py:46` | The cooldown counts COMPLETED syncs only: failed or cancelled syncs restart at once. | accepted (by design: a failed sync may be retried; it already ran its own backoff; the global user throttle applies) |
| JOB-10 | consistency | `api.py:62` | `last_synced_at` is the last completed sync; data versions' `github` the last finished one. | accepted (by design since 0.12.31: "last synced" means successful; versions also count a failed sync that stored data) |

## Sweep: `developers/` (2026-11-02)

Source: full review sweep, `/code-review` (high, no verify pass) of `apps/backend/developers/`
(`admin.py`, `api.py`, `models.py`, `management/commands/reanalyze_profiles.py`), with
`services/profiling/` and `services/jobs.py` as context. Each row checked against the code.
`/security-review`: nothing (every query scoped to the requesting user, no client-supplied ids,
evidence `detail` rendered as text, `experience_level` and `analysis_config` never serialized).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| DEV-1 | data loss | `admin.py:15` | `ReadOnlyAdmin` blocks add and change but not delete: deleting a `Skill` or `Interest` cascades to every developer's rows; deleting a profile cascades candidates, recommendations and recommended issues outside `data_deletion` (no developer lock, no job cancel, no audit). | confirmed; fixed (0.12.49: `ReadOnlyAdmin` on `NoAddDeleteAdmin`) |
| DEV-2 | efficiency | `admin.py:46` | Changelists show foreign keys without `list_select_related`: one query per row. | confirmed; fixed (0.12.49) |
| DEV-3 | display | `models.py:129`, `api.py` prefetches | Evidence ordered `-observed_at`: PostgreSQL puts NULLs first, so undated evidence (no README sync time, empty repository) precedes the newest. | confirmed (minor); fixed (0.12.49: `EVIDENCE_ORDER`, nulls last, then pk; `developers.0002`, state only) |
| DEV-4 | consistency | `reanalyze_profiles.py:22` | Deactivated users queued; their analysis starts discovery. | confirmed (minor); fixed (0.12.49: `is_active=True`; `--user` names an inactive user) |
| DEV-5 | efficiency | `reanalyze_profiles.py:32` | A user with a running sync gets a second analysis and discovery (`_start_job` checks only the analysis type). | confirmed (minor; operator command, newest result wins); fixed (0.12.49: skipped and counted `syncing`; a stalled sync does not hold it back) |
| DEV-6 | robustness | `api.py:72`, `features/profile/api.ts` | The SPA reads one page of 200; past 200 skills the lowest are cut. | accepted (catalog 170 skills, 16 interests; analysis creates catalog entries only); guard test fails once a catalog passes `max_page_size` |
| DEV-7 | bug | `api.py:101` | List order has no unique tiebreaker (`Skill.name` not unique): tied rows can repeat or skip across pages. | confirmed (minor); fixed (0.12.49: `pk` last, also in `Meta.ordering`) |
| DEV-8 | robustness | `api.py:119` | `InterestListView.get_queryset` has no `swagger_fake_view` guard; works only while `filter_backends = []`. | confirmed; fixed (0.12.49) |
| DEV-9 | admin | `admin.py:55` | Interest evidence is not shown in the admin, unlike skill evidence. | confirmed; fixed (0.12.49: `InterestEvidenceInline`) |

## Sweep: `repositories/` (2026-11-02)

Source: full review sweep, `/code-review` (high, no verify pass) of `apps/backend/repositories/`
(`admin.py`, `api.py`, `serializers.py`, `tasks.py`), with `services/repositories/` and
`services/github/retry.py` as context. Each row checked against the code. `/security-review`:
nothing (both endpoints scoped to the user, no ids from the client, `UserRepository` never
serialized, refreshes use the app's credentials, outbound requests only to the API origin).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| REPO-1 | observability | `tasks.py:59` | Any non-GitHub error (bug, database) becomes `internal_error`: no retry, a one-line warning without traceback, recorded and delayed 60 minutes; the same failure repeats silently. | confirmed (logging); fixed (0.12.50: `logger.exception` for `internal_error`, as `revoke_later`). Retrying database errors would change the shared policy for every task; the refresh delay already retries |
| REPO-2 | bug | `tasks.py:62` | `retries + 1` passed straight to `decide_retry`, not through `attempt_number(eager=)`: an inline run retries inline with no backoff (up to `SYNC_MAX_ATTEMPTS`). | confirmed (minor); fixed (0.12.50) |
| REPO-3 | robustness | `tasks.py:44` | `queue_batch` commits its stamps, then `.delay()` one by one without handling: a broker error leaves the rest stamped with no task for the `lost_before` window. | confirmed (minor); fixed (0.12.50: each send tried; refused ones `backlog.unmark_queued`; spec "Background refresh") |
| REPO-4 | efficiency | `tasks.py:67` | Two rate-limit retries (up to ~1812 s) outlast the queued window (1500 s): the backlog queues a second task (fenced by the claim, but fetched twice). | confirmed (minor); fixed (0.12.50: a scheduled retry `backlog.mark_queued`; spec "Background refresh") |
| REPO-5 | data integrity | `admin.py:43` | `RepositoryAdmin` (and `UserRepositoryAdmin`) fully editable: lifecycle and eligibility outside `lifecycle.py`, languages and dependencies without the row lock, deletes cascading into other users' candidates, recommendations and saves. | confirmed; fixed (0.12.50: view only, inlines cannot delete) |
| REPO-6 | data loss | `admin.py:17` | `ReadOnlyAdmin` allows delete (candidates, snapshots). | confirmed (as DEV-1); fixed (0.12.50: on `NoAddDeleteAdmin`) |
| REPO-7 | efficiency | `admin.py:59` | Three changelists without `list_select_related`. | confirmed; fixed (0.12.50) |
| REPO-8 | display | `serializers.py:24` | `/discovery/candidates` returns a released name (`owner/name~<id>`) and its old link until re-analysis. | accepted (the SPA does not call it; the refresh is queued at once since 0.12.36; a fix needs a nullable `html_url`, a contract change) |

## `/simplify` of batches 36–38 (2026-11-02)

Source: `/simplify` with four agents (reuse, simplification, efficiency, altitude) over one
combined diff of the uncommitted 0.12.48–0.12.50 code and tests (generated API files and
lockfiles excluded). Findings deduplicated; each checked against the code.

| ID | Type | Where | Finding | Status |
|---|---|---|---|---|
| SIM-1 | reuse | `jobs/admin.py`, `developers/admin.py`, `repositories/admin.py` | Three copies of "`NoAddDeleteAdmin` plus no change permission". | fixed (`core.admin.ViewOnlyAdmin`; app copies removed) |
| SIM-2 | logging | `repositories/tasks.py` `process_repository_backlog` | `logger.exception` ran after the `except` block: it logged `NoneType: None`, no traceback. | fixed (warning with `exc_info` inside the `except`, per refused send; `unmark_queued` of no ids is a no-op) |
| SIM-3 | simplification | `repositories/tasks.py` `_refresh` | Two near-identical log calls for `internal_error` and other failures. | fixed (one `logger.log`, level and `exc_info` from the code) |
| SIM-4 | reuse | `tests/test_*_review_fixes.py` | Three `superuser` fixtures, three view-only permission tests, three changelist query-count closures. | fixed (`shared_fixtures.assert_view_only`, `changelist_queries`; pytest-django `admin_user`/`admin_client`) |
| SIM-5 | simplification | `features/sync/pipeline.ts` | `isActive` repeated per stage after finding the current job. | fixed (branches on the first active job) |
| SIM-6 | simplification | `app/jobTransitions.ts` `isStalled` | Re-checked `isActive`; the server sets `stalled` only for RUNNING. | fixed (reads `job.stalled`) |
| SIM-7 | duplication | `pipeline.ts`, `OnboardingPage.tsx` | The stalled notice written twice with different endings. | fixed (`features/sync/messages.STALLED_NOTICE`) |
| SIM-8 | data loss | `recommendations/admin.py` (feedback imports it) | Its own `ReadOnlyAdmin` still allows delete (as DEV-1, REPO-6). | fixed (`issues/` in 0.12.51, ISS-1, ISS-2; `recommendations/` and `feedback/` in 0.12.52, REC-1: `ReadOnlyAdmin` removed) |
| SIM-9 | altitude | `reanalyze_profiles.py` | The "sync is running" check lives in the command, not in `start_profile_analysis`. | wontfix (design D4 of `developers-review-fixes`: specified job behavior for every caller) |
| SIM-10 | altitude | `_refresh`, `revoke_later`, `run_tracked_job` | Three call sites, two traceback rules. | deferred (`ideas.md` §15 "One traceback rule for job failures") |
| SIM-11 | altitude | `repositories/tasks.py`, `backlog.py` | Stamp, unstamp and renew rules split between the task and `backlog`. | deferred (`ideas.md` §15 "The backlog owns sending its refreshes") |
| SIM-12 | simplification | `backlog.mark_queued`, `unmark_queued` | One `update` with two values. | wontfix (two names read better at the call sites) |
| SIM-13 | efficiency | `reanalyze_profiles.py` | One `active_jobs(...).exists()` per user. | accepted (operator command; an `Exists` annotation would need the private `_stale_running`) |
| SIM-14 | simplification | `jobs/models.py` | `_ACTIVE` next to `ACTIVE_STATUSES` and the class aliases. | wontfix (the migration holds a list of strings; another form generates a migration) |
| SIM-15 | reuse | tests | `make_job`/`make_profile` variants, an inline snapshot, a branching tied-rows test. | wontfix (test-local shapes differ on purpose: age, confidence) |
| SIM-16 | efficiency | `syncjob_active_updated_idx` | Indexing `updated_at` costs heartbeat updates their HOT path. | accepted (a few running jobs; keeps recovery off a full scan) |

## Sweep: `issues/` (2026-11-03)

Source: full review sweep, `/code-review` (high, no verify pass) of `apps/backend/issues/`
(`admin.py`, `api.py`, `models.py`, `serializers.py`), with `services/issues/` and
`services/matching/issues.py` as context. Each row checked against the code. `/security-review`:
nothing (the detail is scoped to the user's own recommendations, anything else 404; the issue
body is returned as plain text and rendered escaped).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| ISS-1 | data loss | `admin.py:9` | `IssueAdmin` on `ReadOnlyAdmin` allows delete: an `Issue` cascades into every developer's `RecommendedIssue` outside `data_deletion` and the lock order, and the recommendations' issue snapshots (`relevant_issue_count`, `issue_difficulties`, `issue_contribution_types`) keep counting it, so the difficulty and contribution-type filters return recommendations with no matching issue until the next generation. | confirmed (SIM-8 for this module, as DEV-1, REPO-6); fixed (0.12.51: `core.admin.ViewOnlyAdmin`) |
| ISS-2 | data loss | `admin.py:30` | `RecommendedIssueAdmin` allows delete: the same stale snapshots, for one developer. | confirmed; fixed (0.12.51: `ViewOnlyAdmin`) |
| ISS-3 | staleness | `api.py:33` | "matched" uses the current skills, the reasons come from the last generation. | accepted (a profile analysis moves `analyzed_at`; the freshness sweep regenerates within 30 minutes; design D3) |
| ISS-4 | staleness | `api.py:25` | An issue assigned or locked since generation is still shown. | accepted (the issue fetch moves `issues_synced_at`; regeneration re-runs `load_issues`, which drops it; a filter here alone would leave the recommendation listing a link that 404s; D3) |
| ISS-5 | efficiency | `admin.py:9` | The issue changelist prints `Repository.__str__` per row: one query per row. | confirmed; fixed (0.12.51: `list_select_related = ("repository",)`; `RecommendedIssueAdmin` needs none, its `__str__`s read ids) |
| ISS-6 | staleness | `api.py:25` | An issue transferred between two pooled repositories keeps its old link until regeneration. | accepted (bounded by the freshness sweep, as ISS-4; D3) |
| ISS-7 | duplication | `serializers.py:35` | Technology `source` choices repeat the literals of `services/issues/technologies.py`. | confirmed; fixed (0.12.51: `technologies.TITLE`, `LABEL`, `BODY`; OpenAPI unchanged) |
| ISS-8 | cleanup | `admin.py:20`, `admin.py:32` | `readonly_fields` do nothing once change permission is off. | confirmed; fixed (0.12.51: removed) |

## Sweep: `recommendations/` (2026-11-03)

Source: full review sweep, `/code-review` (high, no verify pass) of `apps/backend/recommendations/`
(`admin.py`, `api.py`, `models.py`, `serializers.py`, management commands), with
`services/ranking/`, `services/evaluation/` and `feedback/admin.py` as context. Each row checked
against the code. `/security-review`: nothing (every endpoint scoped to the user, another user's
id is 404; no score, rank or signal values serialized; admin HTML escapes the version; command
paths are operator input).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| REC-1 | data loss | `admin.py:10` | `ReadOnlyAdmin` allows delete: `RecommendationAdmin` and the three feedback admins delete recommendations (reasons and recommended issues cascade outside `lock_developer`), dismissals (the project returns with no `undismissed` event or generation) and append-only feedback history. | confirmed (SIM-8); fixed (0.12.52: `ReadOnlyAdmin` removed, all four on `core.admin.ViewOnlyAdmin`, reason inline cannot delete) |
| REC-2 | data integrity | `admin.py:21` | `ScoringConfigAdmin` allows add and delete; `PROTECT` blocks only configurations with recommendations, so an evaluated version can be deleted and stored again with other numbers, and the active one deleted (generation then fails `NoScoringConfig`). | confirmed (breaks "Versioned scoring configuration"); fixed (0.12.52: `NoAddDeleteAdmin`; seeds store configurations, description stays editable) |
| REC-3 | bug | `evaluate_ranking.py:111` | `--top-n 0` falls back to the default; `--top-n -5` reaches `kept[:top_n]` and drops the last 5. | confirmed; fixed (0.12.52: below 1 refused, `is not None`) |
| REC-4 | data integrity | `models.py:73` | `ScoringConfig.save` skips the check when the row is gone; Django inserts it again with the instance's numbers. | confirmed; fixed (0.12.52: `ImmutableConfig`) |
| REC-5 | design | `evaluate_ranking.py:171` | `--write-baseline` accepts `--top-n`, while activation judges at the pinned top N. | false positive (spec "at the pinned minimum score default and top N unless a top N is given"; format 4 records top N per dataset) |
| REC-6 | efficiency | `admin.py:61`, `feedback/admin.py` | No `list_select_related`: one query per row for developer, repository and config (user and repository in feedback). | confirmed; fixed (0.12.52) |
| REC-7 | robustness | `import_judgments.py:28`, `benchmark_sheet.py:30` | A JSON list or a candidate without `repository` crashes with a traceback; `benchmark_sheet` counted rows after writing the CSV. | confirmed (minor); fixed (0.12.52: `SheetError` from `sheet._single_developer`/`_candidate_names`, `candidate_count` before writing) |
| REC-8 | display | `serializers.py:29` | The excerpt drops a complete word ending exactly at the limit. | confirmed; fixed (0.12.52: cut at `limit + 1`) |
| REC-9 | efficiency | `api.py:172` | Status runs a `Max` aggregate the latest row already answers (4 queries). | confirmed (minor); fixed (0.12.52: 3 queries) |
| REC-10 | display | `serializers.py:20` | `_`/`~` stripped inside words (`my_package`, `~/.config`); HTML entities shown literally. | confirmed; fixed (0.12.52: `_` at word edges, `~~` only, `html.unescape`) |

## Sweep: `feedback/` (2026-11-03)

Batch 42. Source: full review sweep, `/code-review` (high, no verify pass) of
`apps/backend/feedback/` (`admin.py`, `api.py`, `models.py`, `serializers.py`), with
`services/feedback.py` as context. Each row checked against the code. The uncommitted
`admin.py` change (`ViewOnlyAdmin`, REC-1/REC-6) raised nothing. `/security-review`: nothing
(every endpoint goes through `IsAuthenticated` and the CSRF-checking session auth; recommendation
endpoints look up `pk` with `developer__user`, another user's id is 404; `opened_issue` must name
one of that recommendation's issues; clients post only `CLIENT_ACTIONS`; list, unsave and restore
filter `user=`; a forged cursor moves only within the caller's rows, unreadable → 400).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| FB-1 | race | `feedback/api.py:61`, `services/feedback.py:79` | The `opened_issue` relevance check (`RecommendedIssue` of this recommendation) runs in the view before any lock; `record` locks the recommendation and the issue but never re-checks the link. A generation committing in between keeps the recommendation id (upsert) and replaces its `RecommendedIssue` rows (`ranking/service.py:250`), so an event is stored for an issue no longer offered; business rule in a view. | confirmed (generation rewrites `RecommendedIssue` while holding the recommendation row locks, `service.py:178`, so a check after `_current(lock=True)` is consistent); fix: `record(..., issue_id=)` checks the link under the lock, view passes the id (no event when the issue left, as for a gone recommendation; a 400 stays for an id never relevant before the lock). Fixed (0.12.53, `feedback-review-fixes`): `record(..., issue_id=)` locks the issue and checks the link under the recommendation lock; an issue closed or dropped meanwhile: 204, no event (FD2-6, owner) |
| FB-2 | data quality | `services/feedback.py:98` | Only `viewed` is de-duplicated; `opened_repository` and `opened_issue` store one event per POST (double click, a script loop), and `feedback_report` shares count events, so one user can raise a config's or bucket's positive share and move a calibration verdict. | partial (as specified: spec "Recording feedback" de-duplicates `viewed` only; impact bounded to the analytics report, which also prints distinct users; opening twice is two real opens). Decide: accept, or de-duplicate opens within the view window (spec delta). Accepted (owner, 2026-11-03) |
| FB-3 | bug | `feedback/api.py:93`, `features/feedback/api.ts:70` | Unsave by recommendation id (`DELETE /recommendations/{id}/save`) looks the recommendation up first: once a freshness generation drops it, a still-rendered card's Unsave gets 404 and the save stays on `/saved`, though `unsave` is meant to work whether or not the repository is still recommended. | confirmed; fix: the card's unsave calls `DELETE /saved/{repository_id}` (the hook already exists, `useUnsaveRepository`), or the view falls back to the repository; no spec change. Fixed (0.12.53): the card and detail Unsave call `DELETE /saved/{repository_id}`; the old endpoint stays |
| FB-4 | gap | `services/feedback.py:171` | Restore does not check the repository is still pooled and scorable: a repository pruned or made ineligible meanwhile is in neither list after restore. | false positive (spec: after restore it "MAY be recommended again by the next generation"; the UI promises only that it is no longer hidden; it can return when discovery finds it again) |
| FB-5 | efficiency | `feedback/api.py:40` | `_own_recommendation` joins repository and config, and `record`/`save` read the same row again (`_current`), so every feedback, save and dismiss request reads the recommendation twice; `SaveView.delete` needs only `repository_id`. | confirmed (minor; `viewed` fires per card shown); fix: ownership check with `.only("pk", "repository_id")`, the service's locked re-read is the full read (`dismiss` reads `recommendation.repository` and needs it). Fixed (0.12.53): `_own_recommendation` loads `only("pk", "repository_id")`, `dismiss` reads the repository by id |
| FB-6 | efficiency | `feedback/api.py:162` | Cursor mode runs `queryset.count()` on every page besides the keyset query. | confirmed (minor: per-user rows on `saved_keyset_idx`/`dismissed_keyset_idx`; the spec requires `count` to be the total on every page, so dropping it is a spec change). Accept unless cheap. Accepted (owner, 2026-11-03) |
| FB-7 | design | `feedback/api.py:126` | `KeysetPagination` is generic paging living in `feedback/api.py`; `/recommendations` keeps page numbers that shift on change. | wontfix (one consumer, so moving it gains nothing yet; `/recommendations` is ordered by `rank`, which a regeneration reassigns wholesale, so a keyset would not keep pages stable there either; the SPA refetches the list by data versions) |

## Sweep: `services/profiling/` (2026-11-03)

Batch 43. Source: full review sweep, `/code-review` (high, no verify pass) of
`apps/backend/services/profiling/` (no diff; the module as it stands). Each row checked against
the code; PROF-1…PROF-8 reproduced with the backend venv. `/security-review`: nothing (`tomllib`
and `json` only, pom/Gradle by regex, so no XML parser and no XXE; no `eval`/`pickle`/`yaml`/
subprocess; ORM only; catalog rows only for taxonomy slugs, names from the taxonomy; writes only
under the analyzed user's profile; evidence details capped and rendered as React text).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| PROF-1 | crash | `text.py:35` | `PhraseMatcher.find` looks the match up by `.lower()`, but `re.IGNORECASE` also matches Unicode case-fold variants (`ı` U+0131, `ſ` U+017F), whose lowercase is not the catalog key → `KeyError`. Reproduced: `PLAIN_MATCHER.find("Kotlın developer")` → `KeyError('kotlın')`, `SYNONYM_MATCHER.find("Machıne learning")` → `KeyError('machıne learning')`. Untrusted text reaches it: a profile README fails the analysis; a repository description (`matching/signals.py:98`) or an issue title/body (`issues/technologies.py:26`, `:31`) fails generation or issue analysis for every user whose pool holds that repository. | confirmed (highest priority of the batch); fix: key the map by `casefold()` and look up `match.group(0).casefold()`, skip a miss; test with `ı`, `ſ` and `K` (Kelvin sign). Fixed (0.12.54, `profiling-review-fixes`): `casefold()` keys and lookup, a miss is skipped |
| PROF-2 | wrong evidence | `readme.py:53` | `tech_sections` reads `#` lines inside fenced code as ATX headings. Reproduced: `## About` + a bash fence with `# install tools` → a section "install tools" (`tool` matches `_SECTION_TITLE`) yielding go and rust; `## Skills\n- Python` + a fence with `# setup` + `- Go` ends the section at the comment, Go lost. | confirmed; fix: skip lines inside ``` / ~~~ fences when collecting headings. Fixed (0.12.54): fenced lines are never headings (still section text) |
| PROF-3 | wrong evidence | `readme.py:133` | Headings inside HTML comments count, and the section text starts after `<!--`, so `plain_text` never strips the comment. Reproduced: `<!--\n## Tech stack\n- Go\n- Rust\n-->` → go, rust ("Tech stack" section). Template READMEs leave such placeholders; badges and alt text inside comments count too. | confirmed; fix: drop `<!-- ... -->` from the README before any extraction (as `classify._HTML_COMMENT` for issues, D-12). Fixed (0.12.54): HTML comments dropped before README extraction |
| PROF-4 | wrong data | `manifests.py:56` | `parse_pyproject` iterates `project.dependencies`, each `optional-dependencies` and `dependency-groups` value without checking for a list; a string is iterated per character. Reproduced: `optional-dependencies={dev="pytest"}` → `p, y, t, e, s, t`. Junk `RepositoryDependency` rows; they also set `has_dependencies`, which keeps a lists/docs repository eligible under `not_code`. | confirmed; fix: `_pep508_names` takes only a list (else nothing); same for the `.values()` mappings (a non-dict skips). Fixed (0.12.54): only lists of specs and tables of groups are read |
| PROF-5 | lost evidence | `manifests.py:45` | `parse_requirements` skips every line containing `://`, so a PEP 508 direct reference (`django @ https://...`) loses its name. Reproduced: only `flask` of `django @ https://example.com/django.whl\nflask`. | confirmed (minor); fix: match `name @ ` before the URL skip (bare URLs and `-e` lines still skipped). Fixed (0.12.54): `name[extras] @ URL` keeps its name |
| PROF-6 | wrong evidence | `manifests.py:116` | `parse_pom` and `parse_gradle` match commented-out dependencies. Reproduced: `<!-- <dependency>…a…b…</dependency> -->` → `a:b`; `// implementation "org.x:y:1"` → `org.x:y`. | confirmed; fix: strip `<!-- -->` (pom) and `//` / `/* */` comments (Gradle; outside string literals is enough for coordinates) before matching. Fixed (0.12.54): pom `<!-- -->`, Gradle `/* */` and `//` after whitespace stripped |
| PROF-7 | display | `readme.py:28` | The ATX regex's closing `#*` takes a trailing `#` with no space before it. Reproduced: `## Languages: C#` → title "Languages C" (`_clean_title` also drops `:`); evidence detail misnames the section. | confirmed (minor); fix: closing sequence only after whitespace (`(?:\s+#+)?\s*$`, CommonMark). Fixed (0.12.54): closing `#` only after whitespace |
| PROF-8 | spec gap | `collectors.py:81`, `interests.py` | Contribution evidence (skills: `pull_request`, `commit`, `repeated_contribution`; interests: `contribution`) never checks `contribution.repo.is_fork`; the module docstring says "forks never count". | partial: interest-detection spec says "Forked repositories SHALL NOT provide evidence" (violated); skill-detection's "Contribution evidence" is silent (its fork rule covers owned repositories). Decide: skip forks in both (pushes to someone's fork are rare; merged PRs to a fork are unusual), or document that contributions to forks count; either way the docstring and one spec need aligning. Decided by the owner (2026-11-03): forks never count. Fixed (0.12.54): `ProfileInput.contributed_work` for skills and interests; `skill-detection` spec delta; experience ignores forks too (FD2-5, owner) |
| PROF-9 | contention | `analysis.py:225`, `:290` | `_upsert_catalog_skills`/`_interests` (`bulk_create(update_conflicts=True)`) rewrite every matched shared `Skill`/`Interest` row on every analysis, inside the `_persist` transaction (`job_write`), so concurrent analyses (`reanalyze_profiles` on 4 threads, sync-triggered) queue on hot rows (`python`, `javascript`) until the previous one commits, and each run leaves dead tuples. | confirmed (by reading; not timed). Fix: `ignore_conflicts=True` insert, then update only rows whose name or category differ (names change only with the taxonomy), keeping the global sorted order (B-3). Fixed (0.12.54): insert-ignore, then `bulk_update` of changed rows only |

## Sweep: `frontend/src/app/` (2026-11-03)

Batch 44. Source: full review sweep, `/code-review` (high, no verify pass) of
`apps/frontend/src/app/` (no diff; the module as it stands), with `features/sync/api.ts` and
`features/auth/api.ts` as context. Each row checked against the code (by reading; nothing run).
`/security-review`: nothing (query cache in memory only, no persister or web storage; sign-in is
a full-page OAuth round trip, so no cache survives to another user; every sign-out path clears
after the server confirms; CSRF token only on mutating same-origin requests; navigation targets
and fetch paths are constants; no `eval`/`innerHTML` sinks).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| APP-1 | bug | `jobTransitions.ts:39` | A job that disappeared (`status.job` null) counts as newly finished: delete-data's `invalidateQueries(['sync'])` (`features/auth/api.ts:79`) sees `5:COMPLETED` → `:` and calls the sync refresh, which invalidates `['jobs']` (just cancelled, still observed) and the versions. A versions answer (all null) landing before the later `resetQueries` makes the layout invalidate every `['profile', ...]` area while the dashboard still observes them: requests for deleted data, the case U-7 meant to avoid. | confirmed (window until `replace('/onboarding')`; extra requests, no wrong data kept: the keys are removed after); fix: refresh only when `status.job` is non-null. Fixed (0.12.55): a status without a job never refreshes |
| APP-2 | race | `jobTransitions.ts:34` | The finished-job comparison runs inside the `queryFn`: an `invalidateQueries` (default `cancelRefetch`) that cancels an in-flight status fetch restores the cached data, and both the abandoned and the new run read the same `previous` and call `refresh()`; the second refresh can cancel and restart other status queries in turn. Same defect U-6 fixed for data versions. | confirmed (duplicate refreshes, extra requests; no wrong state); fix: compare in an effect on the status data (one observer per status, as `useDataVersions`), or pass the signal (APP-3) so the abandoned run stops before comparing. Fixed (0.12.55): status fetches take the query's signal; a cancelled fetch stops before comparing |
| APP-3 | cleanup | `jobTransitions.ts:31` | `fetchStatus` takes no `AbortSignal` (`() => apiFetch(...)` in each status hook), so `cancelQueries` (sign-out's `leave`, APP-2's cancel) never aborts a status request, and its `refresh()` still runs after the user left. | confirmed (minor; after sign-out the invalidated queries are removed by `clearSignedInData`); fix: `queryFn: ({ signal }) => fetchStatusAndRefresh(..., () => apiFetch(path, { signal }), ...)`, and return early on `signal.aborted` before comparing. Fixed (0.12.55): with APP-2; `cancelQueries` aborts status requests |
| APP-4 | bug | `features/sync/api.ts:43` | `useStartSync.onSuccess` writes the new PENDING job with `setQueryData` without cancelling an in-flight `/sync/status` fetch (focus, route change); the older answer (finished job 5) lands after and replaces job 6, `refetchInterval` sees no active job and stops polling, so job 6's finish is never seen until the next focus or route change. | confirmed; fix: `await queryClient.cancelQueries({ queryKey: syncStatusKey })` before `setQueryData` (check the other start mutations: generation and restore set or invalidate their status the same way). Fixed (0.12.55): `useStartSync` cancels the sync status before writing the job (the only status `setQueryData`) |
| APP-5 | bug | `queryClient.ts:62` | A sign-out mutation sets `signedOut = true` on mutate and back to false on error: a 401 swallowed while it was pending (the session did end server-side, the logout answer was lost) is never reported, and the network error itself ends nothing. The user stays on signed-in pages with a dead session. | partial (bounded: the next request that answers 401, a focus or route change refetching versions, ends the session); fix: remember a swallowed 401 while pending and report it on the mutation's error. Fixed (0.12.55): a 401 ignored while a sign-out is pending ends the session if that sign-out fails |
| APP-6 | robustness | `session.ts:25` | `leave` awaits `navigate`; `unauthenticated` calls `void endSession(...)`, so a rejected navigation is unhandled and `signedOut` stays true until a successful `/auth/me`, which signed-in pages may never fetch again: later 401s are ignored. | partial (React Router's `navigate` to a constant path with no loaders or blockers does not reject today); fix: `.catch` in `unauthenticated` that resets `signedOut` (cheap guard). Fixed (0.12.55): a rejected `endSession` resets `signedOut` |
| APP-7 | design | `session.ts:31` | `endSession` leaves clearing the cache to `LandingPage`'s effect on `?auth_error=session_ended`; a navigation replaced before it mounts would keep the user's data cached. | accepted (by design: clearing before the navigation commits let the dashboard refetch, see 0.12.8; only the same user's data, in memory; the security review found no cross-user path since sign-in reloads the page) |
| APP-8 | efficiency | `dataVersions.ts:61` | The user's own save, unsave, dismiss and restore move the `recommendations` version (`feedback.LIST_ACTIONS`, 0.12.44), so the next route change refetches every recommendations-area query (list pages and filters, details, issues, saved, dismissed) the mutation already refreshed. | partial (intended for other tabs and devices; redundant in the acting tab); fix: after a list mutation, refetch the versions so the new time becomes the seen value without invalidating (a `seed` path in `useDataVersions`), or accept. Accepted (0.12.55): the time is meant for other tabs and devices; a "seen" path could also hide a concurrent background change |
| APP-9 | test gap | `dataVersions.test.ts:33` | Nothing enforces CLAUDE.md's rule that every derived `['profile', ...]` query is listed in `AREA_KEYS`; the test only checks listed keys start with `profile`. A forgotten key stays stale for its 5-minute `staleTime` after background changes. | confirmed; fix: export the profile query keys from one place (or scan `queryClient` in a render test of every page) and assert each is covered by an area. Fixed (0.12.55): `dataVersions.test.ts` scans the sources for `['profile', '<name>'` keys |
| APP-10 | efficiency | `dataVersions.ts:62` | One `invalidateQueries` per key (up to 9), each scanning the cache. | confirmed (minor; small caches); fix: one call with a predicate over the changed keys (`partialMatchKey`), or accept. Fixed (0.12.55): one `invalidateQueries` with a `partialMatchKey` predicate |



## Fix-diff review of 0.12.55–0.12.57 (2026-11-03)

Batch 52. Source: `/code-review` (high, no verify pass) of the uncommitted 0.12.55–0.12.57 code
after the batch 51 `/simplify`. Each row checked against the code by reading; the owner chose to
fix all. Folded into 0.12.57.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| CR-1 | bug | `RecommendationDetailPage.tsx`, `SavedPage.tsx`, `DiscoveryCard.tsx`, `RecommendationList.tsx` | Still checked `isError` before data: one failed refetch or poll replaced shown content (ROUTE-2 class; SIM2-9). | fixed: data first everywhere; `src/components/Loaded` (shared, from `AppShell`) for the dashboard sections and the discovery card; spec "Failed refresh keeps the page" edited directly |
| CR-2 | bug | `SavedPage.tsx` | Part of CR-1 (saved and hidden lists). | fixed with CR-1 |
| CR-3 | wording | `features/issues/evidence.ts` | "From a enhancement label" / "a infrastructure". | fixed: "a" or "an" by the first letter |
| CR-4 | robustness | `features/issues/evidence.ts` | `signals: [null]` or `difficulty_evidence: null` still crashed the page. | fixed: non-objects skipped, missing evidence reads as none |
| CR-5 | altitude | page gates | Rule applied page by page. | fixed with CR-1 (`Loaded`); detail pages and the saved lists keep inline data-first gates (404 and empty states) |
| CR-6 | ux | `routes/LandingPage.tsx` | Blank page while `/auth/me` loads or retries. | fixed: "Loading…" as `RequireAuth`; spec "Sign-in page while the identity loads" edited directly |
| CR-7 | bug | `app/queryClient.ts` | After a failed navigation the identity was already removed, so the next 401 went to sign-in without the notice. | fixed: the cached identity is put back when `endSession` rejects |
| CR-8 | display | `components/Fact.tsx` | Recommendation detail values now right-aligned. | no change: stated in the 0.12.57 changelog |
| CR-9 | test design | `tests/test_issue_signal_wording.py` | Regex over TypeScript source. | kept: SIM2-11 (an OpenAPI enum would replace it; API change) |
| CR-10 | style | `SavedPage.tsx`, `SkillGroups.tsx` | `@/components/ExternalLink` import in the third-party group. | fixed |

Found while fixing: the refetch tests for the issue page, the recommendation detail page and the
saved lists asserted before TanStack notified the observers (it batches on a timer), so they
passed against the old gates; each now waits (`settle`) and fails against the old code.

## `/simplify` of 0.12.55–0.12.57 (2026-11-03)

Batch 51. Source: `/simplify` (reuse, simplification, efficiency, altitude; one combined diff of
the uncommitted 0.12.55–0.12.57 frontend code and its backend test). Applied before commit, folded
into 0.12.55–0.12.57. The fix-diff `/code-review` was not run.

| ID | Type | Where | Finding | Status |
|---|---|---|---|---|
| SIM2-1 | simplification | `app/jobTransitions.ts` | `signal` passed twice (argument and a `fetchStatus(signal)` that took it back) at three status hooks. | fixed: `fetchStatusAndRefresh(queryClient, key, path, signal, refresh)` fetches itself |
| SIM2-2 | simplification | `app/queryClient.ts` | Three flags (`signedOut`, `signingOut`, `missed401`) for one sign-out state. | fixed: a failed sign-out refetches `/auth/me`; the identity's 401 ends the session (APP-5 kept) |
| SIM2-3 | dead code | `app/dataVersions.ts` | `useDataVersions(enabled)` had no caller passing it. | fixed: parameter removed |
| SIM2-4 | reuse | `routes/AppShell.tsx`, `features/sync/messages.ts` | The same medium date-time formatter twice. | fixed: `lib/format` `formatDateTime`, `formatTime` |
| SIM2-5 | simplification | `routes/AppShell.tsx` | Three copies of data → list / error → loading. | fixed: `Loaded` component; `analyzed` local dropped |
| SIM2-6 | reuse | `RepositoryList`, `SkillGroups`, `InterestList`, `SavedPage` | Hand-written new-tab links (`RepositoryList` had `rel="noreferrer"` only). | fixed: `ExternalLink` |
| SIM2-7 | efficiency | `app/dataVersions.test.ts` | Eager raw glob of every source at module load. | fixed: lazy glob, loaded in the test |
| SIM2-8 | reuse | `app/jobTransitions.test.ts` | Own job builder and hand-built held promise. | fixed: `COMPLETED_JOB`, stubbed `fetch` with one `held()` helper |
| SIM2-9 | altitude | `RecommendationDetailPage`, `DiscoveryCard`, `SavedPage`, `RecommendationList` | Still check `isError` before data (ROUTE-2 class); a shared page-state helper would fix it once. | skipped: outside the diff; for the low-group sweep of those modules |
| SIM2-10 | altitude | `features/auth/api.ts` | `useSignedInUser` via outlet context needs each layout to pass it on. | skipped: design D5 of `routes-review-fixes` (a throwing `useMe` hook can run in the render where `endSession` removed the identity) |
| SIM2-11 | altitude | `tests/test_issue_signal_wording.py` | Reads `evidence.ts` source; an OpenAPI enum of signal names would let `tsc` check it. | skipped: API change; candidate for a later OpenSpec change |
| SIM2-12 | reuse | sync start error markup, test fail-then-refetch and `auxclick` helpers | Small repeats. | skipped: the two start error blocks differ (status vs alert); test repeats are two or three lines |

## Sweep: `frontend/src/routes/` (2026-11-03)

Batch 45. Source: full review sweep, `/code-review` (high, no verify pass) of
`apps/frontend/src/routes/` (no diff; the module as it stands). Each row checked against the code
(by reading; nothing run). `/security-review`: nothing (no unsafe sinks; `?auth_error=` is only a
key into a fixed own-keys message table; navigation targets and the sign-in URL are constants, the
OAuth callback redirects to settings paths only; `RouteId` admits `^[1-9]\d*$` safe integers, so
nothing else reaches an API path; `/app/*` and `/onboarding` sit under `RequireAuth`, public routes
render no user data).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| ROUTE-1 | bug | `SignedInLayout.tsx:14` | The mount skip compares with the first `location.key`, kept forever: `createBrowserRouter`'s first entry is `default`, so Back to it (e.g. `/app` after a detail page) never refetches the versions, and a background change stays unseen until focus or another route change. | confirmed; fix: a boolean "mounted" ref skips only the first run (with ROUTE-7). Fixed (0.12.56): compared with the previous route (path, query, fragment) |
| ROUTE-2 | bug | `AppShell.tsx:38`, `OnboardingPage.tsx:22` | `status.isError` is also true when a background refetch fails with data cached (TanStack v5): one failed sync status poll (5xx after two retries) replaces the whole dashboard (or onboarding) with "Could not load…" until a later poll succeeds. | confirmed; fix: error page only without `status.data` (as `RequireAuth` checks `me.data` first). Fixed (0.12.56): the error page only without status data |
| ROUTE-3 | bug | `AppShell.tsx:31`, `:89` | `analyzed = developer.isSuccess` turns false on a failed refetch with data cached: summary, discovery card, recommendations, skills, interests and languages are replaced by "Could not load your developer profile", and `useSkills`/`useInterests` are disabled. A data-versions refetch hitting one 5xx is enough. | confirmed; fix: gate on `developer.data` (`not_analyzed` only without data). Fixed (0.12.56): gated on `developer.data` |
| ROUTE-4 | bug | `AppShell.tsx:116`, `:127`, `:152` | Skills, interests and repositories check only `isPending`; a failed load renders `data?.results ?? []`, an empty section indistinguishable from "none found" (CLAUDE.md §3: failures never shown as empty data). | confirmed; fix: an error line when `isError` and no data. Fixed (0.12.56): an error line for a failed first load |
| ROUTE-5 | display | `OnboardingPage.tsx:79` | Onboarding shows `start.error.message` only; `sync_cooldown` gets no wait time (AppShell formats `retryAfter`). Reachable with a recent completed sync and a stalled active one ("Try again"). | confirmed (rare); fix: one `startErrorText(error)` in `features/sync/messages.ts` used by both pages. Fixed (0.12.56): `startErrorText` on both pages |
| ROUTE-6 | display | `AppShell.tsx:76` | The cooldown notice's "in N minutes" stays until the next mutate, so it is wrong once the wait has passed. | confirmed (minor); fix: `start.reset()` after `retryAfter` (timer) or word it with the time ("after 14:05"). Fixed (0.12.56): the cooldown names the clock time |
| ROUTE-7 | efficiency | `SignedInLayout.tsx:18` | Keyed on `location.key`, which also changes on state-only `replace` navigations: the dismiss flow (`navigate('/app', { state })`, then RecommendationList clearing the state) refetches the versions twice for one page view. | confirmed (minor); fix: key on `pathname + search`. Fixed (0.12.56): a state-only navigation is not a route change |
| ROUTE-8 | cleanup | `SignedInLayout.tsx:12`, `:18`, `:21` | `!!me`, `me &&` and `if (!me) return null` cannot be false: `routes.tsx` nests the layout under `RequireAuth`, which renders the `Outlet` only with `me.data`. | confirmed (dead code); fix: read `me` as defined (a non-null helper or `RequireAuth` passing it via outlet context). Fixed (0.12.56): identity through the outlet context (`useSignedInUser`) |
| ROUTE-9 | cleanup | `OnboardingPage.tsx:17` | The effect navigating to `/app` on COMPLETED repeats the render-time `<Navigate>` (`:26`): a completed sync comes with `last_synced_at` in the same status answer, so both fire (two navigations, two versions refetches); its promise is not `void`ed. | confirmed; fix: remove the effect. Fixed (0.12.56): effect removed |
| ROUTE-10 | ux | `LandingPage.tsx:24` | While `/auth/me` is pending the sign-in page shows, so a signed-in user opening `/` or an unknown path sees "Continue with GitHub" briefly; a click starts a new OAuth round trip (harmless); unknown paths never say "not found". | partial (flash confirmed; the click only re-signs in); fix: render nothing (or a spinner) while `me.isPending`; a not-found page for `*` is a separate UX choice. Fixed in part (0.12.56): nothing rendered while the identity loads; a not-found page left to the interface revamp |

## Sweep: `frontend/src/features/issues/` (2026-11-03)

Batch 46. Source: full review sweep, `/code-review` (high, no verify pass) of
`apps/frontend/src/features/issues/` (no diff; the module as it stands), with
`services/issues/classify.py` and `issues/` as context. Each row checked against the code (by
reading; nothing run). `/security-review`: nothing (issue body rendered as a React text child in a
`<pre>`, no markdown library or HTML sink; every other GitHub field is escaped text; the only
data-driven attribute is `href={github.url}`, GitHub's own `html_url`, with `rel="noopener
noreferrer"`; `IssueDetailView` filters by the requesting user, another user's issue is 404;
`opened_issue` posts ids only).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| FI-1 | wrong explanation | `evidence.ts:38` | `contributionBasis` quotes the canonical label (`classify.contribution_type` stores `{"by": "label", "value": <canonical>}`) as if it were the issue's GitHub label: an issue labeled `kind/docs` reads `From the "documentation" label`, while "From GitHub" lists no such label. | confirmed; fix: word it as the category (`From a documentation label`), or store the raw label that mapped to it (backend evidence change, `ISSUE_TAXONOMY_VERSION` bump). Fixed (0.12.57): "From a documentation label" (frontend wording) |
| FI-2 | robustness | `evidence.ts:31` | `difficultyBasis` returns the raw signal key for an unknown signal (`linked_prs`). | partial (every signal `classify` writes today — `label`, `body_length`, `technology_count`, `contribution_type`, `comments` — is handled); fix: skip unknown signals, plus a test pinning the list to `classify`'s signals. Fixed (0.12.57): `SIGNAL_TEXT` table, unknown signals dropped; backend test `test_issue_signal_wording.py` pins it to `classify` |
| FI-3 | bug | `IssueDetailPage.tsx:35` | `issue.isError` is checked before data: a failed background refetch (data versions after a route change or focus; 5xx after retries or network loss) replaces the issue being read with the DeadEnd. | confirmed (as ROUTE-2); fix: DeadEnd only without `issue.data` (a 404 on refetch still ends the page). Fixed (0.12.57): dead end only for a 404 or without data |
| FI-4 | robustness | `evidence.ts:13` | `difficulty_evidence.signals` is cast to `Vote[]` unchecked; a non-array crashes the render. | accepted (the backend always writes a list via `_vote`; evidence is recomputed on every fetch; a cheap `Array.isArray` guard can ride with FI-2). Guard added with FI-2 (0.12.57): `Array.isArray` |
| FI-5 | robustness | `IssueDetailPage.tsx:152` | `date.format(new Date(x))` throws `RangeError` for an unparsable time. | false positive (DRF `DateTimeField` serializes ISO 8601 or null, and null is skipped) |
| FI-6 | data quality | `IssueDetailPage.tsx:71` | `opened_issue` is recorded on `onClick` only; middle click and "Open link in new tab" (`auxclick`, context menu) record nothing, so `feedback_report` undercounts positive events. Same for `opened_repository` (`RecommendationCard.tsx:109`, `RecommendationDetailPage.tsx:153`). | confirmed; fix: also record on `onAuxClick` (button 1) in one shared external-link component; the context menu stays unrecorded (no event). Fixed (0.12.57): `components/ExternalLink` records click and middle click |
| FI-7 | wording | `IssueDetailPage.tsx:126` | No technologies shows "Not enough evidence", though zero mentions is a computed fact. | confirmed; fix: "No technologies mentioned". Fixed (0.12.57): "No technologies mentioned" |
| FI-8 | display | `IssueDetailPage.tsx:86` | "Why it matches" renders over an empty list when `reasons` is empty. | false positive (an issue is relevant only with a per-part contribution above 0, and its reasons come from the same contributions, T-11/T-1, so a stored relevant issue has at least one reason) |
| FI-9 | display | `IssueDetailPage.tsx:150` | State capitalized only for `open`. | false positive in practice (issues are listed with `state=open`, `client.py:460`, and closed ones are dropped on the next fetch, so stored rows are `open`); optional: a state text map |
| FI-10 | duplication | `IssueDetailPage.tsx:16`, `:74` | `Fact` duplicates `RecommendationDetailPage.tsx:43` (one with a note); the medium-date `Intl.DateTimeFormat` is repeated in four files (`SavedPage`, `SkillGroups`, both detail pages). | confirmed; fix: one `Fact` (optional note) in `src/components`, one `formatDate` in `src/lib`. Fixed (0.12.57): `components/Fact`, `lib/format.formatDate` |

## Sweep: `frontend/e2e/` with `vite.config.ts`, `csp.config.ts`, `playwright.config.ts` (2026-11-03)

Batch 47. Source: full review sweep, `/code-review` (high, no verify pass) of
`apps/frontend/e2e/` and the three configs (no diff; as they stand), with
`scripts/e2e-backend.mjs` as context. Each row checked against the code (by reading; nothing run).
`/security-review`: nothing (built policy `script-src 'self'` without `unsafe-*`, `object-src` and
`base-uri 'none'`; framing denied by Django's `X_FRAME_OPTIONS` and header policies, README tells
whoever serves `dist/` to send `frame-ancestors`; `host: true` judged hardening: public source,
`.env` under Vite's `fs.deny`, `ALLOWED_HOSTS` plus host-scoped Lax cookies keep the developer's
session out of reach, single fixed proxy target; `e2e_seed` refuses without the `e2e` app and
`contribfinder_e2e`; sessions file gitignored and outside `public/`; runner spawns with argument
arrays).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| E2EC-1 | test tooling | `fixtures.ts:21`, `playwright.config.ts:22`, `:41` | Mutating tests pick their seeded user by `testInfo.retry`, and the seed builds `RETRIES + 1` copies from the config constant: `--repeat-each 2` (same `retry` 0) or a second `--ui` run (servers not re-seeded) reuses the already-changed `e2e-save`/`e2e-delete` and fails; CLI `--retries 2` throws "No seeded session …, attempt 2". | partial (CI and `npm run e2e` use the config's retries and a fresh seed per run, so they pass; only ad-hoc flags break); fix: document the flags as unsupported in `playwright.config.ts`/README, or seed more copies via an env var and index by `retry + repeatEachIndex * attempts`. Fixed (0.12.58): data-changing users refuse `--repeat-each` and explain a missing retry copy at sign-in; supported flags documented in `playwright.config.ts` and README |
| E2EC-2 | hardening | `vite.config.ts:20` | `server.host: true` listens on every interface, and `preview` inherits it: the dev server and its `/api` proxy to the developer's Django are reachable on the LAN. | accepted as hardening (security review: no concrete exploit, see the note above); optional: default `host: 'localhost'` and let `docker-compose.yml` pass `--host` (the frontend container publishes 5173) |
| E2EC-3 | hardening | `playwright.config.ts:18` | The `E2E_DEV_SERVER=1` branch lacks `--host localhost`, unlike the preview branch, whose comment promises localhost only. | confirmed (local only, seeded throwaway database); fix: add `--host localhost` to the dev branch too (one constant with `SERVE`). Fixed (0.12.58): one `SERVE` with `--host localhost` for both servers |
| E2EC-4 | test isolation | `dashboard.spec.ts:53`, `auth.spec.ts:22` | The "read-only" `e2e-dashboard` user writes data: the relevant-issues link opens the detail page, which posts a `viewed` event (`RecommendationDetailPage.tsx:107`); `fixtures.ts:8` says the others are only read. | confirmed (no spec reads feedback today, so nothing fails); fix: correct the comment ("only views are recorded"), or route such tests through a mutating user if one ever asserts on feedback. Fixed (0.12.58): comment corrected |
| E2EC-5 | test design | `fixtures.ts:40` | The policy check matches Chromium's English console text, not the `securitypolicyviolation` event. | accepted (by design, 0.12.38: the canary `policy.spec.ts` fails when the wording changes, so checks cannot go silent unnoticed); optional: `addInitScript` + `exposeBinding` on `securitypolicyviolation` would drop the canary |
| E2EC-6 | config | `vite.config.ts:30` | `test.exclude` replaces Vitest's default list (`dist`, `.git`, `.cache`, tool configs…), and `dist-e2e/` is not listed. | confirmed (minor; build output is hashed bundles, no `*.test.*` today); fix: `[...configDefaults.exclude, 'e2e/**', 'dist-e2e/**']`. Fixed (0.12.58): `[...configDefaults.exclude, 'e2e/**', 'dist-e2e/**']` |
| E2EC-7 | flake | `policy.spec.ts:22` | The canary polls for at least one violation, then requires exactly one; a duplicate console entry arriving after `take()` fails the fixture's teardown. | partial (Chromium logs one error per blocked load; not observed in CI since 0.12.38); fix: assert every taken entry contains the directive (`toContain`-style over the array), cheap. Fixed (0.12.58): every taken entry must name `img-src` |

## Sweep: `scripts/` (2026-11-03)

Batch 48. Source: full review sweep, `/code-review` (high, no verify pass) of `scripts/` (no
diff; the module as it stands). Each row checked against the code (by reading; nothing run).
`/security-review`: nothing (every spawn takes fixed argv without a shell, except constant
`npm ci` and Windows `npm audit --json`; no command string built from `.run/` records, process
command lines, audit JSON or git output; `.env` secrets from `crypto.randomBytes`, an existing
`.env` never touched, values never printed; a forged `.run/` record needs write access to the
checkout and must still match the live executable and marker; advisory data only parsed;
`audit.yml` runs on `pull_request`, not `pull_request_target`).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| SCR-1 | bug | `stack.mjs:33` | `ownedByPath` matches the repository root as a plain substring: `npm run stop` in `G:\Projects\ContribFinder` also kills Django, Celery and Vite of a sibling checkout `G:\Projects\ContribFinder-v2` (its paths contain the root). Breaks "kills this repo's stack only". | confirmed; fix: match the root followed by a path separator (`/` after normalizing `\`), test with a sibling prefix. Fixed (0.12.59): whole-folder root match (root + `/`, normalized) |
| SCR-2 | bug | `stack.mjs:34`, `:36` | Any node process with `vite` in its command line counts as stack Vite, which includes `node_modules/vitest/vitest.mjs` (`npm test`, IDE Vitest workers) and Playwright's `vite preview`; any python with `celery` anywhere (`pytest tests/test_celery_config.py`) counts as the worker. `npm run stop` force-kills them. | confirmed; fix: match `vite/bin/vite.js` (not `vitest`) for node and `-m celery` / the `celery` executable for python; tests for vitest and a pytest path. Fixed (0.12.59): program shapes (`vite/bin/vite.js`, Celery as a program or `-m celery`, `manage.py runserver`) |
| SCR-3 | bug | `stop.mjs:15` | `Where-Object CommandLine` drops processes whose command line is unreadable (a stack started from an elevated console, stopped from a normal one); their live runner records then look stale, are deleted, and nothing is killed, so a later elevated stop cannot find them either. | partial (a non-elevated stop could not kill them anyway; the loss is the deleted records); fix: list every process with its pid and treat a record whose pid is alive with an unreadable command line as "unknown, keep" (and report it). Fixed (0.12.59): every Windows process listed; an unreadable live record is kept, left running and reported (`matchStack` `unknown`) |
| SCR-4 | bug | `child.mjs:115`, `:117` | On POSIX `stop` signals `-child.pid` and `killTree` kills `-pid`, ignoring `options.detached`: with `detached: false` (`e2e-backend.mjs:61`) the child leads no group, both throw ESRCH (swallowed), Django keeps serving :8001 and the runner waits forever on its `exit`. | partial (Playwright stops the web server by SIGKILL to the runner's group, which includes the non-detached Django, so CI is unaffected; a manual SIGTERM on Linux hangs); fix: group signals only when detached, else `child.kill(signal)`. Fixed (0.12.59): a non-detached child is signalled directly |
| SCR-5 | bug | `child.mjs:133` | The `exit` handler calls `process.exit` as soon as the direct child (uv.exe) exits; the pending `killTree` timer is dropped, so a grandchild still running (Django's autoreloader child, a Celery pool python) is orphaned and holds its port until `npm run stop`; the header promises the whole tree is killed. | partial (not reproduced; on Windows an orphan's parent pid is gone, so `taskkill /T` cannot reach it after the fact); fix: while stopping, `killTree(child.pid)` before the child is allowed to exit (e.g. on the first signal on Windows after the grace, and on `exit` run a final `killTree` by the recorded group/job), or record grandchildren by marker so `stop` finds them. Accepted (0.12.59): not reproduced; `npm run stop` stops this repository's Django, Celery and Vite by path |
| SCR-6 | bug | `redis.mjs:86`, `:104` | When Redis never becomes reachable the catch calls `stop()`, which exits 0: `concurrently`'s `killOthersOn: ['failure']` never fires, backend and Vite keep running, and worker and beat fail 60 s later far below the real cause. | confirmed; fix: `stop(code = 0)` with `stop(1)` from the catch. Fixed (0.12.59): `stop(1)` when Redis never comes up |
| SCR-7 | robustness | `redis.mjs:61` | The keep-alive `ChildProcess` has no `'error'` listener: a spawn failure (first start or a restart: EMFILE, WSL being updated) is an unhandled `'error'` event and crashes the runner with a stack trace, past the restart-budget message; the comment says a failed spawn is handled. | confirmed; fix: `session.on('error', ...)` logging and exiting 1 (or counting against the restart budget). Fixed (0.12.59): keep-alive `'error'` handler, exit 1 with a message |
| SCR-8 | bug | `env.mjs:42` | `URL.hostname` keeps IPv6 brackets: `REDIS_URL=redis://[::1]:6379/1` gives `[::1]`, so `isLocal` is false (no WSL Redis started) and `net.connect` fails `ENOTFOUND`. | confirmed (minor; the default and `.env.example` use `localhost`); fix: strip `[`/`]` from the hostname. Fixed (0.12.59): brackets stripped |
| SCR-9 | bug | `uv.mjs:24` | Python install folders are ordered by lexical `sort().reverse()`: `Python39` comes before `Python313`/`Python312`, so an old pip-`--user` uv is picked over a current one. | confirmed (minor; `UV_BIN` and PATH come first); fix: sort by the numeric version suffix. Fixed (0.12.59): `uv.newestPythonFirst` |
| SCR-10 | duplication | `setup.mjs:14`, `backend.mjs:9`, `manage.mjs:8` | Each recomputes the repository root from `import.meta.url` instead of importing `root` from `env.mjs`. | confirmed; fix: `import { root } from './env.mjs'` and `path.join(root, 'apps', 'backend')` (check `setup.mjs` can import `env.mjs` before `.env` exists). Fixed (0.12.59): `root` from `env.mjs` |

## Sweep: `.github/workflows/` (2026-11-03)

Batch 49. Source: full review sweep, `/code-review` (high, no verify pass) of `ci.yml` and
`audit.yml` (no diff; as they stand), with `apps/frontend/package.json`, `check-version.mjs` and
`csp.config.test.ts` as context. Each row checked against the files (by reading; nothing run).
`/security-review`: nothing (`pull_request` and `push` to `main` only, plus `schedule` and
`workflow_dispatch` for the audit; no `pull_request_target`/`workflow_run`/`issue_comment`;
`permissions: contents: read` everywhere, no `secrets.*`; only `event_name`/`ref`/`sha` and
`hashFiles` in expressions, none in `run:`; PR caches are scoped to the PR ref, so a fork cannot
seed `main`'s; the only artifact, `playwright-report/`, holds at most cookies of throwaway seeded
users). Verdicts on CI-4…CI-6: hardening (read-only token, no secrets, nothing deployed or
published), worth doing in a public repository.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| CI-1 | gap | `ci.yml:51`, `:114`, `:157` | `uv sync --frozen` installs the lock without checking it against `pyproject.toml`, and the bare `uv run …` steps then lock and sync by default: a dependency added without `uv lock` passes CI on a resolution never committed, while Docker (`--frozen`) and the audit (`uv export --frozen`) use the stale lock. `check-version.mjs:32` says `uv sync --frozen` rejects stale locks; it does not. | confirmed; fix: `--locked` on the syncs and `UV_LOCKED: 1` at workflow level (covers `uv run` inside npm scripts); correct the comment. Fixed (0.12.60): `uv sync --locked` in every job, `UV_LOCKED: "1"` at workflow level; comment corrected |
| CI-2 | gap | `ci.yml:83`, `:85` | `npm test` runs before `npm run build`, so `csp.config.test.ts:46` (`it.runIf(existsSync('dist/index.html'))`: built index carries the policy, no inline script) is always skipped in CI. | confirmed (e2e covers the policy indirectly since 0.12.38); fix: Build before Tests (and drop the separate Type check, CI-10). Fixed (0.12.60): Lint, Format, Build, Tests |
| CI-3 | gap | `ci.yml:123` | The drift check `git diff --exit-code -- apps/frontend/src/api` ignores untracked files: a newly generated file there is never flagged. | confirmed (minor; both outputs are tracked today); fix: fail on non-empty `git status --porcelain -- apps/frontend/src/api`. Fixed (0.12.60): `git status --porcelain` drift check |
| CI-4 | supply chain | `apps/frontend/package.json:17` (`gen:api`), `ci.yml:119` | `npx --yes openapi-typescript@7.13.0` resolves the package and its transitive dependencies outside any lockfile on every run; nothing pins their integrity, `audit:deps` never sees them, and a transitive release can change the output (drift failure with no code change). | confirmed (hardening per the security review); fix: pinned `openapi-typescript` devDependency in `apps/frontend` (locked, audited), `gen:api` calls the local binary (needs `npm install --allow-remote=all`, which the owner runs). Fixed (0.12.60): own locked tree `apps/frontend/tools/api-types/` (generator 7.13.0, TypeScript 5.9.3; the app's TypeScript 6 is outside its peer range), `gen:api` runs its binary; CI `npm ci` there, `npm run setup` installs it, `audit:deps` audits it; `api:sync` unchanged output |
| CI-5 | supply chain | `ci.yml:46`…, `audit.yml:27`… | Actions pinned to mutable tags (`checkout@v4`, `setup-uv@v6`, `setup-node@v4`, `cache@v4`, `upload-artifact@v4`) in a public repository. | confirmed (hardening: read-only token, no secrets); fix: full commit SHAs with a version comment (and Dependabot for actions to keep them current). Fixed (0.12.60): SHA pins with version comments in `ci.yml` and `audit.yml`; `.github/dependabot.yml` (GitHub Actions, weekly) |
| CI-6 | supply chain | `ci.yml:46`…, `audit.yml:27` | `actions/checkout` keeps `persist-credentials: true`: the job token stays in `.git/config` for `npm ci` lifecycle scripts and the npx download; no step pushes. | confirmed (hardening: `contents: read`, nothing uploads `.git`); fix: `persist-credentials: false` on every checkout. Fixed (0.12.60): `persist-credentials: false` on every checkout |
| CI-7 | diagnostics | `ci.yml:177` | The Playwright report uploads only `if: failure()`; the e2e job's only limit is `timeout-minutes: 30`, and a timed-out job is cancelled, so a hang (the 0.12.12 mode) loses the report and traces. | confirmed; fix: step-level `timeout-minutes` on "Browser tests" (e.g. 20) and `if: ${{ failure() \|\| cancelled() }}`; also upload `test-results/` (traces). Fixed (0.12.60): step timeout 20 min; report and `test-results/` upload on failure or cancel |
| CI-8 | coverage | `ci.yml:108` | `test:scripts` runs on `ubuntu-latest` only; the runners' main target is Windows (`taskkill`/`killTree`, `%APPDATA%` uv lookup, `npm.cmd` shell in `audit.mjs`, detached `wsl.exe`), so the win32 branches never run in CI. | confirmed; fix: a `windows-latest` job (or matrix leg) for `test:scripts` (pure functions run anywhere; platform branches need injectable `platform`). Fixed (0.12.60): `scripts-windows` job (`windows-latest`, `npm run test:scripts`); injectable `platform` not added (non-goal) |
| CI-9 | speed | `ci.yml:167` | The Playwright browser cache key hashes the whole frontend lockfile; the browsers depend only on the exactly pinned `@playwright/test` (`1.64.0`), so every release bump re-downloads Chromium. | confirmed (minor, ~1–2 min per lockfile change); fix: key on the installed Playwright version (`npx playwright --version` into a step output). Fixed (0.12.60): cache key from `npx playwright --version` |
| CI-10 | speed | `ci.yml:81`, `:85` | `tsc -b` runs twice: "Type check" (`npm run typecheck`) and "Build" (`tsc -b && vite build`). | confirmed (minor); fix: drop the Type check step (Build fails on type errors), with CI-2's reorder. Fixed (0.12.60): Type check step removed |

## Fix-diff review of 0.12.51–0.12.54 (2026-11-03)

Batch 50. Source: `/simplify` (4 agents, one combined diff of the uncommitted 0.12.51–0.12.54
code; applied directly: one `strip_html_comments`, single-query `opened_issue` check, `dismiss`
reads once, `_sync_catalog`, shared test builders; four skips noted in the CLAUDE.md 0.12.54
entry), then `/code-review` (high) of the same diff. FD2-1 and FD2-2 reproduced by the reviewer;
each row checked against the code. FD2-5 and FD2-6 decided by the owner (2026-11-03). All fixed
before commit, folded into 0.12.53/0.12.54.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| FD2-1 | regression | `services/profiling/manifests.py` (`_GRADLE_COMMENT`) | The Gradle block-comment rule fired on `/*` inside string literals (globs such as `'META-INF/*.kotlin_module'`, `'**/*.java'`) and, with `re.S`, deleted everything to the next `*/`: every dependency lost, a real Android repository could turn `not_code`. | confirmed (reproduced); fixed: one regex matches string literals or comments and puts strings back (`_strip_gradle_comments`), so globs and URLs survive; the whitespace rule for `//` is gone |
| FD2-2 | regression | `services/profiling/readme.py` (`tech_sections`) | The fence tracker compared only a 3-character marker: a nested ```` ```bash ```` inside a ```` ````markdown ```` block closed it early (PROF-2 back) and the real close then opened a phantom fence hiding later headings. | confirmed (reproduced); fixed: CommonMark rule, a fence closes only on a run of the same character at least as long with no info string |
| FD2-3 | gap | `services/profiling/text.py` (`strip_html_comments`) | An unterminated `<!--` stayed text (GitHub hides the rest), and `issues/classify._HTML_COMMENT` stripped to the end: two strippers disagreed on the same input. | confirmed; fixed: one stripper, `<!--.*?(?:-->|\Z)`, used by READMEs, `parse_pom` and issue difficulty (`classify` imports it); spec "README skill evidence" edited directly |
| FD2-4 | bug | `services/feedback.py` (`dismiss`) | `Repository.objects.get` after a concurrent delete-data raised `DoesNotExist`: HTTP 500. | confirmed; fixed: `dismiss` raises `Recommendation.DoesNotExist` when the repository is gone, the view answers 404 |
| FD2-5 | consistency | `services/profiling/experience.py` | Experience signals still counted contributions to forks after PROF-8. | owner: forks never count, also for experience. Fixed: `ProfileInput.__post_init__` drops fork contributions (and strips README comments, FD2-9), `contributed_work` removed; spec "Experience level" (developer-profile) edited directly |
| FD2-6 | behavior | `services/feedback.py` (`record`) | An issue closed or dropped between page load and click returned 400, while a recommendation gone meanwhile returns 204. | owner: 204, no event, for both races. Fixed: on a miss, 400 (`IssueNotRelevant`) only for an issue of another repository; spec "Recording feedback" edited directly |
| FD2-7 | duplication | `services/issues/classify.py` | A second comment regex with a different unterminated rule. | fixed with FD2-3 |
| FD2-8 | duplication | `features/feedback/api.ts` | The unsave toggle repeated `useUnsaveRepository`'s request; `DELETE /recommendations/{id}/save` unused by the SPA. | fixed: one `unsaveRepository` request function; the endpoint is kept for API clients (comment in `SaveView.delete`, OpenAPI `1.0.0`) |
| FD2-9 | altitude | `services/profiling/interests.py`, `readme.py` | Comment stripping per README consumer. | fixed: once in `ProfileInput` (every consumer reads the stripped README) |

## `/simplify` of 0.12.58–0.12.60 (2026-11-06)

Batch 53. Source: `/simplify` (reuse, simplification, efficiency, altitude; one combined diff of
the uncommitted 0.12.58–0.12.60 code: `scripts/`, workflows, e2e config). Applied before commit,
folded into 0.12.58–0.12.60. The fix-diff `/code-review` followed (batch 54).

| ID | Type | Where | Finding | Status |
|---|---|---|---|---|
| SIM3-1 | duplication | `scripts/redis.mjs` | The keep-alive's `'error'` and `'exit'` handlers repeated record removal and the stopping check; the give-up path exited directly while the error path called `stop(1)`. | fixed: local `ended()`; both failures go through `stop(1)` |
| SIM3-2 | simplification | `scripts/redis.mjs` | `stop` was hoisted with `keepAlive?.kill()` and a comment saying the `'error'` handler could run first; spawn events are asynchronous, so it cannot. | fixed: `stop` declared before `startKeepAlive()`, plain `keepAlive.kill()`, comment keeps the exit-code reason |
| SIM3-3 | dead code | `scripts/stack.mjs` (`matchStack`) | `proc.cmd !== null` could never be false there (the null case `continue`s above, or `recordMatches` fails on the name). | fixed: guard removed |
| SIM3-4 | simplification | `scripts/child.mjs` (`runChild`) | `stop` nested `posix` and `grouped` branches. | fixed: one `try` with `grouped` / `posix` |
| SIM3-5 | altitude | `scripts/setup.mjs`, `scripts/audit.mjs` | The npm trees were listed by hand in each (and in `ci.yml`); a missed tree goes unaudited or uninstalled in silence. | fixed: `env.NPM_TREES`; `env.test.mjs` checks each has a lockfile and appears in `ci.yml`, and that every `apps/frontend/tools/*` lockfile is listed |
| SIM3-6 | efficiency | `ci.yml` (`scripts-windows`) | `npm ci` and the npm cache on Windows for tests that import only Node built-ins and `./*.mjs`. | fixed: no install |
| SIM3-7 | simplification | `ci.yml` (e2e) | A step ran `npx playwright --version` and parsed it for the cache key. | fixed: key `hashFiles('apps/frontend/node_modules/@playwright/test/package.json')` |
| SIM3-8 | altitude | `csp.config.test.ts` | The built-index test still skipped in silence if CI ever stopped building first (CI-2 relied on step order). | fixed: `runIf(existsSync(built) \|\| CI)`, so a missing build fails in CI. Also: `child.test.mjs` waits for the child's first line instead of 500 ms; redundant `taken.length` assertion in `policy.spec.ts` and a stale comment in `playwright.config.ts` removed |
| SIM3-9 | altitude | `scripts/child.mjs` (`killTree`) | On POSIX `killTree(-pid)` does nothing for a pid that leads no group (also `stop.mjs`'s path-matched processes). | skipped at first; fixed as CR3-5 (owner: fix all) |
| SIM3-10 | altitude | `apps/frontend/package.json` (`gen:api`) | Runs a file inside the generator package (`bin/cli.js`). | skipped: same pattern as `playwright.config.ts`'s Vite; the version is exact, and a moved file fails `api:sync` loudly in CI |
| SIM3-11 | duplication | `ci.yml` | `UV_LOCKED: "1"` and `--locked` state the same policy. | skipped: the flag documents each sync; design D1 keeps both |
| SIM3-12 | efficiency | `scripts/audit.mjs` | The four audits run one after another. | skipped: a few seconds; parallel output and error handling would grow the script |
| SIM3-13 | efficiency | `scripts/setup.mjs` | Three `npm ci` in sequence. | skipped: once per setup; interleaved output |
| SIM3-14 | altitude | `e2e/fixtures.ts` | Guards per flag (`--repeat-each`, `--retries`) instead of creating the user at test start. | skipped: E2EC-2, E2EC-5 accepted by the owner |

## Fix-diff review of 0.12.58–0.12.60 (2026-11-06)

Batch 54. Source: `/code-review` (high) of the uncommitted 0.12.58–0.12.60 code (scripts, e2e
tooling, workflows) after batch 53; the pinned action SHAs were checked against `git ls-remote`.
Each row checked by reading; owner: fix all. Folded into 0.12.60. `npm run e2e` 9/9; the POSIX
paths first run in Linux CI (no Node in WSL here).

| ID | Type | Where | Finding | Status |
|---|---|---|---|---|
| CR3-1 | flake | `e2e/fixtures.ts`, `policy.spec.ts` | E2EC-7 checked only entries seen before `take()`; a duplicate violation logged after it still failed the fixture's teardown. | fixed: `take()` remembers the taken texts; later entries with one of them are ignored |
| CR3-2 | docs | `fixtures.ts`, `playwright.config.ts`, README | A second run inside one `--ui` session was said to fail at sign-in with a message; it has the same attempt numbers and cannot be detected. | fixed: docs say it is undetectable and fails on stale data; restart to re-seed (E2EC-1 covers `--repeat-each` and CLI `--retries` only) |
| CR3-3 | bug | `scripts/child.mjs` (`runChild`) | A non-grouped POSIX child's force kill hit only `uv`; Django (its child) kept :8001. | fixed: force kill is always `killTree(child.pid)` (whole tree, CR3-5) |
| CR3-4 | bug | `scripts/stack.mjs` | The Celery shape matched the bare word as any argument (`python -m pytest <repo>/tests -k celery`), so `npm run stop` killed it. | fixed: `isCelery(line)`: the command, or what python runs (path or `-m celery`, past interpreter flags); tests for `-k celery`, a venv `python3 .../bin/celery`, `python -u -m celery` |
| CR3-5 | bug | `scripts/child.mjs` (`killTree`) | On POSIX only `-pid` was signalled: path-matched processes that lead no group survived `npm run stop` (SIM3-9). | fixed: `ps -eo pid=,ppid=` listed first, then each group and every descendant SIGKILLed; `withDescendants` (pure, tested) |
| CR3-6 | test | `scripts/child.test.mjs` | The SCR-4 test's 5 s timeout equalled `GRACE_MS`, so the force kill could make it pass. | fixed: 2 s timeout |
| CR3-7 | test | `scripts/env.test.mjs` | The root lockfile "in CI" check matched `apps/frontend/package-lock.json` as a substring; only `tools/*` was scanned for unlisted trees. | fixed: lockfiles from `git ls-files --cached --others --exclude-standard` must equal `NPM_TREES`; each must be a whole `ci.yml` entry |
| CR3-8 | test | `csp.config.test.ts` | `CI=false` (or any value) also forced the built-index test (ENOENT without `dist/`). | fixed: `process.env.CI === 'true'` |

## Public-release check (2026-11-12)

Batch 55. Source: a check of the full git history and the tree before making the repository
public (after v0.12.60; `ideas.md` §5 "Making the repository public"). Searched every commit's
patch for token and key patterns, the paths ever committed, commit authors, local paths in
tracked files, `.env.example`, the evaluation datasets, workflow permissions and triggers.
Clean: only fake test tokens (`gho_testtoken0000…`), `.env`, `judging/`, `reports/` and `.run/`
never committed, every commit on the no-reply address, persona-only datasets, `permissions:` set
in both workflows, no `pull_request_target`, no `secrets.*`.

| ID | Type | Where | Finding | Status |
|---|---|---|---|---|
| PUB-1 | docs | `CHANGELOG.md` (link references) | The compare links stopped at 0.10.0 and pointed at `v*` tags that were never created (the repository has no tags), so every version link returned 404. | fixed (0.12.61): link references removed, headings stay `## [x.y.z] - date` as plain text; noted under `[Unreleased]` "Removed". Tagging release commits and restoring the links stays possible |
| PUB-2 | privacy | git history (`55f0fe9` … `8074cbe`) | Both SRS files, untracked in 0.12.39, are still reachable in history. | accepted: the owner's own documents, not confidential (`ideas.md` §5); removing them would need a history rewrite and a force-push |
| PUB-3 | settings | GitHub repository settings | Private vulnerability reporting (which `SECURITY.md` relies on), secret scanning with push protection, Dependabot alerts, `main` protection (required checks, no force-push) and approval for fork workflows are not yet turned on. | open (owner only; the list is in `ideas.md` §5) |

## Sweep: `services/repositories/` (2026-11-12)

Batch 56, the first module of the low group. Source: full review sweep, `/code-review` (high, no
verify pass) of `apps/backend/services/repositories/` (no diff; the module as it stands). Each row
checked against the code (by reading; nothing run); the review's `backlog.py` line numbers were
wrong and are corrected here. `/security-review`: nothing (ORM only, no `raw`/`extra`/cursor;
`release_name` builds the name with `Concat`/`F`/`Value`; manifests through regexes and `tomllib`,
no XML parser, YAML, pickle or `eval`; manifest fetches limited to root entries with fixed names,
paths `quote()`d, host and scheme from `GITHUB_API_BASE_URL` with origin checks on redirects and
links; stored GitHub text rendered as React text, links only from GitHub-generated `html_url`; the
one log line holds name, code and exception class; shared rows hold public data only). RS-1 is a
correctness gap, not a security one: the data involved is public.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| RS-1 | bug | `analysis.py:169`, `:205` | A refresh without metadata (issues-only at 6 h, README-only, …) fetches by the stored name and never checks the GitHub ID; `hold(fetched_name=)` only sees a rename in our own database. Repository A (`foo/bar`, id 1) renamed on GitHub, a new `foo/bar` (id 2) not stored: the new repository's issues, README or snapshot are stored and recommended under A. | partial (bounded: A's metadata goes stale within `REPO_STALE_AFTER["metadata"]` (12 h), then `_metadata` finds A by ID, and storing id 2 releases the name; meanwhile wrong issues and README are shown and matched); fix: when metadata is not fetched, check the identity first with `get_repository(name)` (ETag-cached, a 304 is cheap) and, on another ID or a 404, fetch metadata by ID as in `_metadata` before the other parts. Fixed (0.12.62): identity check by name (conditional) before a refresh without metadata; another ID or a 404 fetches metadata by ID first |
| RS-2 | bug | `analysis.py:347`, `:383`, `:384` | GitHub text goes into PostgreSQL text columns unsanitized: a NUL (README read as text, `\u0000` in an issue's JSON) or a lone surrogate (`\ud800` in JSON) makes the write raise (psycopg `DataError` / `UnicodeEncodeError`), which is not in `REPOSITORY_ERRORS`: `run` releases and re-raises. No NUL handling exists anywhere in `services/`. | confirmed, worse than reported: in discovery `_analyze` re-raises any worker error, so the analysis step, and the whole discovery job, fails for every developer whose pool holds that repository, on every retry; background refreshes fail the same way forever and the row is never FAILED. Fix: one text cleaner (drop `\x00`, replace lone surrogates: `encode("utf-8", "replace")`-style) applied to README content, issue title and body (and labels) before storing; consider the same for the profile README in `services/github/sync.py` (outside this module, same column type); test with NUL and `\ud800`. Fixed (0.12.62): the GitHub client's response wrapper makes every string storable (raw files through `content`, JSON bodies walked), so README, issues, labels, descriptions and the profile README are all covered |
| RS-3 | bug | `backlog.py:107` | `queue_released` sends through `transaction.on_commit(send)` without `robust=True` and never calls `unmark_queued` for a refused send (`process_repository_backlog` and `queue_revocation` both handle broker refusals). | confirmed: with Redis down, `delay` raises after the caller's commit, so a discovery search, profile sync or analysis that saved its data fails or retries anyway (in `run`'s `NameChanged` path it escapes the handler), and the unsent pks keep `refresh_queued_at` for the `lost_before` window. Fix: `on_commit(send, robust=True)`, `send` tries every pk and `unmark_queued` the refused ones (as the backlog task). Fixed (0.12.62): `on_commit(send, robust=True)`, every pk tried, refused ones logged and unmarked |
| RS-4 | bug | `lifecycle.py:257` | `recheck_eligibility` leaves `previous_lifecycle` of a STALE row unchanged when eligibility flips, so (per the review) a released refresh restores RECOMMENDABLE with `is_eligible` False. | false-positive: `claim` overwrites `previous_lifecycle` with the current state (`lifecycle.py:86`), so a STALE row's refresh restores STALE; nothing reads a STALE row's `previous_lifecycle` (set by `mark_stale`, overwritten by the claim). Scoring also requires `is_eligible` |
| RS-5 | bug | `lifecycle.py:260` | `recheck_eligibility` stamps `lifecycle_changed_at = now`, the discovery job's start time (`DiscoveryService.self.now`), while `claim`, `complete` and `upsert_repository` use the wall clock. Another developer's generation that started between that job's start and its pool step never sees the eligibility change (`freshness.due_profiles`: `changed > last_generation`). | confirmed (the analysis' `*_synced_at = now` (job time) is covered: `complete` stamps `lifecycle_changed_at` with the wall clock, which `pool_changed` reads); fix: `timezone.now()` for the transition stamp in `recheck_eligibility`, test with an old `now`. No ranking change. Fixed (0.12.62): transition stamped with the wall clock; `now` still judges the rules |
| RS-6 | bug | `lifecycle.py:121` | `release_name` matches holders with a case-sensitive `full_name=`; GitHub names are case-insensitive and `Repository.full_name` is `unique=True` (case-sensitive). `Foo/Bar` (id 1) deleted, `foo/bar` (id 2) created: nothing is released, two rows share the name case-insensitively, the old row stays eligible with a URL to the new repository and is not queued for a by-ID refresh. | confirmed (rare; its metadata refresh then finds id 2 by name, falls back to ID and 404s → FAILED, so it ends within 12 h); fix: `full_name__iexact` (the contributions code already matches `full_name__iexact`); a case-insensitive unique constraint would need a migration that repairs existing duplicates, left out. Fixed (0.12.62): `full_name__iexact`, served by the new `repository_full_name_upper_idx` (`repositories.0010`, EXPLAIN shows an index scan) |
| RS-7 | bug | `analysis.py:178` | `run` returns `Outcome.FAILED` after `lifecycle.fail()`, which updates nothing when the claim was lost; the outcome then disagrees with the stored state. | confirmed (minor: discovery acts only on `ANALYZED`; the outcome feeds counts and task logs); fix: `fail` returns the update count (or raises `ClaimLost`, as `renew`), `run` returns SKIPPED on 0. Fixed (0.12.62): `fail` returns whether it changed the row; SKIPPED otherwise |
| RS-8 | consistency | `analysis.py:133`, `:297`–`:303` | `normalize_label` is a weaker copy of `services.issues.labels.normalize`/`category`: no scope prefixes (`type: good first issue`), edge symbols or aliases (`first-timers-only`, `good-first-bug`). Issue analysis treats these as `good_first_issue`/`help_wanted`, but `has_good_first_issue_label`/`has_help_wanted_label` stay False, so the openness signal gives no points. | confirmed; fix: `labels.category(name) == labels.GOOD_FIRST_ISSUE` / `HELP_WANTED`, remove `normalize_label` (and its `__all__` entry). Ranking-visible through data (openness), like `labeled-issue-fetch`: needs an OpenSpec change; benchmarks store the flags, so baselines cannot move (check with `evaluate_ranking`). Fixed (0.12.62): flags from `labels.category`; `normalize_label` removed. Baselines unchanged (`test_baseline_metrics_unchanged`) |
| RS-9 | efficiency | `backlog.py:43`–`:57` | `mark_stale` loads every column of every pooled RECOMMENDABLE/INDEXED repository on each beat run to compute `stale_parts`, then sends one UPDATE per stale row. | confirmed (minor at today's pool sizes); fix: `.only("pk", "lifecycle", "full_name", *PART_FIELDS.values())` (plus whatever `stale_parts` reads), and one UPDATE per (lifecycle, parts) group, as `recheck_eligibility`. Fixed (0.12.62): `.only(...)` and one UPDATE per (lifecycle, parts) group |
| RS-10 | locking | `lifecycle.py:127`–`:140` | `release_name` locks holders through unordered bulk UPDATEs, against the module docstring ("rows locked in bulk are locked in GitHub ID order"), often while the caller holds another repository's lock (`hold` in the store transaction, a search upsert). | partial: holders are almost always one row; the deadlock needs two analyses whose repositories swapped names, which ordering the holders cannot prevent (each caller already holds its own row), and PostgreSQL then aborts one (`OperationalError`, retried). Fix: lock holders with `select_for_update().order_by("github_id")` before the updates, for the documented order. Fixed (0.12.62): holders locked with `select_for_update().order_by("github_id")` first |

## Sweep: `services/issues/` (2026-11-12)

Batch 57. Source: full review sweep, `/code-review` (high, no verify pass) of
`apps/backend/services/issues/` (no diff; the module as it stands). Each row checked against the
code by reading; ISV-1…ISV-4 also reproduced by calling the functions. `/security-review`: nothing
(pure functions, no I/O; keyword patterns built from fixed tuples through `re.escape`; stored
evidence rendered as React text, no `dangerouslySetInnerHTML` in `apps/frontend/src`;
`difficultyBasis` checks the evidence shape and reads `SIGNAL_TEXT` through `Object.hasOwn`;
technologies are catalog slugs only; links come from GitHub's `html_url`). Every fix changes issue
analysis (`ISSUE_TAXONOMY_VERSION`); benchmarks store issue analysis, so baselines cannot move.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| ISV-1 | bug | `labels.py:113` | `_SCOPE` knows only `:`, `/` and `]`: hyphen-scoped labels (`type-bug`, `E-easy`, `C-bug`, `difficulty-easy`) normalize to `type bug`, `e easy`, … and match no alias and no difficulty form (reproduced: no category, no label vote). The spec treats hyphens and spaces alike, and `type bug` is how the scope rule sees it. | confirmed; fix: when no punctuation scope is found, a first word from a fixed list of scope words (`type`, `kind`, `area`, `category`, `c`, `e`, `t`, `difficulty`, `level`, `complexity`, …) is a scope too; spec scenario. Fixed (0.12.63): `labels.parts` (punctuated scope, else a first word in `SCOPE_WORDS`) |
| ISV-2 | bug | `classify.py:105` | `_label_votes` reads `DIFFICULTY_LABELS` from the scope-stripped form whatever the scope: `Priority: Medium` votes intermediate (reproduced), `severity: trivial` beginner. `good first issue` + `Priority: Medium`, a common pair, contradicts → `unknown`. | confirmed; fix: a scoped label votes difficulty only under a difficulty scope (`difficulty`, `level`, `complexity`, `effort`, `e`, `exp`, `experience`, `skill`); unscoped forms as now. Fixed (0.12.63): only unscoped labels and `DIFFICULTY_SCOPES` vote |
| ISV-3 | bug | `technologies.py:29` | Labels go through `ALL_MATCHER` (ambiguous aliases allowed) anywhere in the label: `C-bug` → C, `spring cleaning` → Spring, `status: good to go` → Go (reproduced). False technology matches, an inflated technology count and a wrong technology on the issue page. | partial fix planned: ambiguous words only in the label's value after its scope (ISV-1's scope words included), so `C-bug`/`C-feature-request` no longer mean C; `spring cleaning` and `good to go` stay (the catalog marks `react` ambiguous too, so whole-value-only would drop React from `React Hooks`). Fixed in part (0.12.63): ambiguous words matched in the label value only, unambiguous phrases in the full label |
| ISV-4 | bug | `technologies.py:31` | The body is not passed through `strip_html_comments` before technology detection; `plain_text`'s tag rule cuts a comment at its first `>`: `<!-- e.g. Python >= 3.10, Node.js 20 -->` leaves Node.js (reproduced). | confirmed; fix: `plain_text(strip_html_comments(body))`. Fixed (0.12.63): body technologies after `strip_html_comments` |
| ISV-5 | config | `core/checks.py:372`, `classify.py:91` | `several_technologies == many_technologies` passes core.E040, but the `>= many` branch runs first, so the technology count never votes intermediate; with `min_votes` 2 no issue can be intermediate, and core.W004 (from the fixed `LEVEL_VOTERS`) does not warn. | confirmed; fix: core.E040 requires `several_technologies < many_technologies`. Fixed (0.12.63): core.E040 `several_technologies < many_technologies` |
| ISV-6 | bug | `classify.py:131` | The description length counts fenced code blocks (pasted logs, stack traces): a one-line report with a 4,500-character traceback votes advanced. | partial (unfenced logs still count; fences are the common case in templates); fix: length without fenced code blocks (CommonMark fences, the rule `readme.tech_sections` uses); spec text and scenario. Fixed (0.12.63): length after `text.strip_code_fences` (the one CommonMark fence rule, shared with `readme.tech_sections`) |
| ISV-7 | bug | `services/repositories/analysis.py:387`, `core/checks.py` | The body is capped at `ISSUE_BODY_MAX_CHARS` before HTML comments are removed: a body that starts with 10,000+ characters of template comments is stored as comments only (length 0, real text lost). No check keeps `long_body` below the cap (a cap of 3000 silences the long-description vote). | partial (default cap 10,000 vs `long_body` 4000); fix: the stored body drops HTML comments before the cap (issue-ingestion spec), core.E040 requires `long_body < ISSUE_BODY_MAX_CHARS`. Fixed (0.12.63): stored body drops HTML comments before the cap; core.E040 `long_body < ISSUE_BODY_MAX_CHARS` |
| ISV-8 | consistency | `analysis.py:47` | An `unknown` contribution type stores `{}` evidence without the taxonomy version (difficulty evidence always has it), so unknown-typed rows cannot be dated to a taxonomy. | confirmed (minor; the SPA reads `by` and handles its absence); fix: `{"taxonomy": ...}` for unknown too. Fixed (0.12.63): `{"taxonomy": ...}` for unknown too |
| ISV-9 | bug | `classify.py:55` | Keywords never match next to a hyphen: `docs-only`, `CI-failure`, `e2e-tests` give no keyword. | accepted: the exclusion also keeps `test-driven`, `error-prone`, `ci-friendly`, `docs-site` out; hyphenated compounds are ambiguous both ways, labels usually decide, and changing it is a guess with no evidence either way |
| ISV-10 | duplication | `technologies.py:29`, `classify.py:105`, `labels.py` | `technologies` splits labels by its own `replace("-", " ").replace("_", " ")` (a second copy of `labels._SEPARATORS`); each label is normalized and scope-stripped three or four times per issue (`normalize_labels`, `_label_votes`, `category`, the repository flags). | confirmed; fix: one cached `labels.parts(name)` (full form, scope, value) used by categories, difficulty votes and technologies. Fixed (0.12.63): `labels.parts` cached; `technologies` uses it |

## `/simplify` and fix-diff review of 0.12.62–0.12.63 (2026-11-13)

Batch 58. Source: one `/simplify` (4 agents) and one fix-diff `/code-review` (high) over the
combined uncommitted 0.12.62–0.12.63 code; all fixed before commit. `/simplify`: one HTML-comment
strip for issue bodies (`IssueInput`), `labels.DIFFICULTY_SCOPES` inside `SCOPE_WORDS`, `forms`
folded into `category`, GitHub JSON walked only when it holds an unstorable escape,
`backlog.send_refreshes` (one send-and-unmark loop), shared test fixtures (`take_name`, `broker`).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| CR4-1 | bug | `classify.py:_label_votes` | A multi-word scope (`Skill Level: Easy`, `Difficulty Level: Hard`) is not in `DIFFICULTY_SCOPES`, so the label casts no vote (it did before 0.12.63). | fixed: `labels.scoped_by(scope, DIFFICULTY_SCOPES)` (every scope word a difficulty word; `Priority Level: Medium` still none); the unpunctuated scope is the run of leading scope words (`skill-level-easy`) |
| CR4-2 | bug | `labels.py:_EDGES` | `normalize` strips a leading `.`: `.NET` → `net`, no dotnet. | fixed: a leading `.` is kept |
| CR4-3 | bug | `labels.py:parts` | Single-letter scope words make `C-API`, `c extension` scope `c` (C lost) and `e-commerce` scope `e`. | fixed: a lone one-letter scope only before a known category or difficulty |
| CR4-4 | bug | `technologies.py:detect` | A punctuated scope that is an ambiguous technology is dropped: `Rust: async` → none, `go/rust` → only rust. | fixed: ambiguous matching on the value only under a scope of scope words, else the full label |
| CR4-5 | bug | `profiling/text.py:FENCE` | A line starting with inline triple backticks (```` ```npm test``` fails ````) opens a fence that never closes; the rest of the body is dropped. | fixed: a backtick run followed by another backtick on the line is not a fence (CommonMark) |
| CR4-6 | efficiency, bug | `repositories/analysis.py:_fetch` | The identity check discards its answer: another ID asks the name twice; a rename (redirect, same ID) passes and the stored name stays old. | fixed: `_identity` returns the answer; a rename stores it as metadata, another ID or 404 goes straight to the ID lookup |
| CR4-7 | bug | `github/oauth.py:fetch_identity` | `/user` is parsed without `storable`: a NUL in the name fails sign-in (`display_name`). | fixed: `services/github/text.py` (`storable`, `storable_json`, `parse_json`), shared by the client and `oauth` (the client imports `oauth`) |
| CR4-8 | bug | `lifecycle.release_name`, `storage` | Inside an ID-ordered batch, each upsert locks its name's holders before its own row: the transaction does not lock in GitHub ID order (deadlock with a concurrent batch). | fixed: `storage.lock_for_upsert(repos)` locks the rows and their holders (case-insensitive) in GitHub ID order; sync and discovery call it once per batch, `upsert_repository` for its one row |
| CR4-9 | efficiency | `repositories/analysis.py:_store_issues` | HTML comments stripped twice per issue (store and `IssueInput`). | fixed: `IssueInput(max_chars=)` strips then caps; the stored body is `IssueInput.body` |
| CR4-10 | robustness | `classify.difficulty`, `technologies.detect` | Both rely on `IssueInput` having removed comments; a direct caller would count template text. | fixed: docstrings state it; a test fails when anything under `services/` other than `issues/analysis.py` calls them |

## Sweep: `services/discovery/` (2026-11-13)

Batch 59. Source: full review sweep, `/code-review` (high, no verify pass) of
`apps/backend/services/discovery/` (no diff; the module as it stands). Each row checked against the
code by reading. `/security-review`: nothing (skill and interest terms come from the catalog only;
own topics are GitHub-restricted and searched with the developer's own token; the query sits in `q`
via `urlencode`, token in the header only; candidates scoped by developer; job metadata never
serialized; the yield report holds aggregates only). OpenSpec change
`services-discovery-review-fixes`.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| DSC-1 | bug | `queries.py:plan_queries` | Every skill and interest topic counts as covered, also when the budget cuts its query: a recurring own-repository topic (e.g. `fastapi`, skill #6 of 3 slots) is never searched. | fixed: covered only by skill/interest queries planned in pass 1 of two `allocate` passes (design D1) |
| DSC-2 | bug | `service.py:_record` | "Same run" compares `last_seen_at == self.now`; a retry resets `now`, so the second band's worse rank overwrites the better one and the pool order depends on band order. | fixed: `_search_started()` (`search_started_at`, else the attempt clock) is the boundary (D3) |
| DSC-3 | bug | `queries.py:_qualifiers` | Empty login yields `-user:`; every query refused. | false positive: `run()` needs a GitHub account (`for_user`), sign-in requires a non-empty username, deletion cancels the run first |
| DSC-4 | bug | `queries.py:allocate` | Leftover slots go to the first strategies, not the largest remainders: shares 1/1/1/9 at budget 5 give topic 3, not 4. Default shares divide exactly. | fixed: leftover by largest remainder, ties in `STRATEGIES` order, positive shares only (D2) |
| DSC-5 | bug | `yield_report.py:load` | Window on nullable `started_at`: never-started cancelled runs count all-time but not in a window, and runs that never searched are labelled "without per-query yield". | fixed: window on `Coalesce(started_at, created_at)`; `runs_without_search` (no plan, or search step pending/skipped) apart from `runs_without_yield` (D4) |
| DSC-6 | efficiency | `yield_report.py:load` | Fetches every job's whole metadata to read `query_yield`. | fixed: `values_list` of `metadata__query_yield`, `metadata__plan__0`, `steps__search` (D4) |
| DSC-7 | efficiency | `filters.py:prefilter` | Stored dependencies read before checking an earlier rejection (only for unannotated callers; the one stored caller annotates). | fixed: dependencies read only after every other rule passed (D5) |
| DSC-8 | structure | `service.py:_step_search` | The search step repeats the not-code rule (`suspected_list` twice) outside `filters.py`. | fixed: `filters.stored_result_not_code(result, repo, cfg)` (D5) |

## Sweep: `services/matching/` (2026-11-13)

Batch 60. Source: full review sweep, `/code-review` (high, no verify pass) of
`apps/backend/services/matching/` (no diff; the module as it stands). Each row checked against the
code by reading. `/security-review`: nothing (profile and candidate loads scoped to the developer;
issues are shared public data limited to the candidates; ORM only; config and evidence read as
JSON data; reason text rendered as React text, no raw HTML in the SPA; links from GitHub's
`html_url`; no logging). OpenSpec change `services-matching-review-fixes`.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| MAT-1 | bug | `features.py:_snapshot` | Push age and label as captured, never aged: a stale repository whose refresh keeps failing reads "pushed today" weeks later and scores as recently active. | fixed: `activity.current` at load: days from `Repository.pushed_at` (else snapshot days aged since capture), label under current thresholds; score, reason and filter share it (design D1) |
| MAT-2 | bug | `features.py:load_developer` | `repo_count` counts contribution evidence: "appears in 3 of your repositories" for 1 owned + 2 contributed. | fixed: `features.OWN_REPOSITORY_SOURCES` (language, topic, dependency) filter the count; collector test guards it (D3) |
| MAT-3 | bug | `signals.py:skill_match` | Evidence keeps technologies with weight 0 (topic source weight 0, a share rounding to 0): the reason names technologies that added nothing. | fixed: evidence keeps `weight * confidence > 0`; value unchanged (D4) |
| MAT-4 | bug | `activity.py:activity_label` | One unknown count is treated as 0: pushed 5 days ago, commits unknown, 0 merged PRs → `low_activity`; both unknown → moderate. | fixed: `meets(count, key)` per count; unknown never 0 (D2) |
| MAT-5 | bug | `activity.py` / `features.py` | `thresholds_version` is never compared: after a threshold change one list mixes labels until each refresh. | fixed: by MAT-1 (label under current thresholds at load) |
| MAT-6 | bug | `features.py:best_rank` | Best rank compares ranks across star bands. | rejected: ranks restart per band on purpose (`discovery-size-mix`), the tie-break shares the pool order |
| MAT-7 | structure | `signals.py:OPENNESS_FLAGS` | Openness flags, activity labels and tech sources duplicate `ranking/config.py` key lists, unchecked; a one-sided addition raises `KeyError` in generation. | fixed: guard test `test_matching_key_lists_match_configuration_validation` (D5) |
| MAT-8 | efficiency | `signals.py:skill_match`, `language_match` | Confidence looked up twice per technology. | fixed: walrus, one lookup (D4) |

## `/simplify` of 0.12.64–0.12.65 (2026-11-14)

Batch 61. Source: `/simplify` with four agents (reuse, simplification, efficiency, altitude) over
one combined diff of the uncommitted 0.12.64–0.12.65 code (`services/discovery`,
`services/matching`, `services/ranking/service.py`, tests). Findings deduplicated across agents.

| ID | Type | Where | Finding | Status |
|---|---|---|---|---|
| SIM4-1 | reuse | `discovery/service.py:_prune_discoveries` | Parsed `search_started_at` itself although `_search_started` claimed to be the shared boundary. | fixed: `_search_started()` returns None without the key; pruning uses it, `_record` falls back to `self.now` |
| SIM4-2 | simplification | `discovery/queries.py:plan_queries` | Three closures (`topic_queries`, `quotas_for`, `topics_of`, one reading `budget` assigned after it) and `(key, core, topic)` triples with `""` for languages. | fixed: `searched_topic` (key → topic), `available` once, both passes inline |
| SIM4-3 | reuse | `matching/activity.py` | "Whole days since, never negative" written three times. | fixed: `_days_since(then, now)` (`current`, `compute_activity`) |
| SIM4-4 | simplification | `activity.activity_label`, `features._snapshot` | Closure `meets` per call; seven positional arguments to `current`. | fixed: module-level `_meets(count, threshold)`; `_snapshot` calls `current` by keyword |
| SIM4-5 | simplification | `matching/signals.py:skill_match` | `matched` rebuilt after the sum to drop weight-0 technologies. | fixed: one filter `t.weight > 0 and c > 0` (same value and evidence) |
| SIM4-6 | reuse, altitude | tests | `stored()` duplicated `make_candidate_repo`; `ACTIVITY_DATA` copied the default thresholds unchecked. | fixed: `stored()` wraps `make_candidate_repo`; `test_activity_data_gives_its_label` |
| SIM4-7 | altitude | `discovery/yield_report.py:Run.searched` | Inferred from the plan and step states; `search_started_at` suggested instead. | skipped as proposed (the key alone counts empty-plan runs as searched); superseded by CR5-4 (searched = a query finished) |
| SIM4-8 | efficiency, simplification | `service._record`, `yield_report.load` | ISO parse per `_record` call; `Run(*row)` positional; `Coalesce` window bypasses a `started_at` index. | skipped; the parse later fixed by CR5-7 (`_seen_since`) |

## Fix-diff review of 0.12.64–0.12.65 (2026-11-14)

Batch 62. Source: `/code-review` (high, no verify pass) of the uncommitted 0.12.64–0.12.65 code
after batch 61. Each row checked against the code; owner: fix all.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| CR5-1 | bug | `discovery/queries.py:plan_queries` | Pass 2 can plan fewer skill/interest queries than pass 1 (a longer topic list wraps less back), so a topic covered in pass 1 whose query pass 2 cuts is searched by nothing (shares 2/4/2/2, budget 10: skill 9, then 8). Breaks the spec of DSC-1. | fixed: allocate until the covered set is the planned one; it only shrinks, so it ends (design D1's oscillation worry does not hold) |
| CR5-2 | bug | `recommendations/serializers.py`, `feedback/serializers.py`, `repositories/api.py` | Only generation recomputed activity: the detail facts said "Last push: today" beside "last push 40 days ago"; the saved list and the discovery pool showed the stored label. | fixed: `features.current_activity` (saved list; detail facts at `generated_at`), `repositories.queries.with_current_activity` (pool, SQL), parity test; spec `repository-activity` edited directly |
| CR5-3 | bug | `evaluation/export.py:export_developer` | `load_candidates` called without the export's `now`. | fixed: passes `now` |
| CR5-4 | bug | `discovery/yield_report.py:Run.searched` | A run cancelled in its first request counted as "without yield" (the legacy bucket). | fixed: searched = a query finished (`query_yield`, `queries_done`, `queries_skipped`); no step-state inference (also answers SIM4-7); spec edited directly |
| CR5-5 | bug | `matching/activity.py:current` | Ageing floors twice: up to a day short. | fixed in part: snapshots store no push time, so the fallback (no repository push time) rounds the time since capture up and never claims a younger push; the usual path reads `Repository.pushed_at` |
| CR5-6 | robustness | `discovery/queries.py` | Topic queries skip the `seen` dedup. | fixed as a test: filtering by `seen` would hide the topic of a cut skill query again (CR5-1); a planned query covers its topic, so no core repeats (`test_topic_of_a_query_cut_in_a_later_pass_is_still_searched` asserts unique cores) |
| CR5-7 | efficiency | `discovery/service.py:_record` | ISO parse per record. | fixed: `_seen_since`, cached per service (one attempt) |
| CR5-8 | simplification | `discovery/filters.py:stored_result_not_code` | Repeated `stored_not_code`. | fixed: `suspected_list`, then `stored_not_code(repo, cfg, topics=)` |


## Sweep: `services/ranking/` (2026-11-14)

Batch 63. Source: full review sweep, `/code-review` (high, no verify pass) of
`apps/backend/services/ranking/` (no diff; config, pipeline, score, explain, freshness,
activation as they stand, plus `matching/signals.py`). Each row checked against the code by
reading. `/security-review`: nothing (ORM only, field names from constants; no eval, pickle or
YAML; reason text rendered as React text; generation and API scoped to the user's profile; no
logging; activation only from the management command). Note: the activation audit metadata also
carries `reason`, which the 0.12.13 notes in `CLAUDE_HISTORY.md` omit (doc only). OpenSpec change
`ranking-review-fixes`; fixed in 0.12.66.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| RNK-1 | bug | `freshness.py:failed_recently` | Any failed generation in the last 6 h excludes the developer, even after a later completed one: a re-analysis after a fail-then-succeed waits up to 6 h. | fixed: `failed_recently` reads the latest finished generation (COMPLETED or FAILED by `completed_at`) |
| RNK-2 | bug | `freshness.py:outdated_config` | Config change seen only through stored recommendations: a developer with candidates and 0 recommendations is never regenerated on activation. | fixed: due when the last completed generation's `metadata.config_version` differs from the active version |
| RNK-3 | bug (latent) | `matching/signals.py:framework_match` | Ignores `Tech.weight`: a topic-only framework counts and passes the relevance gate when topics weigh 0. Stored configs weigh topics 0.6. | fixed: `framework_match` skips `Tech.weight` 0 |
| RNK-4 | bug (latent) | `matching/signals.py:contribution_openness` | Evidence lists 0-point flags; the reason claims them (spec: only evidence the signal used). Stored configs give every flag points. | fixed: evidence lists flags with points above 0; value unchanged |
| RNK-5 | bug | `activation.py:activate` | `update(is_active=True)` count unchecked: candidate deleted between judging and the switch leaves no active config and audits success. Needs a concurrent delete. | fixed: candidate re-checked under the row locks; `ActivationError`, nothing changed or audited |
| RNK-6 | bug | `freshness.py:start_due_generations` | A broker error from one `on_commit` send (no outer transaction in the beat task) stops the sweep for every later profile. | fixed: `start_due_generations` logs and continues; the PENDING job is re-sent by recovery |
| RNK-7 | bug | `explain.py:reasons` | Kept on the unrounded contribution, stored rounded: a reason with weight 0.0. | fixed: a reason needs `round(part, 4) > 0` |
| RNK-8 | simplification | `score.py:weighted_score` | Unused outside tests; its and `reasons`' `params=None` default drops relevance scaling. | fixed: `weighted_score` removed; `reasons(signals, parts)` has no params default |
| RNK-9 | efficiency | `pipeline.py:rank_pool` | Issues loaded and matched when both issue weights are 0. No stored config hits it. | fixed: issues loaded only when issue fit or difficulty fit weighs above 0. **Reverted** in 0.12.69 (CR6-4): matched issues are shown, not only scored, so a 0 weight must not hide them |
| RNK-10 | efficiency | `explain.py:reasons` | Recomputes `contributions` already summed by `score_candidate`. | fixed: `Scored.parts` carries the contributions; reasons reuse them |

## Sweep: `services/evaluation/` (2026-11-14)

Batch 64. Source: full review sweep, `/code-review` (high, no verify pass) of
`apps/backend/services/evaluation/` (no diff; dataset, metrics, runner, bootstrap, baseline,
export, sheet, build, feedback report as they stand, plus the evaluation commands). Each row
checked against the code and spec by reading. `/security-review`: nothing at the bar. Inputs are
parsed with `json.loads` only (no pickle, YAML, eval or subprocess), paths come from operator
flags, the export holds no username, email or token, the feedback report outputs aggregates only,
and import reads grades 0–2 for pool repositories only. Its one candidate, formula injection in
the judging CSV, was rated 3/10 by the false-positive check (only the owner opens the sheet, it
holds public names only, and spreadsheets prompt before fetching external data); it is fixed as
hardening under EVL-6. OpenSpec change `services-evaluation-review-fixes`.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| EVL-1 | bug | `bootstrap.py:Interval.marked` | Percentile bootstrap marks 4-of-4 holdout wins (sign test p = 0.125) and any non-zero 1-developer difference. As specified, but the 95% claim is not supported. | fixed: marked only with at least 6 developers (`MIN_MARKED_DEVELOPERS`); fewer get a too-few note |
| EVL-2 | bug | `feedback_report.py:build` | The adjusted share renormalizes over the buckets that have a share, so configurations are adjusted over different mixes. | fixed: `coverage` beside the adjusted share (config line, JSON) |
| EVL-3 | bug | `feedback_report.py:build` | Every event counts: repeated opens add positives, and an undone save or dismissal still counts (only `viewed` is deduplicated at write time). | fixed: one outcome per user, repository and version (latest decisive event not undone); counts stay raw |
| EVL-4 | rule | `baseline.py:write` | Bare `write_text`, not `core.reports.write_json`: non-atomic, and an `OSError` is a traceback. | fixed: `baseline.write` through `core.reports.write_json`; same bytes |
| EVL-5 | bug | `baseline.py:write` / `default_datasets` | Keyed by dataset name, looked up as `evaluation/<name>.json`; `--dataset ../../judging/x.json --write-baseline` records an entry the test silently skips. | fixed: `--write-baseline` refuses a dataset that is not `evaluation/<name>.json`; `write` refuses a name without its file |
| EVL-6 | hardening | `sheet.py:write_sheet` | Descriptions from GitHub written unescaped to a CSV opened in spreadsheets (formula cells). | fixed: text cells starting with `= + - @`, tab or CR get a leading `'` (the repository column is a GitHub full name and stays as-is for import) |
| EVL-7 | bug (latent) | `feedback_report.py:_reasons`, label rows | Stored reasons and labels outside the current choices vanish; reasons stop adding up. Choices are validated at write time today. | fixed: other stored reasons after the current ones, other labels after the current ones; calibration uses the current labels only |
| EVL-8 | efficiency | `runner.py:uncertainty` | Draws rebuilt per candidate and dataset. | accepted: drawn once per comparison already; ≤ 6 developers × 10,000 is negligible |
| EVL-9 | bug (latent) | `dataset.py:_issue` | Naive `updated_at` accepted; issue order then depends on the machine's time zone. All 72 committed values carry `+00:00`. | fixed: `updated_at` needs a UTC offset; committed datasets load unchanged |
| EVL-10 | robustness | `build.py:build`, `sheet.py:write_sheet` | Wrong shapes raise `AttributeError`/`KeyError` tracebacks; `resolved` repeats a repository. | fixed: `BuildError` / `SheetError` for wrong shapes; `resolved` lists each repository once |

## Sweep: `frontend/src/features/recommendations/` (2026-11-14)

Batch 65. Source: full review sweep, `/code-review` (high, no verify pass) of
`apps/frontend/src/features/recommendations/` (no diff; list, cards, detail, filters, messages as
they stand). Each row checked against the code, the backend filters and the specs.
`/security-review`: nothing. Text is rendered by React (no raw HTML), the only external link is
GitHub's `html_url` through `ExternalLink`, detail ids go through `RouteId`, filters are sent as
query parameters under a fixed list of keys, list, detail, feedback, save and dismiss are scoped
to the user, and CSRF is sent on every request that changes data. OpenSpec change
`recommendations-view-review-fixes`.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| REC-1 | bug | `RecommendationList.tsx` filter selects | A URL value outside the options (`?language=ruby`, `?size=unknown`, `?match=foo`) shows as "Any" and can't be cleared; there is no Clear control although the alert says "Clear them". | fixed: a URL value outside the options shown as its own option; Clear filters in the form and beside the invalid-filter alert |
| REC-2 | bug | `RecommendationList.tsx` recovery, `feedback/api.ts:useDismiss` | Recovery runs only on pages after the first, and a dismissal never refetches the list: page 1 emptied by dismissals says "No suitable projects yet" while more exist. | fixed: the list is invalidated once the last dismissal in flight settles |
| REC-3 | bug | `RecommendationList.tsx` empty branch | The empty-state message shows while the dismissal is still pending (wrong if it fails). | fixed: an emptied page shows Loading while a dismissal, placeholder or refetch is pending (recovery waits for it too) |
| REC-4 | bug | `RecommendationList.tsx` undo state | History state is cleared only when the notice closes; Back or a reload offers Undo again with a fresh 10 s. | fixed: the dismissal is taken from navigation state on mount and the state cleared at once |
| REC-5 | bug | `api.ts:useRecommendations` placeholder | The previous page's results show under the new page label with no loading cue; Next stays enabled from the old `next`, so a double click skips a page. | fixed: placeholder results `aria-busy` and dimmed, Previous/Next disabled |
| REC-6 | bug | `RecommendationDetailPage.tsx` Back link, after-dismiss navigation | Both go to a bare `/app`, dropping the list's filters and page. | fixed: card links pass the list's search string; Back and after-dismiss use `/app${from}` (`navigation.listPath`) |
| REC-7 | a11y | `RecommendationDetailPage.tsx:LanguageBar` | Shares only as `aria-hidden` bar widths: no amounts for screen readers or sighted users. | fixed: share as text (`shareText`: whole percent, under 1%) |
| REC-8 | types | `messages.ts` `ACTIVITY_TEXT`, `SIZE_TEXT` | `Record<string, string>`: a new backend value compiles and renders blank or "undefined". | fixed: `ActivityLabel`, `RepositorySize` from `src/api/types.ts` |
| REC-9 | structure | `messages.ts:SIZE_OPTIONS` | Second hand-written size wording; omits `unknown`, which the backend accepts (feeds REC-1). | fixed: `SIZE_OPTIONS` from `SIZE_TEXT`, `unknown` included |
| REC-10 | simplification | `messages.ts:difficultyText` | Repeats `NOT_ENOUGH_EVIDENCE` instead of `DIFFICULTY_TEXT.unknown`. | fixed: `DIFFICULTY_TEXT.unknown` |

## Sweep: `frontend/src/features/feedback/` (2026-11-14)

Batch 66. Source: full review sweep, `/code-review` (high, no verify pass) of
`apps/frontend/src/features/feedback/` (no diff; `api.ts`, `RecommendationActions.tsx`,
`SavedPage.tsx`, `messages.ts` as they stand). Each row checked against the code; the review's
line numbers were off, so rows name functions. `/security-review`: nothing. Save, unsave,
dismiss, restore, feedback and both lists are scoped to the user (foreign ids get 404 or delete
nothing); CSRF is enforced and sent; the dismiss body takes only a reason from a fixed list;
feedback takes client actions only; ids are integer routes; text is rendered by React; the paging
cursor is URL-encoded and `next` is never followed. OpenSpec change `feedback-ui-review-fixes`.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| FBK-1 | bug | `api.ts:rollback` | A failed save, unsave or dismiss writes back every cached list page from its start: save A (slow), dismiss B (succeeds), A fails → B is listed again until the data versions refetch. | fixed: per-item rollback (D1): saved flag back for the id only; a dismissal re-inserted at its index (clamped) on pages that lack it |
| FBK-2 | bug | `RecommendationList` → `DismissUndo` | No key: `useRestore` state carries over to the next dismissed project ("Undo didn't work." on B; B's Undo disabled while A's restore runs). | fixed: `key={dismissed.repositoryId}` (D2) |
| FBK-3 | bug | `DismissButton.run` + detail page `onDismissed` | `mutateAsync` resolves after the user left the detail page and `navigate('/app')` pulls them back. | fixed: mounted guard on the detail page (D3) |
| FBK-4 | bug | `DismissUndo` timer | Closes at 10 s while a restore is pending; a later failure is never shown. | fixed: deadline state; no close while restoring; a failure extends 10 s (D2) |
| FBK-5 | ux | cards, `SavedPage` entries, `ShowMore` | Failed save, dismiss, remove, restore and "Show more" are silent; the control just re-enables. | fixed: inline errors (D4, `FAILED_TEXT`); dismiss reads the latest dismissal's status from the mutation cache, since the rolled-back card is a new component; unsave says "Couldn't remove." |
| FBK-6 | bug | `api.ts:useDismiss` | Lists never invalidated after a dismissal. | duplicate of REC-2, fixed in 0.12.68 (`recommendations-view-review-fixes`) |
| FBK-7 | bug | `RecommendationList` undo state | Undo notice comes back on Back. | duplicate of REC-4, fixed in 0.12.68 (`recommendations-view-review-fixes`) |
| FBK-8 | rule | `SavedPage.tsx` | Hand-written pending/error gate twice instead of `Loaded` (CLAUDE.md frontend rule). | fixed: `Loaded` for both lists (D5) |
| FBK-9 | structure | `api.ts` `useRestore`, `useUnsaveRepository` | `['profile', 'recommendations']` typed out instead of the recommendations root key. | fixed: `recommendationsRootKey` (D5) |
| FBK-10 | efficiency | `api.ts:snapshot` | Two independent `cancelQueries` awaited one after the other. | fixed: `Promise.all` (D5) |

## Sweep: `frontend/src/features/profile/` (2026-11-14)

Batch 67. Source: full review sweep, `/code-review` (high, no verify pass) of
`apps/frontend/src/features/profile/` (no diff; as it stands). Each row checked against the code
and the backend analysis. `/security-review`: nothing (three read-only endpoints without ids,
filtered by the user; explicit serializer fields, no token, email or account data; text rendered
by React; links are GitHub's `html_url` through `ExternalLink`). OpenSpec change
`profile-ui-review-fixes`.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| PRF-1 | bug | `SkillGroups.tsx`, `InterestList.tsx` keys | Keyed by row id; every analysis deletes and recreates the rows, so expanded skills and interests collapse after Refresh. | fixed: keys by slug (D1); test refetches with new ids, skill and interest stay open |
| PRF-2 | bug (latent) | `evidence.ts:CATEGORY_ORDER` | Unchecked list; a category missing from it hides those skills (empty section, no message). All 7 categories listed today. | fixed (latent): `CATEGORY_ORDER` from `CATEGORY_LABELS` (D2); guard test |
| PRF-3 | a11y | `SkillGroups.tsx`, `LanguageChart.tsx` | Two lists named "Languages". | fixed: `CATEGORY_LIST_NAMES` ("Language skills"), chart "Languages by code" (D6) |
| PRF-4 | bug (latent) | `evidence.ts:evidenceLabel` | Language evidence without a repository gives a blank label. App code never deletes repository rows (only an admin delete). | fixed (latent): "repository languages", else "evidence recorded" (D4) |
| PRF-5 | a11y | `SkillGroups.tsx:SkillBar` | `aria-controls` points at a list that is not mounted while collapsed. | fixed: `<details>/<summary>` (D3) |
| PRF-6 | bug | `languages.ts:languageRows` | A single 9th language folds into "Other" instead of its name. Unsorted input assumed sorted (the backend sorts, so latent). | fixed: sorted by bytes; "Other" only for 2+ leftovers (D5) |
| PRF-7 | structure | `InterestList.tsx` | Copied evidence row and source labels; drifted: interest rows omit `observed_at`. | fixed: shared `EvidenceItem`, both source labels in `evidence.ts`; interests show the date (D4) |
| PRF-8 | simplification | `SkillGroups.tsx:SkillBar` | Hand-built disclosure beside native `<details>`. | fixed with PRF-5 (D3) |
| PRF-9 | ux | `SkillGroups.tsx` skill name | Truncated to 8rem with no way to read the full name. | fixed: `title` on the name (D3) |
| PRF-10 | structure | `app/dataVersions.ts:AREA_KEYS.profile` | Profile keys typed out instead of imported. | fixed: profile keys imported (D6) |

## Sweep: `frontend/src/features/sync/ + discovery/` (2026-11-14)

Batch 68. Source: full review sweep, `/code-review` (high, no verify pass) of
`apps/frontend/src/features/sync/` and `features/discovery/` plus `routes/OnboardingPage.tsx` (no
diff; as they stand). Each row checked against the code and `services/jobs.py`.
`/security-review`: nothing (start and status act on the signed-in user, no client ids; CSRF
enforced; job responses omit metadata and error detail, codes map to fixed text; fixed sign-in
URL and post-login redirects; the repositories `next` link keeps only its query). OpenSpec change
`pipeline-progress-review-fixes` (includes one backend fix).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| PIPE-1 | bug | `services/jobs.py:run_tracked_job` ← `sync/api.ts` | A job commits COMPLETED before its `on_completed` hook creates the next job: the discovery status refetched on the sync's completion can return the previous finished run, so polling never starts and the new stages run unobserved. | fixed: `_finish_and_follow_up` ends the job and runs the hook (savepoint) in one transaction; tasks sent on commit, a refused send logged (D1) |
| PIPE-2 | bug | same, `discovery/api.ts` | Same gap between discovery and generation, and for the generation rerun. | fixed with PIPE-1 (D1) |
| PIPE-3 | bug | `sync/pipeline.ts:usePipelineStage` | Passive observers: discovery and generation are fetched only while `DiscoveryCard`/`RecommendationList` are mounted (`developer.data`). | fixed in part: `usePipelineStage(fetchStages)`, true once the profile settled without data (deviation from D2: not while it loads, since the cards then mount and refetch on mount a second time) |
| PIPE-4 | bug | `routes/OnboardingPage.tsx` | A start rejected `github_not_connected` shows only the message; sign-in is offered only for a failed job, so Start sync fails forever. | fixed: `needsSignIn(start.error.code)` (D5) |
| PIPE-5 | bug | `discovery/messages.ts:describeDiscovery` | A stalled discovery reads "Finding projects…" while the header says work stopped. | fixed: stalled before active, stalled notice (D3) |
| PIPE-6 | bug | `discovery/messages.ts:timeAgo` | Computed per render; an idle status never re-renders ("this minute" an hour later); server time ahead → "in 2 minutes". | fixed: `formatRelative` (future clamped); card ticks each minute (D4) |
| PIPE-7 | bug | `sync/SyncSteps.tsx` | A stalled job's running step spins "In progress" beside the stalled notice. | fixed: stalled running step shows "Stopped", no spin (D3) |
| PIPE-8 | robustness | `sync/SyncSteps.tsx:ICONS` | Unknown step state → undefined component → page crash. Types rule it out; a cached older SPA can meet a newer backend. | fixed: unknown state reads as pending (D3) |
| PIPE-9 | rule | `discovery/messages.ts:timeAgo` | Date formatting outside `src/lib/format`, hard-coded English. | fixed with PIPE-6: `lib/format` (D4) |
| PIPE-10 | structure | `discovery/messages.ts:FAILURES` | Second GitHub failure table, drifted (no `github_not_connected`). | fixed: `GITHUB_FAILURES` (reason, sign-in), each page adds its next step (D5) |

## Sweep: `frontend/src/components/ + src/lib/` (2026-11-14)

Batch 69. Source: full review sweep, `/code-review` (high, no verify pass) of
`apps/frontend/src/components/` and `src/lib/` (no diff; as they stand, with their callers). Each
row checked against the code. `/security-review`: nothing (`ExternalLink` sets `noopener
noreferrer` and every href is GitHub's `html_url`; CSP blocks inline script; the hash only feeds
`getElementById`, scroll and focus; no unsafe sinks; `cn` merges no objects). OpenSpec change
`shared-components-review-fixes`.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| CMP-1 | bug | `lib/format.ts`, `routes` | An invalid time throws `RangeError` in render, and no route has an `errorElement`: any render error shows the router's default error screen. Times are ISO from DRF (format crash latent); the missing error screen is real. | partial: fixed, formatters return "Unknown"; root `errorElement` `RouteError` (D1) |
| CMP-2 | bug (latent) | `ExternalLink.tsx` | `onClick={onOpen}` passes the event to a `() => void` callback; a caller with an optional parameter would receive it. All callers use arrows. | confirmed (latent): fixed, `onClick={() => onOpen?.()}` (D4) |
| CMP-3 | ux | `lib/useScrollToHash.ts` | Per-component ref: Back to a hash URL scrolls and focuses again. | confirmed: fixed, module-level handled keys (D2; tests clear them with `forgetScrolledEntries`, since every memory router starts at key "default") |
| CMP-4 | bug (latent) | `lib/useScrollToHash.ts` | A target missing when `ready` turns true is never retried. The one caller renders it synchronously. | accepted: no caller needs it |
| CMP-5 | ux | `components/Loaded.tsx` | After a failed first load, a running refetch still shows "Please refresh the page". | confirmed: fixed, loading while `isFetching` (D3) |
| CMP-6 | rule | `SavedPage.tsx` | Hand-written gate instead of `Loaded`. | duplicate of FBK-8 |
| CMP-7 | structure | both detail pages | Same pending/404/failed gate copied; order differs from `Loaded`. | confirmed: fixed, `DetailLoaded` in `components/Loaded.tsx` (D3) |
| CMP-8 | a11y | `components/DeadEnd.tsx` | No heading; focus lost to `<body>` when a page turns into a dead end; no retry for a failed load. | confirmed: fixed, focused `h1`, optional Try again (D3) |
| CMP-9 | layout | `components/Fact.tsx` | `<dd>` cannot shrink: a long unbroken value widens the page. | confirmed: fixed, `min-w-0 break-words` (D4) |
| CMP-10 | structure | 11 "Loading…" paragraphs | Copied with differing classes. | confirmed: fixed, `components/Loading.tsx` (D3) |

## Sweep: root config (2026-11-14)

Batch 70, the last module of the full review sweep. Source: `/code-review` (high, no verify pass)
of `docker-compose.yml`, `.env.example`, `package.json` (no diff; as they stand, with the
Dockerfiles, Vite config, settings and runners). Each row checked against the files.
`/security-review`: nothing at its bar. Docker's DEBUG dev server on all interfaces has no
concrete path to data (API needs a session and never returns tracebacks, no usable admin account,
debug pages mask secrets), so it is hardening (ROOT-1). Vite `host: true` in `npm start` is
accepted (LAN phone testing). Placeholder secrets are replaced by `npm run setup`, and production
defaults are safe. OpenSpec change `root-config-review-fixes`.

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| ROOT-1 | hardening | `docker-compose.yml` backend `ports` | `8000:8000` on all interfaces with `DEBUG=True`: the dev server is reachable from the LAN (Postgres and Redis are loopback). | confirmed (hardening): fixed, `127.0.0.1:8000` and `127.0.0.1:5173` (D1) |
| ROOT-2 | hardening | same, `NUM_PROXIES=1` | A direct client sets `X-Forwarded-For` (throttle and audit IP). | confirmed: fixed by ROOT-1 |
| ROOT-3 | bug | `docker-compose.yml` redis `ports` | Host port 6379 collides with the WSL Redis `npm start` uses (either compose fails or `npm start` silently uses the container). | confirmed: fixed, not published (D1) |
| ROOT-4 | bug | `docker-compose.yml` `/app/node_modules` | Anonymous volume keeps old dependencies after `up --build`. | confirmed: fixed, `--renew-anon-volumes` in README and compose (D4) |
| ROOT-5 | bug | `vite.config.ts` | No polling: Windows bind mounts give no file events, so no HMR in Docker. | confirmed: fixed, `VITE_WATCH_POLLING` (D4) |
| ROOT-6 | bug | `.env.example` / settings | `DJANGO_DEBUG` ignored: development forces True, production False. | confirmed: fixed, development honors it, default true (D2) |
| ROOT-7 | docs | `.env.example` | 17 settings read by `base.py`/`production.py` missing (SECURE_SSL_REDIRECT, throttles, sync limits, ...). | confirmed: fixed, template plus `tests/test_env_example.py` (D3); the test found 2 more (`GITHUB_OAUTH_REDIRECT_URI`, `EXPERIENCE_THRESHOLDS`), 19 added |
| ROOT-8 | bug | `docker-compose.yml` `DJANGO_SETTINGS_MODULE` | Interpolated from the shell before `.env`; an exported value overrides it. | confirmed: fixed, from `.env` only (D2) |
| ROOT-9 | structure | `docker-compose.yml` | Postgres credentials written three times. | confirmed: fixed, `x-postgres-env` anchor, healthcheck from the container env (D5) |
| ROOT-10 | tooling | `package.json` | `format:scripts` checks only; no `engines` for the Node the runners need. | confirmed: fixed, `format:scripts:write`, `engines.node >=22` (D5) |

## Fix-diff review of 0.12.66–0.12.68 (2026-11-14)

Batch 71. Source: `/code-review` (high, no verify pass) of the staged 0.12.66–0.12.68 code. Three
cleanups it found were already fixed in the unstaged edits (`useLocation` per card, `Stacks`
holding whole events, two queries for the active config). Each row checked against the code;
owner: fix all. Fixed in 0.12.69 without an OpenSpec change (the fixes follow the existing specs;
CR6-4 reverts RNK-9, whose design D6 stays in its archived change).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| CR6-1 | bug | `evaluation/feedback_report.py:_settle` | Stacks keyed by version, and events without one skipped: `restore` records `undismissed` with no version, and an unsave after a regeneration carries a later one, so undone dismissals and saves still counted as outcomes. | fixed: stacks per (user, repository), `Decision.version`; outcome = latest decision per version; 3 tests |
| CR6-2 | bug | `frontend/src/features/feedback/api.ts:useDismiss` | `isMutating(...) === 1` in `onSettled`: a mutation stays pending until its `onSettled` ends, so two overlapping dismissals each saw 2 and neither refetched the list. | fixed: unanswered dismiss requests counted around `mutationFn` (per query client); the list is refetched when none is left. No test (the race needs controlled settle timing) |
| CR6-3 | ux | `RecommendationList.tsx` | `settling` included `list.isFetching`: an empty list showed "Loading…" on every background refetch, and next to a running generation. | fixed: `settling = dismissing \|\| stale`; the page-back recovery also waits for `isFetching`; no "Loading…" while generating; test (fails on the old code) |
| CR6-4 | bug | `ranking/pipeline.py:rank_pool` | RNK-9 skipped issue matching when both issue weights are 0, so no relevant issues were stored or shown. | fixed: issues matched whenever the config has `issues` params; RNK-9 reverted; test flipped |
| CR6-5 | robustness | `ranking/freshness.py:start_due_generations` | Bare `except Exception` swallowed database errors per developer. | fixed: catches `kombu.exceptions.OperationalError` only; database-error test |
| CR6-6 | structure | `evaluate_ranking`, `baseline.write` | Dataset-location rule written twice. | fixed: `baseline.check_source` (via `dataset_file`) is the one rule; `write` no longer checks; test moved to `check_source` |

## Fix-diff review of 0.12.70–0.12.74 (2026-11-15)

Batch 72. Source: `/code-review` (high, no verify pass) of the uncommitted 0.12.70–0.12.74 code
(75 tracked files plus new sources). Each row checked against the code. Owner: fix all. Fixed in
0.12.75 without an OpenSpec change (the fixes follow the existing specs). Every fix has a test
that fails on the old code, except CR7-5 (the race needs controlled `onMutate` timing).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| CR7-1 | bug | `evaluation/feedback_report.py:load` | `--config V` filtered rows by `config_version`, so restores (no version) and unsaves under a later version never reached `_settle`, and undone decisions still counted for `V` (CR6-1 defeated). | fixed: `load` reads every event; `build(versions=)` settles all of them, then reports only `V` (no unattributed); test |
| CR7-2 | bug | `services/jobs.py:_finish_and_follow_up` | The hook's `on_commit` sends run at the outer commit, outside `_follow_up`'s `except`. A non-broker error, such as an inline eager task raising under `EAGER_PROPAGATES`, escaped `run_tracked_job` after the job was COMPLETED. | fixed: a first `on_commit` marks the commit; any later error is logged ("not queued" for a broker error, "Follow-up … failed" otherwise); errors before the commit still raise; test |
| CR7-3 | bug | same | The hook ran under the finishing job's row lock, and `_expire_stale` then locked other stale jobs, out of the pk order that recovery and cancel use (`_end_jobs`), so they could deadlock. | fixed: with a hook, the user's active jobs are locked in pk order first; test (a second connection finds the earlier job locked) |
| CR7-4 | bug | `routes/OnboardingPage.tsx` | `failure ? failure.needsSignIn : …`: a failed job's code hid a newer rejected start's `github_not_connected`, so no sign-in button. | fixed: either source needs sign-in; test |
| CR7-5 | bug | `feedback/api.ts:useDismiss` | The unanswered count started in `mutationFn`, after `onMutate`'s awaited cancel, so a dismissal still in `onMutate` was not counted and another's `onSettled` refetched the list early. | fixed: counted from the start of `onMutate` (released if it throws) until the request is answered. No test |
| CR7-6 | ux | `feedback/RecommendationActions.tsx:DismissButton` | The error was read from any cached dismiss mutation for the id (kept for `gcTime`), so "Couldn't hide." followed the recommendation to its detail page and later list visits. | fixed: `PageVisit` context (`feedback/visit.ts`, provided in `SignedInLayout`, changes on every route change); dismissals carry their visit; test |
| CR7-7 | bug | `feedback/api.ts:useDismiss.onError` | Rollback re-inserted per page unless that page held the item; a refetch that moved it to another page duplicated it and inflated `count`. | fixed: skipped when any page of the same list (path without `page`) holds it; test |
| CR7-8 | docs | `sync/pipeline.ts:usePipelineStage` | Doc said pass true while the profile loads; the only caller passes false then. | fixed: doc matches the caller |
| CR7-9 | bug | `lib/format.ts:formatRelative` | Unit chosen before rounding: 3599 s → "60 minutes ago", 86399 s → "24 hours ago". | fixed: unit chosen after rounding; tests |
| CR7-10 | structure | `profile/evidence.ts` | `CATEGORY_LIST_NAMES` repeated every category of `CATEGORY_LABELS` by hand. | fixed: both derived from one `CATEGORIES` record |

## `/simplify` of 0.12.76 (2026-11-16)

Batch 73. Source: `/simplify` with four agents (reuse, simplification, efficiency, altitude) over
the uncommitted 0.12.76 code (`services/github/client.py`, `services/data_deletion.py`,
`github/tasks.py`, `accounts`, tests). Reuse found nothing; altitude confirmed `_get` is the only
user-scope cache writer. Findings deduplicated across agents.

| ID | Type | Where | Finding | Status |
|---|---|---|---|---|
| SIM5-1 | efficiency | `client.py:_get` | `_still_current()` ran after a cache write the backoff had skipped or that had just failed: one wasted query per GitHub response during a cache outage. | fixed, then reverted by CR8-1 (the shared backoff state races between threads) |
| SIM5-2 | simplification | `test_etag_cache_generation.py` | Account-deletion test repeated `user_keys` inline with a wider filter. | fixed: `user_keys(user)` (the in-memory `user` keeps its pk) |
| SIM5-3 | simplification | same | Route setup line repeated in six tests. | fixed: `languages()` registers the route |
| SIM5-4 | simplification, altitude | `client.py:for_user` | `_owner` holds the pk `_scope` already implies; a client built directly with a user's scope skips the check. | skipped: no caller builds one (only `for_user`, `for_app`); parsing the scope back into an int is no simpler. Revisit if the constructor changes |
| SIM5-5 | efficiency | `client.py:_still_current` | One primary-key query per user-scope cache write. | skipped: minimal query next to a GitHub round trip; batching or checking first reopens the write/check gap (design D1) |

## Fix-diff review of 0.12.76 (2026-11-16)

Batch 74. Source: `/code-review` (high, no verify pass) of the uncommitted 0.12.76 code after
batch 73. Each row checked against the code. Owner: fix all; CR8-5 and CR8-6 rejected with reasons
(fixing them would undo design D1 or the fix itself).

| ID | Type | Where | Finding → failure | Status |
|---|---|---|---|---|
| CR8-1 | bug | `client.py:_get` (SIM5-1) | The check was skipped while the process-wide `_cache_backoff` was down; in the threaded worker another thread can mark it down between this thread's successful write and the check, so a deleted user's entry stayed. | fixed: SIM5-1 reverted, the check always runs after a set (its test removed) |
| CR8-2 | bug | `data_deletion.py` | Dropping `_purge_later` dropped the only retry of a purge that fails at commit; the generation covers only entries written afterwards, so existing entries stayed for `GITHUB_ETAG_TTL`. | fixed: `purge_user_github_cache` returns success; on failure `_purge` queues `github.purge_user_cache` (backoff-seconds countdown, 3 tries, eager: one); spec scenario "Cache purge fails at deletion"; tests |
| CR8-3 | privacy | `client.py:_still_current` | A `DatabaseError` counted as current, keeping the entry. | fixed: fails closed (entry deleted, one cache miss); test. The aborted-transaction part does not apply: GitHub I/O never runs inside `atomic` (no I/O under a lock) |
| CR8-4 | trap | `data_deletion.py:delete_github_data` | The bump updated the row only; a later full `user.save()` of the passed object would write the old generation back. | fixed: `refresh_from_db(fields=[display_name, github_cache_generation])`; test saves the object after the deletion |
| CR8-5 | efficiency | `client.py:_still_current` | One PostgreSQL query per user-scope cache write; keep the generation in Redis or the key instead. | rejected: SIM5-5; design D1 rejected the key namespace (stale entries stay stored), and a Redis copy is lost with the cache it guards |
| CR8-6 | efficiency | `client.py:for_user` | A client built before the deletion committed writes and deletes every entry for the rest of its run. | rejected: refreshing `_owner` after a mismatch would let the cancelled sync cache again, the bug SVC-16 fixes; the churn ends with the run |
| CR8-7 | docs | `CLAUDE_HISTORY.md`, change `tasks.md` 5.2 | Said `/simplify` and `/code-review` were skipped, contradicting batch 73. | fixed: both name batches 73 and 74 |
| CR8-8 | release | `README.md` Screenshots | `docs/screenshots/` untracked: committing only modified files would break the images. | fixed: staged with the release commit |
