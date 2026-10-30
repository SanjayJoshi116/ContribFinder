# Bug Backlog

Findings from the codebase sweep on 2026-10-19 (v0.12.0, `main` @ 50acbb8) and the reviews of
each fix release since; current through 0.12.39. Order: the full review sweep (top priority),
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
| High | `apps/backend/core/` | health, auth class, JSON errors, log redaction, checks, throttling, CSP | [ ] | [ ] |
| High | `apps/backend/accounts/` | User, AuditEvent, auth views, session, account deletion | [ ] | [ ] |
| High | `apps/backend/github/` | GitHubAccount/Profile, sync task, profile API | [ ] | [ ] |
| High | `apps/backend/e2e/` | seed command; must stay out of production | [ ] | [ ] |
| High | `apps/backend/services/*.py` | crypto, audit, jobs, job_guard, locks, feedback, data_deletion, data_versions | [ ] | [ ] |
| High | `apps/backend/services/github/` | OAuth, GitHubClient, sync, storage | [ ] | [ ] |
| High | `apps/frontend/src/api/` | client.ts, types.ts (skip generated openapi.json, schema.d.ts) | [ ] | [ ] |
| High | `apps/frontend/src/features/auth/` | sign-in, route guard | [ ] | [ ] |
| Medium | `apps/backend/jobs/` | SyncJob, status and versions API, recovery | [ ] | [ ] |
| Medium | `apps/backend/developers/` | profile, skills, interests; profile API | [ ] | [ ] |
| Medium | `apps/backend/repositories/` | repository models, discovery API, tasks, reports | [ ] | [ ] |
| Medium | `apps/backend/issues/` | Issue, RecommendedIssue, issue detail API | [ ] | [ ] |
| Medium | `apps/backend/recommendations/` | ScoringConfig, Recommendation, API, evaluation commands | [ ] | [ ] |
| Medium | `apps/backend/feedback/` | feedback, saved, dismissed; keyset pages | [ ] | [ ] |
| Medium | `apps/backend/services/profiling/` | taxonomy, manifest and README parsing (untrusted input) | [ ] | [ ] |
| Medium | `apps/frontend/src/app/` | query client, 401 handling, job transitions, data versions | [ ] | [ ] |
| Medium | `apps/frontend/src/routes/` | routes, AppShell, landing, privacy, RouteId | [ ] | [ ] |
| Medium | `apps/frontend/src/features/issues/` | issue detail (untrusted issue bodies) | [ ] | [ ] |
| Medium | `apps/frontend/e2e/ + vite.config.ts, csp.config.ts, playwright.config.ts` | Playwright, CSP, proxy | [ ] | [ ] |
| Medium | `scripts/` | npm runners, process trees, WSL Redis, dependency audit | [ ] | [ ] |
| Medium | `.github/workflows/` | ci.yml, audit.yml (token permissions) | [ ] | [ ] |
| Low | `apps/backend/services/repositories/` | analysis, lifecycle, staleness, backlog, setup | [ ] | [ ] |
| Low | `apps/backend/services/issues/` | labels, classification, technologies | [ ] | [ ] |
| Low | `apps/backend/services/discovery/` | queries, filters, ordering, yield report | [ ] | [ ] |
| Low | `apps/backend/services/matching/` | activity, technologies, features, signals | [ ] | [ ] |
| Low | `apps/backend/services/ranking/` | config, pipeline, score, explain, freshness, activation | [ ] | [ ] |
| Low | `apps/backend/services/evaluation/` | benchmark, metrics, bootstrap, feedback report (offline) | [ ] | [ ] |
| Low | `apps/frontend/src/features/recommendations/` | list, cards, detail, filters | [ ] | [ ] |
| Low | `apps/frontend/src/features/feedback/` | save/dismiss, saved and hidden lists | [ ] | [ ] |
| Low | `apps/frontend/src/features/profile/` | profile, skills | [ ] | [ ] |
| Low | `apps/frontend/src/features/sync/ + discovery/` | onboarding progress | [ ] | [ ] |
| Low | `apps/frontend/src/components/ + src/lib/` | DeadEnd, utilities | [ ] | [ ] |
| Low | `docker-compose.yml, .env.example, package.json` | root config | [ ] | [ ] |

## Open items

The full review sweep above: started 2026-10-30; `config/` reviewed (batch 26,
no security findings), 33 modules to go. Batch 26 fixed in 0.12.39 (`config-review-fixes`) (CFG-7, CFG-8 accepted). Open rows: RT-3, RT-4, RT-5 (batch 24, design-level; renamed from R-3…R-5, which clashed with the
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
CFG-7 and CFG-8 accepted) in 0.12.39 (`config-review-fixes`).
Next: the full review sweep; RT-3…RT-5 of batch 24 (open, design-level; see its section); the known gaps K-1…K-5 remain.

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
