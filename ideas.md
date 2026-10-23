# Ideas

Gap analysis from 2026-10-20 (v0.12.4), with later rounds added 2026-10-21 and 2026-10-22
(v0.12.7–v0.12.10). Nothing here is planned yet: each idea needs an OpenSpec change before work
starts. Ranking-visible items (marked † below) must win on the benchmark, so they wait for K-1
(`Bug_Backlog.md`).

Layout: the priority table first, then the open ideas grouped by theme, then what has shipped.
Section numbers (§1–§16) are stable, because other documents cite them, so they are not in
numeric order.

## Priorities

Open ideas only. † = changes what users are recommended (waits for K-1).

| | Cheap | Expensive |
|---|---|---|
| **High value** | bootstrap CIs (§3, before or with K-1); online report per config (§4); dismiss reasons (§4); labeled-issue fetch† (§7); opportunity qualifiers† (§6); setup readiness (§8); post-analysis pool cleanup (§11); `no_license` measurement (§12) | responsiveness signals† (§2); user intent / preferences† (§1); upstream dependencies† (§6); `similar_repo` from saves† (§6); content-based `not_code`† (§11, needs a judged sample); data versions (§14); new seeds stored inactive (§15) |
| **Lower value** | IDF weighting† (§1); per-owner diversity cap† (§1); CSP (§5); pip-audit (§5); queue released-name refresh (§13); per-band yield (§12); route-level ids (§14); production build in CI (§14) | discovery-recall metric (§3); second judge / κ (§3); GitHub budget load model (§5); starred repos† (§6, privacy disclosure); periodic resync (§9, budget); server page clamping (§14, API change); generic migration round trip (§15, slow test); stored activity (§16, migration) |

Not ranked yet: time decay on skill evidence† (§1), label calibration (§4), pooling bias (§3),
accessibility and observability (§5).

Offline items (online report, CIs) change no ranking and can ship at any time.

---

# Ranking and matching

## 1. Matching techniques

- **Specificity weighting (IDF).** `skill_match` (`services/matching/signals.py`) is coverage ×
  confidence, so a match on Python, pytest or TypeScript counts the same as a match on a rare
  framework. Weight technologies by inverse frequency over the catalog or candidate pool. It
  stays deterministic and configurable (`ScoringConfig.params`).
- **Time decay on skill evidence.** The decay in `services/profiling/confidence.py` is per
  repeat, not per time. `SkillEvidence.observed_at` is stored but unused, so a skill last seen
  years ago weighs the same as last month's.
- **Diversity in the top-k.** Nothing stops ten Django plugins or five repos from one owner
  filling the top 10. Add a per-owner cap or MMR-style re-ranking as a separate stage after
  ranking (invariant §3.4).
- **Use stated preferences / user intent.** `preferred_project_size` and
  `preferred_issue_difficulty` are never read by any service. Users can't say "learn Rust" vs
  "stay in my stack". This doubles as the cold-start answer for users with few public repos.

## 2. Contribution-success signals

Openness is currently CONTRIBUTING plus labels plus templates. Signals that better predict a
merged first contribution:

| Signal | Status | Source |
|---|---|---|
| Maintainer responsiveness (median time to first reply on issues/PRs) | missing | issue/PR timeline |
| Outside-contributor merge rate | missing | PR search excluding members |
| Issue already being worked on (linked open PR) | missing | assignee is filtered in `services/matching/issues.py`; linked PRs are not |
| Issue heat (many comments, unassigned = contested or blocked) | missing | `comments` already on the payload |
| Last maintainer activity on the issue | missing | issue timeline |

Show them as observable facts ("Maintainers usually reply within 3 days"), never "friendly"
(invariant §3.7). Measure the GitHub API cost per repo against the discovery budget first.

## 4. Learning from interaction

- **Online report per config.** `RecommendationFeedback` already snapshots `rank`,
  `config_version` and `match_label`, but nothing reads it. Report save, dismiss and
  open-on-GitHub rates by config version and rank position (correct for position bias).
  Offline and no ranking change.
- **Label calibration.** Check that Strong beats Good beats Partial on real outcomes. The bands
  have never been checked, and they are the user-visible promise.
- **Dismiss reasons.** Optional enum (not my stack, too big, inactive, already know it). This
  turns dismissals into labeled negatives, which helps judging.

# Evaluation

## 3. Evaluation rigor

- **Significance testing.** With 6–7 developers, NDCG +0.02 (v2 vs v1) is noise. Add a paired
  bootstrap or randomization test per developer, plus CIs in the `evaluate_ranking` report.
  Land this before or with K-1, or the next ranking search can "win" on noise.
- **Inter-rater agreement.** Single judge today. A second judge on about 10 rows (Cohen's κ)
  shows whether the grades mean anything.
- **Pooling bias.** Only candidates discovery found get judged; unjudged = irrelevant, so a
  config that surfaces new good repos is penalized.
- **Discovery recall.** Evaluation starts from a fixed pool, so discovery misses are invisible.
  Add a stage metric: of the judged-relevant repos, how many did discovery find?
- **Issue-level evaluation** (K-3, already tracked).

# Discovery and repository data

Ranking only reorders what discovery finds. All four strategies (`services/discovery/queries.py`)
are keyword search; qualifiers are only `archived/fork/pushed/stars/-user`. Retrieval changes
need the discovery-recall metric (§3) first, or gains stay invisible. (Round 2, 2026-10-20.)

## 6. Retrieval sources

- **Upstream dependencies ("contribute to what you use").** Manifests are already parsed; map
  each package to its repo via registry metadata (PyPI `project_urls`, npm `repository`, crates
  `repository`, Go module path). Strongest contribution prior; explanation is honest ("You
  depend on X in 3 repos"). Needs non-GitHub HTTP: a separate module (e.g.
  `services/registries/`) with the same retry, cache and degrade-on-failure rules.
- **Starred repos.** `GET /users/{u}/starred`, public, no scope. Candidates plus a strong
  interest signal. Disclose on the privacy page.
- **`similar_repo`.** In the FR-REPO-002 source enum, never built. Seed from saved and
  contributed repos (topics, dependencies, owner). Feedback changes what is found, not the score.
- **Opportunity qualifiers.** GitHub search supports `good-first-issues:>0` and
  `help-wanted-issues:>0`; unused. One query variant per strategy, or a band-style mix.

## 7. Issue coverage

- `list_open_issues` (`services/github/client.py`) fetches the most recently updated issues,
  capped at `ISSUES_MAX_PAGES`. In big repos, older `good first issue` / `help wanted` issues
  fall past the cap, so `issue_fit` underrates repos with the most entry points. Add one fetch
  with `labels=good first issue` (and `help wanted`) and merge.

## 8. Setup readiness

- No detection of CI workflows, tests, devcontainer or docker-compose in candidate repos.
  `list_root_contents` exists, so about 1 call per repo. Observable label: "Has CI and tests ·
  devcontainer". Local setup pain is a top first-PR drop-off cause.

## 11. Code-or-list detection

Round 3 (2026-10-21), from the `discovery-repository-data` change (v0.12.7) and its first real
discovery run; also §12 and §13.

- **`not_code` by content, not only markers.** Today a suspected list (`awesome-*`, list
  topic) is code when it declares manifest dependencies, and docs repositories without a list
  marker always pass (K-4). Lists often carry lint or site tooling (`awesome-lint`, mkdocs), so
  dependencies are weak evidence. Stored data already allows a better signal: share of
  non-markup bytes in `RepositoryLanguage`, README link density, or source files at the root
  (`list_root_contents` is already fetched for manifests). Needs a judged sample of lists and
  tools first, since it decides what users can be shown at all.
- **Post-analysis pool cleanup.** The pool step runs before analysis (D7), so a suspected list
  found `not_code` by this run's analysis keeps its pool slot until the next run (X-9). A
  second, cheap `not_code` pass after the analysis step would free it now.

## 12. Search budget

- **`no_license` is the biggest rejection.** The first real run rejected 30 results as
  `no_license` against 3 `not_code`, out of 20 requests. GitHub search has no "has any license"
  qualifier, so each rejected result costs a slot of a 30-result page. Measure per strategy;
  if one query type dominates, a narrower query (or a second page for it) recovers budget.
- **Uneven band yield.** Bands are counted (`pool_bands`) but not compared to what each band's
  requests returned. Recording results per band in the job metadata would show whether the
  20..999 band is worth the same budget as 1000+.

## 13. Repository identity

- **Released names are resolved lazily.** A repository that gave up its name stays
  `name_released` (not recommended) until the hourly sweep and backlog resolve it by GitHub ID.
  Queuing that refresh directly when the name is released would close the gap to minutes.

## 16. Data access and repository hygiene

Round 6 (2026-10-22), from the `performance-cleanup` review and `/simplify` pass.

- **Stored activity on `Repository`.** `latest_snapshot()` slices a prefetch, which Postgres
  runs as `ROW_NUMBER()` over every snapshot of the prefetched repositories. The `-id` index
  tie-break shipped (v0.12.11) and the remaining sort was accepted as bounded (Q-10, v0.12.13:
  0.4 ms; `DISTINCT ON` still sorts on PostgreSQL 18). Keeping the activity fields (or a
  pointer to the newest snapshot) on `Repository` would remove the read entirely.

## 17. Review round 7

Round 7 (2026-10-23), from the review and `/simplify` pass of 0.12.13/0.12.14 (`Bug_Backlog.md`
S-6, S-9…S-11).

- **Job status keys outside `['profile']`.** Generation and discovery status keys live under
  `['profile']`, so a finished generation invalidates seven profile keys one by one instead of
  the prefix. A `['jobs', ...]` namespace (as `['sync', 'status']`) makes it one invalidation, and
  a new profile query cannot be missed (S-9).
- **One registry of lazy components.** `src/test/setup.ts` preloads `LanguageChart` by hand; a
  new lazy route brings back P-3's random timeouts. AppShell could export its loaders and the
  tests that render it preload them all (also saves ~1 s in every other test file) (S-10).
- **Seekable keyset index.** `(user, -saved_at, -id)` and `(user, -dismissed_at, -id)` with a
  row-value comparison, if saved or hidden lists grow large (S-11).
- **Activation off the request path.** The admin action runs the benchmark inside the request;
  a tracked job, or the admin pointing to the command, once `benchmark-v2` grows (S-6).

# Freshness and client

## 9. Profile freshness

- Beat schedule (`config/settings/base.py`) has no user resync: the profile is frozen until the
  user clicks Refresh, while recommendations keep refreshing against it. Option: weekly resync
  for users active in the last N days, within the GitHub budget.

## 14. Client freshness and paging

Round 4 (2026-10-21), from the `frontend-correctness` review and cleanup pass.

- **Data versions instead of job watching.** The SPA refreshes derived data when a sync,
  discovery or generation job finishes. Data changed by anything else (`reanalyze_profiles`, a
  backend repository refresh) stays cached up to 5 minutes (Y-6). *(v0.12.12: a finished
  generation refreshes the profile too, and every analysis ends in one; what remains is data
  with no generation after it.)* One small endpoint returning per-area update times (profile,
  recommendations, saved) would let the status poll refresh exactly what changed, whatever
  changed it.
- **Clamp past-the-end pages on the server.** `/recommendations?page=N` past the end returns
  404, and the client has two recovery paths (404 → page 1, emptied page → previous page).
  Returning the last page (with its number) removes both; with the list refetched after a
  dismissal, the optimistic-page guard goes too.
- **Route-level id validation.** Each detail page parses `:id`, passes `0` as a disabled
  sentinel and renders its own dead end. A route wrapper that validates once would hand pages
  a plain number.
- **Browser tests on a production build in CI.** The e2e suite drives the Vite dev server;
  `vite build && vite preview` would test what ships and load faster per page.

# Platform and tooling

## 5. Platform

- **Content-Security-Policy.** No CSP in `config/`; matters because README excerpts are
  rendered.
- **Dependency scanning in CI.** `pip-audit`, `npm audit`, Dependabot or CodeQL.
- **GitHub API budget across users.** Search allows 30 requests/min per token and the
  app-credential backlog is shared. Model what many concurrent onboardings do.
- **Accessibility.** Not covered by any spec or backlog row.
- **Observability.** Stage latencies, failure-rate trends (post-MVP: Sentry/Prometheus).

## 10. Notes

- **CSP (§5) is lower priority than stated:** README excerpts are rendered as text (no
  `dangerouslySetInnerHTML` or markdown renderer). Still defense in depth.

## 15. Dev tooling and operations

Round 5 (2026-10-21), from the `dev-scripts-checks` review and cleanup pass.

- **A generic data-migration round trip.** `tests/test_seed_migrations.py` covers the scoring
  seeds only. One test that migrates every app back to its first migration and forward again
  would catch the next irreversible or non-idempotent `RunPython`.
- **New seeds stored inactive.** Seed migrations still decide which configuration is active
  (Z-1). Now that `activate_scoring_config` exists (v0.12.13: benchmark-gated, `--force
  --reason`, audited), a future seed could always store its version inactive and leave
  activation to the operator.

---

# Shipped

| Idea | § | Shipped in |
|---|---|---|
| Playwright browser tests for the main flows | §10 | v0.12.8 (backlog batch 9) |
| One `taskkill` per stop | §15 | v0.12.10 (Z-9) |
| Lint and format `scripts/` in CI | §15 | v0.12.11 (P-5) |
| Line endings fixed in the repository (`.gitattributes` `* text=auto eol=lf`) | §16 | v0.12.11 (P-2) |
| One metadata write path (`_update_metadata` wrappers removed) | §16 | v0.12.11 (Q-12) |
| Tests import builders from `e2e.builders` | §16 | v0.12.11 (Q-12) |
| Snapshot index with the `-id` tie-break | §16 | v0.12.11 (Q-10 in part; the rest accepted in v0.12.13) |
| Keyset (cursor) pagination for saved and hidden lists | §14 | v0.12.12 (Y-7) |
| Profile refreshed when a generation finishes (part of "data versions") | §14 | v0.12.12 (Y-6 in part) |
| Helper modules fail loudly when run (`refuseRun`) | §15 | v0.12.13 |
| Activation as an explicit operator action (`activate_scoring_config`) | §15 | v0.12.13 (seeds still activate: §15 "New seeds stored inactive") |
