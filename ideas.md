# Ideas

Gap analysis from 2026-10-20 (v0.12.4), with later rounds added 2026-10-21 to 2026-10-27
(v0.12.7–v0.12.35) and 2026-11-03 (v0.12.54, v0.12.57). Nothing here is planned yet: each idea needs an
OpenSpec change before work starts. Ranking-visible items (marked †) must win on the selection benchmark and not regress on
a fresh holdout. Since 2026-10-28 they no longer wait for K-1 (judging real developers is
optional; `Bug_Backlog.md`).

Layout: the priority table, then the open ideas by when they can ship, then what has shipped.
"Can ship now" (no ranking change) runs in the priority table's order: discovery and
repository data, freshness and client, platform and tooling, then evaluation. "Ranking-visible"
holds the ranking-visible ideas (including what is left of §11 and §12, whose measurement and
cleanup shipped) and the follow-ups of §4, whose ideas have shipped. Shipped ideas are listed
only in "Shipped"; §7, §8, §10, §13 and §17 shipped whole, so they have no section above. Section numbers
(§1–§18) are stable, because other documents cite them, so they are not in numeric order
(reordered 2026-10-26, after v0.12.26).

## Priorities

Open ideas only, in suggested order within each cell. † = changes what users are recommended
(must win on the benchmark).

| | Cheap | Expensive |
|---|---|---|
| **High value** | significance gate for ranking changes (§3); opportunity qualifiers† (§6) | content-based `not_code`† (§11, needs a judged sample); responsiveness signals† (§2); user intent / preferences† (§1); upstream dependencies† (§6); `similar_repo` from saves† (§6) |
| **Lower value** | IDF weighting† (§1); per-owner diversity cap† (§1) | discovery-recall metric (§3); second judge / κ (§3); server page clamping (§14, API change); generic migration round trip (§15, slow test); stored activity (§16, migration); periodic resync (§9, budget); GitHub budget load model (§5); starred repos† (§6, privacy disclosure) |

Not ranked yet: acting on the discovery yield report† (§12, needs runs), intervals on the
feedback-report shares (§4, needs traffic), dismiss reasons against grades (§4, needs real-developer grades),
label bands† (§4), time decay on skill evidence† (§1), pooling bias (§3), accessibility and
observability (§5), interface revamp (§18, owner request; design direction first).

---

# Can ship now (no ranking change)

## Discovery and repository data

### 16. Data access and repository hygiene

Round 6 (2026-10-22), from the `performance-cleanup` review and `/simplify` pass.

- **Stored activity on `Repository`.** `latest_snapshot()` slices a prefetch, which Postgres
  runs as `ROW_NUMBER()` over every snapshot of the prefetched repositories. The `-id` index
  tie-break shipped (v0.12.11) and the remaining sort was accepted as bounded (Q-10, v0.12.13:
  0.4 ms; `DISTINCT ON` still sorts on PostgreSQL 18). Keeping the activity fields (or a
  pointer to the newest snapshot) on `Repository` would remove the read entirely.

## Freshness and client

### 14. Client freshness and paging

Round 4 (2026-10-21), from the `frontend-correctness` review and cleanup pass.

- **A not-found page** (from batch 45, ROUTE-10, 2026-11-03). Unknown paths render the sign-in
  page (`*` → `LandingPage`), which never says "not found"; signed-in users are sent to the
  dashboard. A small not-found page (with the way to sign-in or the dashboard) belongs with the
  interface revamp (§18).
- **Own list actions without a second refetch** (from batch 44, APP-8, accepted). Save, unsave,
  dismiss and restore move the `recommendations` data version, so the acting tab refetches that
  area once more on the next route change. A "seen" path in `useDataVersions` after the user's
  own list mutation would skip it, but must not hide a background change that lands in the same
  window.
- **Clamp past-the-end pages on the server.** `/recommendations?page=N` past the end returns
  404, and the client has two recovery paths (404 → page 1, emptied page → previous page).
  Returning the last page (with its number) removes both; with the list refetched after a
  dismissal, the optimistic-page guard goes too.

### 18. Interface revamp

Round 9 (2026-10-27), requested by the owner. The interface grew page by page with phases
(one `max-w-3xl` column, shadcn/ui defaults); a revamp would give it one design. No ranking
change, so it can ship now, but it is big: one OpenSpec change per step, starting with the
design direction.

- **Design direction first.** Tokens (color, type scale, spacing, radius) in one place, dark
  mode, an empty/loading/error pattern used by every page. Decide before touching pages. Since
  0.12.57 `src/components/Loaded` holds the data-first order (data, else error, else loading) for
  sections and cards; detail pages and lists with 404 or empty states still gate inline.
- **Dashboard layout.** `AppShell` stacks profile summary, language chart, pipeline status,
  filters and the list in one column. A wider layout (profile and filters beside the list, the
  pipeline as a compact header bar) would show more recommendations above the fold.
- **Recommendation cards.** Match label, reasons, technologies, activity, setup facts and
  issue counts compete on each card. A clearer hierarchy: label and the top reason first, the
  rest on demand; consistent badges for technologies and difficulty.
- **Detail pages.** Recommendation and issue details as sections with a sticky summary (match
  label, GitHub link, save/dismiss) instead of one long scroll; the issue page keeps "from
  GitHub" and "ContribFinder analysis" visibly apart (spec `issue-matching`).
- **Onboarding.** The sync steps (`SyncSteps`) and discovery card as one progress view that
  explains what happens next and roughly how long it takes.
- **Profile.** Skills with their evidence (`SkillGroups`), interests and languages as one
  readable profile page instead of dashboard blocks.
- **Saved and hidden lists.** Same card as the dashboard, with the save/hide reason shown.
- **Mobile.** Every page usable at phone width (filters in a sheet, actions reachable).
- **Accessibility audit** (§5): keyboard paths, focus order, contrast in both themes, screen
  reader names; Playwright plus an axe check per page.
- **Constraints that stay:** match labels and evidence, never a percentage (CLAUDE.md §2);
  activity as observable signals, never "healthy"; setup facts shown as found / not found /
  not available, never "No"; everything under the built app's CSP (no inline scripts, no
  foreign origins: fonts and icons self-hosted, `csp.config.ts`); no new dependency without a
  reason (0.12.23 built the dismiss menu by hand for that); browser tests locate elements by
  role and name, so renamed buttons and headings need the e2e specs updated in the same change.
- *Tooling:* the `frontend-design` skill helps once the direction is set (design direction and
  a detector: the Impeccable note below; motion: the transitions.dev note, and
  why not GSAP skills or React Bits; app-screen references: the Taste Skill note); screenshots of the
  current pages are the baseline to compare against.
- *shadcn skill* (checked 2026-10-27). Authentic: documented at `ui.shadcn.com/docs/skills`, the
  skill is `skills/shadcn/SKILL.md` in the official `shadcn-ui/ui` repository, and the `skills`
  CLI (npm `skills`, `vercel-labs/skills`) is Vercel Labs'. Install only with the exact
  `npx skills add shadcn/ui`: copies elsewhere differ (`vercel-labs/vercel-plugin`, third-party
  registries; one copy rated "Critical" in a Tessl scan). Nothing malicious in the SKILL.md, but:
  - it runs `` !`npx shadcn@latest info --json` `` every time it loads (latest, unpinned npm
    package, network);
  - `allowed-tools: Bash(npx shadcn@latest *)` pre-approves every shadcn command, including
    `add --all -y` and `init ... --force` (overwrites `components.json` and CSS);
  - it can pull code from third-party registries (`@magicui`, `@tailark`, `@bundui`,
    `owner/repo`);
  - it references files not yet read (`rules/*.md`, `cli.md`, `design-system.md`,
    `scripts/showcase-coverage.mjs`).
  Against this repository's rules: `add` brings Radix dependencies (no dependency without a
  reason), presets and `apply --only theme,font` may add foreign web fonts that the built app's
  CSP blocks (self-host or extend `csp.config.ts` on purpose), and it does not know the product
  rules above. If used, at the start of the design-direction change: install project-level (not
  `-g`), read every installed file, narrow or remove `allowed-tools` so each command asks,
  consider dropping the load-time command, and add a CLAUDE.md rule (components only through a
  reviewed `add`; never `--all`, `-y` or `--force`).
- *transitions.dev skill* (checked 2026-10-30, not installed; from the repository page only,
  `SKILL.md` not read). `npx skills add Jakubantalik/transitions.dev`: a third-party library of
  UI transitions as plain CSS snippets (`:root` custom properties, `t-*` classes, a
  `prefers-reduced-motion` guard), 18 reference files (`01-card-resize.md` …
  `18-texts-reveal.md`) plus `transitions-ui-generation` (skeleton reveals, dependency-free
  runtime). No Framer Motion or View Transitions API. Candidate for a motion step after the
  design direction, and for loading states (dashboard cards, profile, onboarding progress).
  Against this repository's rules:
  - motion before tokens is backwards: its `:root` variables and `t-*` classes must fit the
    tokens the design direction defines (and shadcn's theme variables);
  - never `transitions-refine` (injects a `<script>` into the running app and starts a local
    relay: the built app's CSP blocks it, and it should) or the `transitions-dev` CLI's Pro
    recipes (browser sign-in);
  - the README is inconsistent (12 transitions listed, 18 files, "43+" claimed).
  If used: install only the `transitions-dev` skill folder, project-level, after reading every
  file; snippets copied in through a reviewed change, kept under the reduced-motion guard.
- *Impeccable* (checked 2026-10-30, not installed; from npm metadata and the repository README,
  skill files not read). `npx impeccable install`: npm `impeccable` 4.8.0 by Paul Bakaus
  (`github.com/pbakaus/impeccable`, `impeccable.style`; first published 2026-03-30). No npm
  install scripts; optional per-platform CLI binaries (`@impeccable/cli-windows-x64`, ...).
  Better fit than transitions.dev, for the design-direction step itself:
  - 24 commands: plan (`init`, `shape`, `document`, `extract`), steer (`typeset`, `colorize`,
    `layout`, `animate`, `quieter`, ...), review (`critique`, `audit`), finish (`polish`,
    `harden`, `adapt`, `optimize`, `onboard`). `PRODUCT.md` and `DESIGN.md` are committed:
    the written direction and tokens §18 asks for before touching pages.
  - A detector, 62 deterministic rules, no LLM or key: `npx impeccable detect <dir>` (JSON,
    GitHub Actions annotations, exit 2 on findings), usable as a CI check. On `.tsx` source
    only pattern rules run; contrast and tiny text need a rendered page.
  Against this repository's rules:
  - the installer adds a design hook that scans every UI file the agent edits, and installed
    hooks run even when the model's commands are denied (outside the permission prompts);
  - an engine binary downloads on first use to `~/.impeccable/bin/`: outside the repo and
    outside `npm run audit:deps`;
  - a new design fetches the impeccable.style catalog and sends an anonymous record of the
    directions shown and chosen (`npx impeccable telemetry off` / `DO_NOT_TRACK=1` stops the
    record, not the fetch);
  - it writes subagents and `.impeccable/` (`config.json`, `design.json`); the README does not
    list every file it puts under `.claude/`;
  - it flags Inter as overused and steers toward another font: any web font must be self-hosted
    or the built app's CSP blocks it (`csp.config.ts`).
  If used, at the start of the design-direction change: `--providers=claude --scope=project`,
  decline the hook, telemetry off, read every installed file before the first run, commit
  `DESIGN.md` as the source of the tokens. Smallest footprint: no skill, only a pinned
  `npx impeccable@4.8.0 detect apps/frontend/src` in CI.
- *Taste Skill* (checked 2026-10-30, not installed; read the marketplace manifest, file tree,
  `SKILL.md` and a scan of the scripts). `/plugin marketplace add Leonxlnx/taste-skill`: plugin
  2.1.5, MIT, one skill `design-taste-frontend`. It deals one of 20 researched directions,
  builds with credited photos from open collections, checks the page in a real browser at 1440,
  768 and 390 px and fixes the worst problems from screenshots (up to three rounds); v2.1 adds
  app screens (`inspect.mjs --app`). Footprint is small: the manifest declares only the skill
  folder (no hooks, commands, MCP servers, `allowed-tools` or telemetry seen); scripts need
  Node 22+ and a local Chrome/Edge/Chromium and install nothing; `inspect.mjs` serves files on
  `127.0.0.1` and drives the browser over CDP; only `assets.mjs` uses the network (Openverse,
  Wikimedia Commons, Art Institute of Chicago, the Met, archive.org, NASA; no keys); working
  files in `.taste-skill/`. Weakest fit of the three:
  - built for landing pages and award-style sites; this app has one landing page and is
    otherwise app screens;
  - 30-45 minutes and "a few hundred thousand tokens" per build (README);
  - its description triggers on almost any page work, so installed it would take over ordinary
    frontend edits;
  - its house style and directions would compete with the design direction §18 decides first;
  - photos must be downloaded into the repo (remote images are blocked by the CSP);
  - a plugin marketplace follows the author's repository, so later versions arrive unreviewed.
  Not to install. Worth reading as input to the design-direction change:
  `references/app-screens.md`, `layout.md`, `type.md`; `inspect.mjs --app` could check the
  redesigned pages at three widths if Playwright does not already.
- *GSAP skills* (checked 2026-10-30, not installed; read the file tree, plugin manifest,
  README and skill front matter). `greensock/gsap-skills`: official, MIT, about 17.5k stars;
  eight skills (core, timeline, ScrollTrigger, plugins, utils, React, frameworks, performance).
  Markdown only: the manifest points at `./skills/`; no scripts, hooks, MCP servers,
  `allowed-tools` or network. Install `/plugin marketplace add greensock/gsap-skills` or
  `npx skills add https://github.com/greensock/gsap-skills`; only the `greensock` repository
  (forks and mirrors exist). Against this repository's rules:
  - useful only with GSAP, and the frontend has no animation library: `gsap` plus `@gsap/react`
    would be a new dependency for a data-heavy app where CSS transitions suffice;
  - the README and skill descriptions tell agents to recommend GSAP for any animation request
    without a named library, so installed it pushes `npm install gsap` (which only the owner
    runs: `allow-remote=none`);
  - its strengths (ScrollTrigger, SplitText, MorphSVG) suit marketing pages, not the dashboard.
  Good parts if GSAP is ever chosen: `gsap.matchMedia()` for reduced motion, `useGSAP` cleanup
  on unmount. Not now; only if the motion step chooses GSAP on purpose (reason recorded), then
  with this official skill.
- *React Bits* (checked 2026-10-30, not installed; read repository metadata, licence, README
  and `public/r/registry.json`). `DavidHDev/react-bits`: about 50k stars; 215+ animated
  components and backgrounds, each in JS/TS and CSS/Tailwind flavors. Not a skill: the free
  agent route is the shadcn MCP server plus a third-party registry
  (`"@react-bits": "https://reactbits.dev/r/{name}.json"` in `components.json`,
  `npx shadcn@latest mcp init --client claude`); the agent skills ("Agent Kit", 20) are Pro,
  paid. Licence MIT + Commons Clause: use in an app is fine, selling or redistributing the
  components is not. Against this repository's rules:
  - dependencies: across 1,274 registry entries, `motion` 112, `@hugeicons/*` 112 (duplicates
    lucide), `gsap` 72, `ogl` 40, `three` 24, `matter-js` 8, `@react-three/*` a few; most
    components bring one;
  - the style is WebGL showpieces for landing pages (Ballpit, Liquid Chrome, Laser Flow); only
    a few fit app screens (count-up, text reveal, animated lists);
  - the MCP route is the third-party-registry pull the shadcn note warns against, and an added
    component brings its dependencies;
  - WebGL and canvas components may need CSP changes (not checked; test against the built
    app's policy, `csp.config.ts`);
  - the README is largely a Pro upsell.
  Not to install; no registry, no MCP. At most, in the motion step, one dependency-free CSS or
  Tailwind flavor copied by hand through a reviewed change, under the reduced-motion guard.

### 9. Profile freshness

- Beat schedule (`config/settings/base.py`) has no user resync: the profile is frozen until the
  user clicks Refresh, while recommendations keep refreshing against it. Option: weekly resync
  for users active in the last N days, within the GitHub budget.

## Platform and tooling

### 15. Dev tooling and operations

Round 5 (2026-10-21), from the `dev-scripts-checks` review and cleanup pass.

- **One "dispatch after commit" helper** (from the 0.12.41 `/simplify` review). Only
  `queue_revocation` dispatches with `transaction.on_commit(..., robust=True)`; `services/jobs.py`,
  `services/repositories/backlog.py` and `services/data_deletion.py` call `.delay()` directly, so
  a broker outage raises there but is logged here. A `services/dispatch.after_commit(task, *args)`
  used everywhere would give one policy.
- **Error handling for views the browser navigates to** (same review). The OAuth callback catches
  `Exception` itself to redirect instead of a JSON 500; a small redirect-on-error wrapper for
  navigation views would replace that one-off catch-all.
- **A 401 rule per query, not per key** (from the batches 32–34 `/simplify`, 2026-11-02). The
  query cache special-cases the identity query by hash (`isMe`) and, since 0.12.47, by whether it
  held data; mutations use `meta.endsSession`. A query `meta` opt-out (set by `useMe` while it has
  no identity) would make both sides one mechanism.
- **Bulk repository locks behind one helper** (same pass, `Bug_Backlog.md` FD-2).
  `release_name` locks the holder of a name out of GitHub ID order inside the sorted upserts of
  the sync and discovery; a `lock_repositories(ids)` in ID order, taken before the upserts, would
  enforce the rule in one place. Belongs with the `services/repositories/` sweep.
- **One traceback rule for job failures** (from the batches 36–38 `/simplify`, 2026-11-02).
  `revoke_later` and the repository refresh log `internal_error` with its traceback;
  `run_tracked_job` logs every final failure as a plain warning, so a sync or analysis bug loses
  its stack. A shared `retry.log_failure(logger, decision, ...)` used by all three would give one
  rule. Belongs with a `services/` follow-up (`Bug_Backlog.md` SIM-10).
- **The backlog owns sending its refreshes** (same pass, SIM-11). `queue_batch` stamps
  `refresh_queued_at`, and the task unstamps refused sends and renews on retry
  (`backlog.mark_queued`/`unmark_queued`); a `backlog.dispatch(batch, send)` would keep every
  stamp rule in `backlog`. Pairs with the "dispatch after commit" helper above.
- **Feedback services take ids** (from the 0.12.51–0.12.54 `/simplify`, `Bug_Backlog.md` batch
  50). Since 0.12.53 the views pass a `Recommendation` loaded with `only("pk", "repository_id")`,
  and `save`, `dismiss` and `record` must not touch `recommendation.repository` before their own
  re-read (a deferred field would be one hidden query). Taking `recommendation_id` and
  `repository_id`, as `unsave` and `restore` already do, would make that rule the type.
- **Retire `DELETE /recommendations/{id}/save`** (same pass). The SPA unsaves through
  `DELETE /saved/{repository_id}` since 0.12.53; the old endpoint still 404s once a generation
  drops the recommendation. Deprecating it in OpenAPI first, then removing it, is a contract
  change and needs its own OpenSpec change.
- **Phrase matching without a case-folded lookup** (same pass). `PhraseMatcher` matches with
  `re.IGNORECASE` and maps the match back through `casefold()`, skipping the few variants that
  fold differently (dotless `ı`). Named groups per slug (`match.lastgroup`) would map every match
  directly. No ranking change for ASCII text, but it touches every taxonomy path.
- **Difficulty signal names in the API schema** (from the 0.12.55–0.12.57 `/simplify` and
  review, `Bug_Backlog.md` SIM2-11, CR-9). `tests/test_issue_signal_wording.py` reads
  `evidence.ts` with a regex to check every signal `classify` writes has words on the issue page.
  Declaring the signal names as an enum in the issue detail serializer would put a
  `DifficultySignal` union in `schema.d.ts`, so `SIGNAL_TEXT: Record<DifficultySignal, …>` is
  checked by `tsc` and `api:sync` drift. OpenAPI addition (not breaking), needs an OpenSpec change.
- **A generic data-migration round trip.** `tests/test_seed_migrations.py` covers the scoring
  seeds only. One test that migrates every app back to its first migration and forward again
  would catch the next irreversible or non-idempotent `RunPython`.

### 5. Platform

- **GitHub API budget across users.** Search allows 30 requests/min per token and the
  app-credential backlog is shared. Model what many concurrent onboardings do.
- **Accessibility.** Not covered by any spec or backlog row.
- **Observability.** Stage latencies, failure-rate trends (post-MVP: Sentry/Prometheus).
- **Making the repository public** (checked 2026-10-30). History scanned: no real secrets (only
  fake test tokens and the log-redaction regex), `.env`, `judging/`, `reports/` never
  committed, no-reply commit emails, persona-only datasets. Done: `LICENSE` (MIT),
  `SECURITY.md` (private vulnerability reporting), the SRS files untracked and kept locally (all
  in v0.12.39; the first sweep module, `config/`, reviewed and fixed in the same release)
  (their old copies stay in history; they are the owner's, not confidential). CI hardened in
  v0.12.60 (actions pinned to commit SHAs with Dependabot updates, `persist-credentials: false`,
  locked installs only). Left, in the repository's GitHub settings (owner only):
  - turn on private vulnerability reporting (`SECURITY.md` points to it), secret scanning with
    push protection, and Dependabot alerts (free for public repositories);
  - protect `main` (no force-push, required checks: CI and the dependency audit);
  - Actions: require approval for workflows from fork pull requests, read-only default
    `GITHUB_TOKEN` permissions;
  - flipping to public is hard to undo: clones and forks persist if it goes private again.

## Evaluation

### 3. Evaluation rigor

- **Significance gate.** Whether the improvement rule should also require a marked NDCG@10
  bootstrap interval (the intervals are printed since v0.12.19; v2's NDCG@10 +0.0195 is
  [-0.0023, +0.0501]). Decide once real developers make the benchmark larger (K-1, optional); with
  six developers a gate would refuse almost every change.
- **Inter-rater agreement.** Single judge today. A second judge on about 10 rows (Cohen's κ)
  shows whether the grades mean anything.
- **Pooling bias.** Only candidates discovery found get judged; unjudged = irrelevant, so a
  config that surfaces new good repos is penalized.
- **Discovery recall.** Evaluation starts from a fixed pool, so discovery misses are invisible.
  Add a stage metric: of the judged-relevant repos, how many did discovery find?
- **Issue-level evaluation** (K-3, already tracked).

---

# Ranking-visible (must win on the benchmark)

## Ranking and matching

### 1. Matching techniques

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

### 2. Contribution-success signals

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

## Retrieval

Ranking only reorders what discovery finds. All four strategies (`services/discovery/queries.py`)
are keyword search; qualifiers are only `archived/fork/pushed/stars/-user`. Retrieval changes
need the discovery-recall metric (§3) first, or gains stay invisible. (Round 2, 2026-10-20.)

### 11. Code-or-list detection

Round 3 (2026-10-21), from the `discovery-repository-data` change (v0.12.7) and its first real
discovery run; also §12 and §13.

- **`not_code` by content, not only markers†.** Today a suspected list (`awesome-*`, list
  topic) is code when it declares manifest dependencies, and docs repositories without a list
  marker always pass (K-4). Lists often carry lint or site tooling (`awesome-lint`, mkdocs), so
  dependencies are weak evidence. Stored data already allows a better signal: share of
  non-markup bytes in `RepositoryLanguage`, README link density, or source files at the root
  (the root listing is already fetched for manifests, and the setup facts read from it are
  stored since v0.12.24). Needs a judged sample of lists and
  tools first, since it decides what users can be shown at all.

### 12. Search budget

- **Act on the yield report†.** `discovery_report` (v0.12.25) shows, per strategy and star band,
  how many results each request returns and which rejections eat them (`no_license` first in the
  first real run). Once enough runs exist: narrow the query type that wastes most of its page,
  move budget between strategies or bands, or give a high-yield query a second page. Each of these
  changes what users are recommended, so it must win on the benchmark and show its gain in the
  report.

### 6. Retrieval sources

- **Opportunity qualifiers.** GitHub search supports `good-first-issues:>0` and
  `help-wanted-issues:>0`; unused. One query variant per strategy, or a band-style mix.
- **Upstream dependencies ("contribute to what you use").** Manifests are already parsed; map
  each package to its repo via registry metadata (PyPI `project_urls`, npm `repository`, crates
  `repository`, Go module path). Strongest contribution prior; explanation is honest ("You
  depend on X in 3 repos"). Needs non-GitHub HTTP: a separate module (e.g.
  `services/registries/`) with the same retry, cache and degrade-on-failure rules.
- **`similar_repo`.** In the FR-REPO-002 source enum, never built. Seed from saved and
  contributed repos (topics, dependencies, owner). Feedback changes what is found, not the score.
- **Starred repos.** `GET /users/{u}/starred`, public, no scope. Candidates plus a strong
  interest signal. Disclose on the privacy page.

## Learning from interaction

### 4. Learning from interaction

Follow-ups of the shipped feedback ideas (see "Shipped"); each needs real traffic or real-developer grades (K-1, optional).

- **Intervals on the report shares.** `feedback_report` shares have no uncertainty yet; add
  them once there is enough traffic for them to mean something.
- **Dismiss reasons against grades.** Compare the reasons users give with K-1 grades of 0: do
  "not my stack" dismissals match what a judge grades irrelevant?
- **Move the label bands†.** If real use shows the labels out of order (calibration verdict),
  change `params.bands`; a ranking change, so it goes through `evaluate_ranking`.

---

# Shipped

Newest first.

| Idea | § | Shipped in |
|---|---|---|
| Browser tests on the production build (`vite build` + `vite preview`, CSP violations fail a test) | §14 | v0.12.38 (`E2E_DEV_SERVER=1` keeps the dev server locally) |
| Route-level id validation (`RouteId` wrapper for detail routes) | §14 | v0.12.37 (same dead ends; the page remounts per id) |
| Released-name refresh queued at commit (`backlog.queue_released`) | §13 | v0.12.36 (pooled holders only, not inline) |
| Labeled-issue fetch (entry-labeled issues beyond the recent cap) | §7 | v0.12.35 (only for capped repositories; default label names only) |
| CI hardening for the public repository (locked installs, SHA-pinned actions, no stored token, Windows runner tests) | §5 | v0.12.60 (backlog batch 49; Dependabot for actions only) |
| Dependency audit in CI (`pip-audit`, `npm audit`, accepted list, weekly run) | §5 | v0.12.34 (no CodeQL; Dependabot for actions since v0.12.60, npm and pip stay manual) |
| One JSON writer for management commands (`core/reports.py`) | §15 | v0.12.33 (T-14; non-ASCII kept in every file) |
| Content-Security-Policy (backend header; meta tag in the built SPA) | §5 | v0.12.30 (no reporting endpoint; the SPA host adds `frame-ancestors`) |
| New seeds stored inactive (`_seeding.store_inactive`, guard test) | §15 | v0.12.28 (v1/v2 seeds unchanged) |
| Data versions (refetch only the areas that changed, whatever changed them) | §14 | v0.12.27 (Y-6; S-8 narrowed; no timer) |
| Post-analysis pool cleanup (lists found by the run's own analysis leave the pool) | §11 | v0.12.26 (X-9) |
| Search yield per strategy and star band (`discovery_report`) | §12 | v0.12.25 (measurement only; acting on it is ranking-visible) |
| Setup readiness (CI, tests, dev container, Docker Compose at the root) | §8 | v0.12.24 (shown, never scored; root only) |
| Dismiss reasons (optional, reported per config) | §4 | v0.12.23 (never scored) |
| Match-label calibration in the feedback report | §4 | v0.12.21 (raw shares per label; bands unchanged) |
| Online feedback report per config (`feedback_report`) | §4 | v0.12.20 (shares of decisive actions; no impressions) |
| Bootstrap intervals in the evaluation report | §3 | v0.12.19 (information only; no gate) |
| Activation off the request path (admin points to the command) | §17 | v0.12.18 (S-6; no tracked job) |
| Job status keys outside `['profile']` | §17 | v0.12.15 (S-9) |
| One registry of lazy components | §17 | v0.12.15 (S-10; still preloaded in every test file) |
| Keyset index for saved and hidden lists | §17 | v0.12.15 (S-11; plain index, no row-value comparison) |
| Helper modules fail loudly when run (`refuseRun`) | §15 | v0.12.13 |
| Activation as an explicit operator action (`activate_scoring_config`) | §15 | v0.12.13 (later seeds stored inactive in v0.12.28) |
| Keyset (cursor) pagination for saved and hidden lists | §14 | v0.12.12 (Y-7) |
| Profile refreshed when a generation finishes (part of "data versions") | §14 | v0.12.12 (Y-6 in part) |
| Lint and format `scripts/` in CI | §15 | v0.12.11 (P-5) |
| Line endings fixed in the repository (`.gitattributes` `* text=auto eol=lf`) | §16 | v0.12.11 (P-2) |
| One metadata write path (`_update_metadata` wrappers removed) | §16 | v0.12.11 (Q-12) |
| Tests import builders from `e2e.builders` | §16 | v0.12.11 (Q-12) |
| Snapshot index with the `-id` tie-break | §16 | v0.12.11 (Q-10 in part; the rest accepted in v0.12.13) |
| One `taskkill` per stop | §15 | v0.12.10 (Z-9) |
| Playwright browser tests for the main flows | §10 | v0.12.8 (backlog batch 9) |
