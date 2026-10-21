# Ideas

Gap analysis from 2026-10-20 (v0.12.4). These are not yet planned: each needs an OpenSpec
change before work starts. Ranking-visible items must win on the benchmark, which needs K-1
(`Bug_Backlog.md`) first.

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

## 4. Learning from interaction

- **Online report per config.** `RecommendationFeedback` already snapshots `rank`,
  `config_version` and `match_label`, but nothing reads it. Report save, dismiss and
  open-on-GitHub rates by config version and rank position (correct for position bias).
  Offline and no ranking change.
- **Label calibration.** Check that Strong beats Good beats Partial on real outcomes. The bands
  have never been checked, and they are the user-visible promise.
- **Dismiss reasons.** Optional enum (not my stack, too big, inactive, already know it). This
  turns dismissals into labeled negatives, which helps judging.

## 5. Platform

- **Content-Security-Policy.** No CSP in `config/`; matters because README excerpts are
  rendered.
- **Dependency scanning in CI.** `pip-audit`, `npm audit`, Dependabot or CodeQL.
- **GitHub API budget across users.** Search allows 30 requests/min per token and the
  app-credential backlog is shared. Model what many concurrent onboardings do.
- **Accessibility.** Not covered by any spec or backlog row.
- **Observability.** Stage latencies, failure-rate trends (post-MVP: Sentry/Prometheus).

## Suggested order

| | Cheap | Expensive |
|---|---|---|
| **High value** | online report per config; bootstrap CIs; dismiss reasons | responsiveness signals; user intent / preferences |
| **Lower value** | IDF weighting; per-owner diversity cap; CSP; pip-audit | discovery-recall metric; second judge / κ; GitHub budget load model |

Offline items (online report, CIs) change no ranking and can ship alongside backlog batches
5–11.

---

# Round 2 (2026-10-20): retrieval and freshness

Ranking only reorders what discovery finds. All four strategies (`services/discovery/queries.py`)
are keyword search; qualifiers are only `archived/fork/pushed/stars/-user`. Retrieval changes
need the discovery-recall metric (§3) first, or gains stay invisible.

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

## 9. Profile freshness

- Beat schedule (`config/settings/base.py`) has no user resync: the profile is frozen until the
  user clicks Refresh, while recommendations keep refreshing against it. Option: weekly resync
  for users active in the last N days, within the GitHub budget.

## 10. Notes

- **CSP (§5) is lower priority than stated:** README excerpts are rendered as text (no
  `dangerouslySetInnerHTML` or markdown renderer). Still defense in depth.
- **Playwright:** in the declared stack, no e2e directory yet. Covered by backlog batch 9.

## Suggested order (round 2)

| | Cheap | Expensive |
|---|---|---|
| **High value** | labeled-issue fetch (§7); opportunity qualifiers (§6); setup readiness (§8) | upstream dependencies (§6); similar_repo from saves (§6) |
| **Lower value** | — | starred repos (§6, privacy disclosure); periodic resync (§9, budget) |
