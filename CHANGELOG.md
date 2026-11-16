# Changelog

All notable changes to ContribFinder are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning follows
[Semantic Versioning](https://semver.org/). Before the MVP, each completed roadmap phase bumps
the minor version (`0.x.0`).

## [Unreleased]

## [0.12.77] - 2026-11-16

Fixes for the first CodeQL code scan, run after the repository went public (`Bug_Backlog.md`
batch 75). No OpenSpec change (the fixes follow the existing specs), no migration, no API or
ranking change. No e2e run.

### Fixed

- HTML comments in profile READMEs, manifests and issue bodies end where the HTML parser ends
  them: `--!>` also closes a comment, and `<!-->` / `<!--->` are empty. Before, text after such a
  comment was dropped as if still commented out (CodeQL `py/bad-tag-filter`).
- Badge and skill-icon evidence counts only `shields.io` and `skillicons.dev` or their
  subdomains, read from the URL's host. A lookalike host (`notshields.io`) no longer counted, and
  a host with a port (`img.shields.io:443`) no longer missed (CodeQL
  `py/incomplete-url-substring-sanitization`).
- The Content Security Policy tests' "no inline script" checks match `<script>` in any case
  (CodeQL `py/bad-tag-filter`).

### Changed

- The repository is public (2026-11-16): private vulnerability reporting, secret scanning with
  push protection, Dependabot alerts, a `main` ruleset (pull request and the six CI checks) and
  CodeQL default setup are on.
- README "Known issues" (a release-by-release batch log, last updated at 0.12.33) replaced by
  "Known limitations": a short list of what does not work yet, linking `Bug_Backlog.md` and
  this changelog.

## [0.12.76] - 2026-11-15

Root fix for the GitHub response cache outliving a data deletion (`Bug_Backlog.md` SVC-16,
closing SVC-6 and SVC-15). OpenSpec change `etag-cache-generation`. One migration
(`accounts/0006`); no API, OpenAPI or ranking change. No e2e run. `/simplify` and a fix-diff
`/code-review` ran before release (`Bug_Backlog.md` batches 73 and 74).

### Added

- README "Screenshots" section: dashboard, recommendation detail, skills evidence, saved and
  hidden projects (`docs/screenshots/`). PNG files are marked binary in `.gitattributes`.

### Fixed

- A GitHub response that a cancelled sync receives after "delete my data" (or account deletion)
  committed is no longer left in the user's response cache. Each deletion bumps a per-user cache
  generation; a client built before it re-reads the generation after every cache write and
  deletes the entry it just wrote. Before, a timed second purge only narrowed the window, and a
  worker slower than `SYNC_STALE_AFTER_SECONDS` escaped it (SVC-16).
- A cache purge that fails as a data deletion commits (a brief cache outage) is retried in the
  background, up to three times; before, the user's existing entries stayed until they expired.
- A failed generation read drops the entry just written instead of keeping it.

### Removed

- The unconditional delayed second cache purge; `github.purge_user_cache` now runs only to retry
  a failed purge.

## [0.12.75] - 2026-11-15

Fixes from the fix-diff review of 0.12.70–0.12.74 (`Bug_Backlog.md` batch 72, CR7-1…CR7-10).
The fixes follow the existing specs, so there is no OpenSpec change. No API, OpenAPI, migration or
ranking change. No e2e run.

### Fixed

- `feedback_report --config V` takes back undone decisions again. A restore (no version) and an
  unsave under a later version undo a decision of `V`. Before, the version filter in the query
  dropped those undo events (CR7-1).
- Errors from a job's follow-up task, sent after the commit, are logged and no longer escape
  the finished job. One example is an inline task failing in eager mode. The job stays
  COMPLETED and job recovery re-sends the PENDING follow-up (CR7-2).
- A job with a follow-up hook locks the user's active jobs in pk order before it finishes.
  The hook's expiry of stale jobs can no longer deadlock with job recovery or a cancel (CR7-3).
- Onboarding offers "Sign in with GitHub again" when Try again is rejected for a missing GitHub
  connection, even after the last sync failed for another reason (CR7-4).
- A second dismissal counts as in flight from the start of its optimistic update, so the first
  one no longer refetches the list and briefly brings the second card back (CR7-5).
- "Couldn't hide." shows only on the page visit where the dismissal failed. Before, it also
  showed on the recommendation's detail page and on a later visit of the list (CR7-6).
- A failed dismissal is not put back on a list page when a refetch has moved it to another page
  of the same list. Before, it was listed twice and counted one too many (CR7-7).
- A relative time picks its unit after rounding: "1 hour ago", not "60 minutes ago" (CR7-9).

### Changed

- `usePipelineStage` doc matches its caller (CR7-8). The category headings and list names come
  from one record (CR7-10).

## [0.12.74] - 2026-11-15

Root config fixes from the review sweep, its last module
(`openspec/changes/archive/2026-11-15-root-config-review-fixes/`; spec `developer-tooling`;
`Bug_Backlog.md` batch 70, ROOT-1…ROOT-10). No API, OpenAPI, migration or ranking change.
`/simplify` and fix-diff `/code-review` skipped (owner's call). No e2e run (no browser flow
change). `docker compose up` not run (Docker not installed here); the compose file parses.

### Fixed

- Docker mode publishes the backend and the frontend on `127.0.0.1` only, so the debug dev
  server is not reachable from the network (ROOT-1, ROOT-2).
- The Redis container is no longer published on host port 6379, where it collided with the WSL
  Redis that `npm start` uses (ROOT-3).
- Docker mode takes `DJANGO_SETTINGS_MODULE` from `.env`, never from the shell (ROOT-8).
- Frontend edits on a Windows host reach Vite in the container (`VITE_WATCH_POLLING`) (ROOT-5);
  the README says how to rebuild after a dependency change (`--renew-anon-volumes`) (ROOT-4).
- `DJANGO_DEBUG=false` turns debug off with the development settings (ROOT-6).
- `.env.example` lists the 19 settings it was missing (throttles, sync limits, session age,
  `SECURE_SSL_REDIRECT`, `GITHUB_OAUTH_REDIRECT_URI`, `EXPERIENCE_THRESHOLDS`, ...), and a test
  keeps it complete (ROOT-7).

### Changed

- Postgres credentials defined once in the compose file (ROOT-9).
- Root `package.json`: `npm run format:scripts:write`, and `engines.node >=22` (ROOT-10).

## [0.12.73] - 2026-11-15

Shared component fixes from the review sweep (`openspec/changes/archive/2026-11-15-shared-components-review-fixes/`;
spec `web-client`; `Bug_Backlog.md` batch 69, CMP-1…CMP-10). Frontend only: no backend, API,
OpenAPI or migration change. `/simplify` and fix-diff `/code-review` skipped (owner's call).
`npm run e2e` 11/11 (one new dead-end spec).

### Fixed

- A page that throws while rendering shows "Something went wrong" with Reload and the way back
  to the dashboard, instead of the router's default error screen; a time the browser cannot read
  shows as "Unknown" (CMP-1).
- While a failed first load is retried, the page shows "Loading…", not the failure (CMP-5).
- A dead end (a recommendation or issue that is gone, a failed load, an invalid link) is a
  heading that takes keyboard focus; a failed load offers "Try again" (CMP-8).
- Back to a page opened at a section (`#relevant-issues`) no longer scrolls to and focuses it
  again; a new visit or a reload still does (CMP-3).
- A long detail value wraps instead of widening the page (CMP-9).

### Changed

- Both detail pages use one gate, `DetailLoaded` (CMP-7); one `Loading` element replaces the
  copied "Loading…" paragraphs (CMP-10); `ExternalLink` calls `onOpen` without arguments (CMP-2,
  latent).

## [0.12.72] - 2026-11-15

Pipeline progress fixes from the review sweep (`openspec/changes/archive/2026-11-15-pipeline-progress-review-fixes/`;
specs `sync-jobs`, `web-client`; `Bug_Backlog.md` batch 68, PIPE-1…PIPE-10). One backend fix
(`services/jobs.py`); no API, OpenAPI or migration change. `/simplify` and fix-diff
`/code-review` skipped (owner's call). `npm run e2e` run (onboarding and dashboard progress).

### Fixed

- A finished job and the follow-up job it starts (discovery after a sync or analysis, a
  generation after discovery, the generation rerun) are committed together. Before, the SPA could
  read the previous finished stage, stop polling, and leave the new stage running unobserved
  (PIPE-1, PIPE-2). A failing follow-up still keeps the job's outcome.
- The dashboard follows discovery and generation while the profile has no data yet (PIPE-3,
  partial).
- Onboarding offers "Sign in with GitHub again" when Start sync is refused because GitHub needs a
  new sign-in (PIPE-4).
- A stalled discovery shows the stalled notice instead of "Finding projects…" (PIPE-5); a stalled
  sync step shows "Stopped" without spinning (PIPE-7).
- "Last checked" times update each minute, use the browser's language, and never read "in 2
  minutes" when the server clock is ahead (PIPE-6).
- An unknown step state reads as pending instead of crashing the page (PIPE-8).

### Changed

- Relative times live in `src/lib/format` (`formatRelative`) (PIPE-9); one GitHub failure table
  for sync and discovery messages (PIPE-10).

## [0.12.71] - 2026-11-14

Profile page fixes from the review sweep (`openspec/changes/archive/2026-11-14-profile-ui-review-fixes/`; spec `developer-profile`;
`Bug_Backlog.md` batch 67, PRF-1…PRF-10). Frontend only: no backend, API, OpenAPI or migration
change. `/simplify` and fix-diff `/code-review` skipped (owner's call). No e2e run (no browser
flow change).

### Fixed

- Expanded skills and interests stay expanded when a re-analysis refreshes the profile: they are
  keyed by slug, since each analysis recreates the rows with new ids (PRF-1).
- The language skill list and the languages chart have distinct names ("Language skills",
  "Languages by code") (PRF-3).
- Skills expand with a native disclosure, like interests: no `aria-controls` pointing at a
  missing element (PRF-5, PRF-8). A truncated skill name shows in full on hover (PRF-9).
- The languages chart orders rows by bytes and folds into "Other" only when two or more
  languages are left; a single leftover is shown by name (PRF-6).
- Interest evidence shows when it was observed, as skill evidence does (PRF-7).
- A skill's evidence label is never empty (PRF-4, latent).

### Changed

- Category order comes from the category labels, so every category is shown (PRF-2, latent);
  one shared evidence row for skills and interests (PRF-7); the profile data version uses the
  profile query keys (PRF-10).

## [0.12.70] - 2026-11-14

Feedback interface fixes from the review sweep (`openspec/changes/archive/2026-11-14-feedback-ui-review-fixes/`; spec `recommendation-feedback`;
`Bug_Backlog.md` batch 66, FBK-1…FBK-10). Frontend only: no backend, API, OpenAPI or migration
change. `/simplify` and fix-diff `/code-review` skipped (owner's call). `npm run e2e` 10/10.

### Fixed

- A failed save, unsave or dismiss reverts only its own card. Before, it wrote back every cached
  list page, so another card's confirmed dismissal came back (FBK-1).
- A failed dismissal puts the card back at its place, with its count (FBK-1).
- Each dismissal gets its own undo notice: a failed undo of one project no longer shows on the
  next (FBK-2).
- The undo notice stays open while an undo is pending; a failed undo keeps it 10 seconds from the
  failure, so "Undo didn't work." is always seen (FBK-4).
- A dismissal confirmed after the user left the detail page no longer pulls them back to the
  list (FBK-3).
- Failed save, unsave, dismiss, remove, restore and "Show more" now say so next to the control
  ("Couldn't save.", "Couldn't hide.", ...); trying again clears it (FBK-5).

### Changed

- The saved page gates both lists with `Loaded`; `recommendationsRootKey` replaces the typed-out
  key; both query cancels run together (FBK-8…FBK-10).

## [0.12.69] - 2026-11-14

Fixes from the fix-diff `/code-review` (high) of the uncommitted 0.12.66–0.12.68 code
(`Bug_Backlog.md` batch 71, CR6-1…CR6-6; owner: fix all). No OpenSpec change, as batch 62: the
fixes follow the existing specs. No API, OpenAPI or migration change; baselines unchanged.

### Fixed

- Feedback report: an undo cancels the action it undoes whatever its version. A restore records
  no version and an unsave after a regeneration a later one, so before, undone dismissals and
  saves still counted as outcomes.
- Two overlapping dismissals could each leave the list refetch to the other, so neither
  refetched it. The list is now refetched once no dismissal awaits its answer.
- An empty recommendation list no longer shows "Loading…" during every background refetch or
  next to a running generation.
- The freshness sweep skips only broker errors; a database error fails the beat task.

### Changed

- Issues are matched again when issue fit and difficulty fit both weigh 0: matched issues are
  shown, not only scored (reverts RNK-9).
- `baseline.write` no longer checks dataset locations itself; `check_source` is the one rule.

## [0.12.68] - 2026-11-14

Recommendations view fixes from the review sweep
(`openspec/changes/archive/2026-11-14-recommendations-view-review-fixes/`; specs
`recommendations-view`, `recommendation-feedback`; `Bug_Backlog.md` batch 65, REC-1…REC-10).
Frontend only: no backend, API, OpenAPI or migration change. No separate `/simplify` or
fix-diff `/code-review` run (owner's call); `/security-review` found nothing.

### Fixed

- A filter from a link that is not one of the options (for example `?language=ruby`) shows as
  selected instead of "Any", and "Clear filters" appears whenever a filter is active and beside
  the "filters are not valid" message (REC-1).
- Dismissing every card on page 1 shows the recommendations that followed, not "No suitable
  projects yet": the list is reloaded once the dismissals are confirmed (REC-2). While a
  dismissal or that reload is pending, an emptied page says "Loading…" (REC-3).
- The Undo notice after dismissing from the detail page is offered once: a reload or Back no
  longer brings it back (REC-4).
- While the next page loads, the shown results are marked as loading and dimmed, and Previous
  and Next are disabled, so a second click cannot skip a page (REC-5).
- "Back to recommendations" and dismissing on the detail page return to the list page and filters
  it was opened from (REC-6).
- Language shares on the detail page are given as text ("52%", "under 1%"), not only as bars
  (REC-7).
- The size filter offers "Size unknown", which the backend already accepted (REC-9).

### Changed

- Activity and size wording is typed with the generated API enums (REC-8); the difficulty text
  reuses its constant (REC-10).
- Tests: `renderRoute` accepts a location with navigation state; a browser test checks that Back
  returns to the list page.

## [0.12.67] - 2026-11-14

Evaluation fixes from the review sweep (`openspec/changes/archive/2026-11-14-services-evaluation-review-fixes/`;
spec `recommendation-evaluation`; `Bug_Backlog.md` batch 64, EVL-1…EVL-10, EVL-8 accepted). No
ranking change, no scoring configuration change, no migration, no setting. OpenAPI stays `1.0.0`;
`baselines.json` is byte-identical. No separate `/simplify` or fix-diff `/code-review` run
(owner's call); `/security-review` reported one candidate (formula cells in the judging CSV,
3/10), fixed as hardening under EVL-6.

**Feedback report shares from before and after this release are not comparable:** shares now
count one outcome per user, repository and configuration, not every event.

### Fixed

- Feedback report: shares count outcomes, not events. Each user, repository and configuration
  version has at most one, its latest decisive action that was not undone (an unsave undoes the
  latest save, an undismiss the latest dismissal), placed in that action's rank bucket and match
  label. Repeated opens no longer inflate a share; action counts stay every event (EVL-3).
- Feedback report: the position-adjusted share reports its coverage, the part of the bucket
  weight behind it; compare adjusted shares at similar coverage (EVL-2).
- Feedback report: dismiss reasons and match labels no longer offered are listed after the current
  ones instead of disappearing; calibration still uses the current labels only (EVL-7).
- `evaluate_ranking`: a bootstrap difference is marked only with at least 6 developers, the fewest
  for which an exact sign test can reach 5%; with fewer the block says so and gives the count.
  Holdouts (4 developers) are never marked. Intervals are unchanged (EVL-1).
- `--write-baseline` writes `baselines.json` whole or not at all, a failed write is a command
  error (EVL-4), and it refuses a dataset that is not `evaluation/<name>.json`, where the baseline
  test looks (EVL-5).
- Datasets: an issue `updated_at` without a UTC offset is rejected, so issue order cannot depend
  on the machine's time zone (EVL-9).
- Judging sheets: text cells starting with `=`, `+`, `-`, `@`, a tab or a carriage return get a
  leading `'`, so a spreadsheet shows them instead of evaluating them (EVL-6). `build_benchmark`
  and `benchmark_sheet` reject badly shaped input with an error naming it, not a traceback; a
  repository resolved by `--on-conflict first` is listed once (EVL-10).

## [0.12.66] - 2026-11-14

Ranking fixes from the review sweep (`openspec/changes/archive/2026-11-14-ranking-review-fixes/`;
specs `recommendation-engine`, `recommendation-explanations`, `recommendation-evaluation`;
`Bug_Backlog.md` batch 63, RNK-1…RNK-10). No scoring configuration change, no migration, no
setting. OpenAPI stays `1.0.0`; baselines unchanged (stored configurations hit none of RNK-3,
RNK-4, RNK-9). No separate `/simplify` or fix-diff `/code-review` run (owner's call);
`/security-review` found nothing.

### Fixed

- The freshness sweep waits after a failed generation only while the latest finished generation
  is that failure: a failure followed by a completed generation no longer delays a re-analysis
  by up to 6 hours (RNK-1).
- Activating a new configuration regenerates developers whose last generation stored no
  recommendations: due when the last completed generation ran under another version (RNK-2).
- One developer whose job cannot be queued no longer stops the freshness sweep for the others;
  the failure is logged and job recovery re-sends the pending job (RNK-6).
- Activation fails, changing and auditing nothing, when the configuration being activated is
  deleted before the switch, instead of leaving no active configuration (RNK-5).
- Framework match ignores a framework found only through a source weighted 0 (RNK-3), and
  openness evidence names only affordances worth more than 0 points (RNK-4).
- A reason whose contribution rounds to 0 at 4 decimals is not stored (RNK-7).

### Changed

- Contributions are computed once: scoring carries them and reasons reuse them; the unused
  `weighted_score` is removed and `reasons` has no default that dropped relevance scaling
  (RNK-8, RNK-10).
- Issues are loaded and matched only when issue fit or difficulty fit is weighted above 0 (RNK-9).

## [0.12.65] - 2026-11-14

Matching fixes from the review sweep (`openspec/changes/archive/2026-11-14-services-matching-review-fixes/`;
specs `repository-activity`, `recommendation-engine`, `recommendation-explanations`;
`Bug_Backlog.md` batch 60, MAT-1…MAT-8, MAT-6 rejected by design). No scoring configuration
change, no migration. OpenAPI stays `1.0.0`; baselines unchanged (evaluation datasets give
activity and repository counts directly). MAT-1, MAT-4 and MAT-5 can change activity values, and
so scores and order, for recommendations generated after the release.
One `/simplify` (`Bug_Backlog.md` batch 61, SIM4-1…SIM4-8) and one fix-diff `/code-review` (batch 62, CR5-1…CR5-8) over the combined 0.12.64–0.12.65 code, fixed before release.

### Fixed

- Activity is measured when recommendations are generated: days since the repository's last
  known push (or the snapshot's days aged since capture) and the label under the current
  thresholds. A repository whose refresh keeps failing no longer reads "pushed today" weeks
  later, and a threshold change applies before the next refresh. The score, the activity reason
  and the activity filter use the same label; stored snapshots are unchanged (MAT-1, MAT-5).
- An unknown activity count is never treated as 0: pushed 5 days ago with an unknown commit
  count and no merged pull requests is moderately active, not low activity (MAT-4).
- "Appears in N of your repositories" counts only repositories you own, not ones you contributed
  to (MAT-2).
- The skill reason no longer names technologies that added nothing to the score (weight 0);
  the value is unchanged (MAT-3).
- The saved list and the discovery pool show the activity label as of now, and a
  recommendation's "Last push" fact is measured when it was generated, so no page contradicts
  its activity label (CR5-2). The benchmark export measures activity at its `now` (CR5-3).

### Changed

- A test keeps matching's openness flags, activity labels and technology sources in step with
  the configuration validation keys (MAT-7); confidence is read once per technology (MAT-8).

## [0.12.64] - 2026-11-14

Discovery fixes from the review sweep (`openspec/changes/archive/2026-11-14-services-discovery-review-fixes/`;
spec `repository-discovery`; `Bug_Backlog.md` batch 59, DSC-1…DSC-8, DSC-3 a false positive).
No scoring or configuration change, no migration. OpenAPI stays `1.0.0`; baselines unchanged
(benchmarks store their candidates). DSC-1, DSC-2 and DSC-4 change which search requests a run
makes or which rank a discovery record holds, so a developer's pool can differ after the next
run. One `/simplify` (`Bug_Backlog.md` batch 61, SIM4-1…SIM4-8) and one fix-diff `/code-review` (batch 62, CR5-1…CR5-8) over the combined 0.12.64–0.12.65 code, fixed before release.

### Fixed

- A topic that recurs across your own repositories is searched again when the budget cuts the
  skill or interest query for the same topic: only a planned query covers a topic (DSC-1).
- When a retried discovery run finds a repository in two star bands through one query, the
  record keeps the better rank. "This run" is the run's recorded search start, not the
  attempt's clock (DSC-2).
- Leftover budget slots go to the strategies with the largest remainder of their share, ties in
  strategy order, so non-default shares are respected. The default split is unchanged (DSC-4).
- `discovery_report --since` also counts runs that were cancelled before they started (window
  on start, or creation). Runs that finished no search request are counted on their own line
  (`runs_without_search` in the JSON), apart from runs from before the yield was recorded (DSC-5,
  CR5-4).
- A topic counted as covered in one allocation round is searched again when a later round cuts
  its query: the plan repeats until the covered topics are the planned ones (CR5-1).

### Changed

- `discovery_report` reads only the three metadata keys it needs (DSC-6).
- The pre-filter reads a stored repository's dependencies only when no other rule rejected it
  (DSC-7); the search step's not-code check is `filters.stored_result_not_code` (DSC-8).

## [0.12.63] - 2026-11-12

Issue analysis fixes from the review sweep (`openspec/changes/archive/2026-11-12-services-issues-review-fixes/`;
specs `issue-analysis`, `issue-ingestion`; `Bug_Backlog.md` batch 57). `ISSUE_TAXONOMY_VERSION`
2026.11.1: stored issues are re-analyzed on their next fetch. No migration. OpenAPI stays `1.0.0`;
baselines unchanged. One `/simplify` and one fix-diff `/code-review` over the combined
0.12.62–0.12.63 code (`Bug_Backlog.md` batch 58, CR4-1…CR4-10), fixed before release.

### Fixed

- Hyphen-scoped labels such as `type-bug`, `C-feature-request` and `E-easy` are understood: a
  first word from a fixed list of scope words is read as a scope (ISV-1).
- Priority and severity labels (`Priority: Medium`, `severity: trivial`) no longer vote on
  difficulty, so a good first issue with a priority label is no longer `unknown`. Only unscoped
  labels and difficulty scopes (`difficulty:`, `level/`, `E-`) vote (ISV-2).
- A label's scope word is no longer a technology: `C-bug` no longer means the C language (ISV-3,
  in part: `spring cleaning` still matches Spring).
- Template comments in an issue body no longer add technologies, also when they contain `>` or
  are never closed (ISV-4).
- A pasted log or stack trace in a fenced code block no longer makes a short report count as a
  long description (ISV-6).
- The stored issue body drops HTML comments before it is capped, so a long issue template no
  longer pushes the report out (ISV-7).
- Multi-word difficulty scopes (`Skill Level: Easy`, `skill-level-easy`) vote again; `C-API`,
  `c extension`, `.NET`, `Rust: async` and `go/rust` keep their technologies; `e-commerce` is
  not scoped (CR4-1…CR4-4).
- A line starting with inline triple backticks no longer hides the rest of an issue body or
  README section (CR4-5).
- A refresh without metadata stores a rename seen by its identity check and no longer asks the
  name twice; a sign-in with a NUL in the GitHub name no longer fails; a batch of repository
  upserts locks name holders in GitHub ID order, so a sync and a discovery run cannot deadlock
  (CR4-6…CR4-8).

### Changed

- Startup checks (core.E040) refuse a `several_technologies` equal to `many_technologies` (the
  technology count could never vote intermediate) and a `long_body` at or above
  `ISSUE_BODY_MAX_CHARS` (the length could never vote advanced) (ISV-5, ISV-7).
- An `unknown` contribution type records the taxonomy version in its evidence (ISV-8).
- One cached label parser serves categories, difficulty votes and technologies; the README
  parser and issue difficulty share one code-fence rule (ISV-10).

## [0.12.62] - 2026-11-12

Repository service fixes from the review sweep, the first module of the low group
(`openspec/changes/archive/2026-11-12-services-repositories-review-fixes/`; specs
`github-data-sync`, `repository-analysis`, `repository-discovery`; `Bug_Backlog.md` batch 56).
One index-only migration (`repositories.0010`). OpenAPI stays `1.0.0`; baselines unchanged.
`/simplify` and the fix-diff `/code-review` ran over the combined 0.12.62–0.12.63 code (see
0.12.63).

### Fixed

- A NUL character or a broken Unicode character in GitHub text (a README, an issue, a label, a
  search result's description, the profile README) no longer makes the database write fail.
  Before, one such repository failed every discovery job whose pool held it, and its refreshes
  failed forever. The GitHub client now removes NUL characters and replaces unpaired surrogates
  in everything it returns (RS-2).
- A refresh that skips metadata first checks that GitHub still has the same repository under
  the stored name. A repository renamed away, whose old name a new repository took, no longer
  gets that repository's issues or README stored under it (RS-1).
- Queuing the refresh of a repository that gave up its name no longer fails a sync, search or
  analysis whose data was already saved when the broker refuses the task; the refused
  repository is no longer marked as queued (RS-3).
- An eligibility change made by discovery's pool step is stamped with the current time, so
  other developers' recommendations notice it (RS-5).
- A stored repository whose name differs only in letter case from a new repository's name now
  gives the name up (RS-6). A new index keeps the case-insensitive lookup fast.
- An analysis that lost its claim to another worker reports itself skipped, not failed (RS-7).

### Changed

- A repository's good-first-issue and help-wanted flags use the same label rule as issue
  analysis, so scoped labels (`type: good first issue`) and aliases (`contributions welcome`)
  count for the openness signal. Stored flags change on each repository's next community refresh
  (RS-8).
- The staleness sweep reads only the fields it needs and updates in groups (RS-9); name release
  locks rows in GitHub ID order (RS-10).

## [0.12.61] - 2026-11-12

Public-release preparation (`Bug_Backlog.md` batch 55, `ideas.md` §5). Documentation and
repository hygiene only: no app, backend, API or ranking change. The git history was checked
again before the repository goes public: no real secrets, no local data, no-reply commit emails.

### Added

- `CONTRIBUTING.md`: setup, where code goes, the checks to run, dependency and pull request rules
  for outside contributors (linked from the README).

### Removed

- The version compare links at the end of this file: they stopped at 0.10.0 and pointed at git
  tags that were never created, so every one returned 404 (PUB-1).

### Changed

- `.gitignore` also ignores private keys and certificates (`*.pem`, `*.key`, `*.p12`, `*.pfx`)
  and `.envrc`, so a credential file cannot be committed by accident once the repository is
  public.

## [0.12.60] - 2026-11-06

CI fixes from the review sweep (`openspec/changes/archive/2026-11-06-ci-review-fixes/`; spec
delta to `developer-tooling`; `Bug_Backlog.md` batch 49). CI and developer tooling only: no app,
backend or API change, no ranking change. One `/simplify` over the combined 0.12.58–0.12.60 code
(batch 53) and one fix-diff `/code-review` (batch 54), both applied before commit.
`/security-review` of `.github/workflows/` found nothing. This closes the medium group of the
review sweep.

### Fixed

- CI could pass on a Python resolution that was never committed: every `uv sync` is now
  `--locked` and `UV_LOCKED=1` covers `uv run`, so a `pyproject.toml` change without `uv lock`
  fails (CI-1). The `check-version.mjs` comment no longer claims `--frozen` rejects stale locks.
- The built-index Content Security Policy test was always skipped in CI; the frontend job now
  builds before it tests, and the separate type check is gone (the build type-checks) (CI-2,
  CI-10).
- The API drift check now also fails on untracked files under `apps/frontend/src/api` (CI-3).
- A hung browser test lost its Playwright report; the step has its own 20-minute limit and the
  report plus traces (`test-results/`) upload on failure or cancellation (CI-7).

### Changed

- The OpenAPI type generator comes from its own locked tree, `apps/frontend/tools/api-types/`
  (`openapi-typescript` 7.13.0 with TypeScript 5.9.3; the app's TypeScript 6 is outside its peer
  range), instead of `npx --yes`. `npm run setup` installs it, CI installs it with `npm ci`, and
  `npm run audit:deps` audits it as a third npm tree (CI-4).
- Every GitHub Action is pinned to a full commit SHA with its version as a comment;
  `.github/dependabot.yml` proposes updates weekly (CI-5). Every checkout sets
  `persist-credentials: false` (CI-6).
- New CI job `scripts-windows` runs `npm run test:scripts` on `windows-latest` (CI-8).
- The Playwright browser cache is keyed on the installed Playwright version, not the whole
  frontend lockfile (CI-9).
- `/simplify` (batch 53): `NPM_TREES` in `scripts/env.mjs` is the one list of npm trees for
  setup and the audit (a test checks lockfiles and `ci.yml`); the Windows job installs nothing;
  the built-index CSP test fails in CI when the build is missing; the Redis runner has one
  failure exit.
- Fix-diff `/code-review` (batch 54): on POSIX, `npm run stop` and a runner's force kill now
  end the whole process tree, also for processes that lead no process group (path-matched
  Celery or Django, the e2e backend's server under `uv`); `npm run stop` no longer counts a
  python whose arguments mention Celery (`pytest -k celery`) as the worker; a CSP violation
  logged twice no longer fails the canary; the env test lists every lockfile through git and
  matches `ci.yml` entries exactly; the built-index CSP test is forced only by `CI=true`; docs
  no longer promise a message for a second `--ui` run.

## [0.12.59] - 2026-11-03

Runner script fixes from the review sweep
(`openspec/changes/archive/2026-11-03-scripts-review-fixes/`; spec delta to `developer-tooling`;
`Bug_Backlog.md` batch 48). Developer tooling only: no app, backend or API change, no ranking
change. `/simplify` and the fix-diff `/code-review` were skipped (owner). `/security-review` of
`scripts/` found nothing. SCR-5 accepted.

### Fixed

- `npm run stop` could kill a sibling checkout whose folder name starts with this one's
  (`ContribFinder-v2`) and any Vitest or pytest process whose command line mentioned Vite or
  Celery; it now matches the repository folder as a whole and only the stack's own programs
  (SCR-1, SCR-2).
- On Windows, processes whose command line could not be read (started elevated) were not
  listed, so their records were deleted as stale; they are now left running, their records kept,
  and `npm run stop` says so (SCR-3).
- The Redis runner exited 0 when Redis never came up, so the stack kept running without it, and
  crashed with a stack trace when the WSL keep-alive could not start; both now exit 1 with a
  message and stop the stack (SCR-6, SCR-7).
- On POSIX, a runner child started without its own process group (the e2e backend) ignored a
  stop signal (SCR-4).
- An IPv6 `REDIS_URL` (`redis://[::1]:6379/1`) was not recognized as local (SCR-8).
- The uv lookup preferred an old Python's uv (`Python39` before `Python313`) (SCR-9).

### Changed

- `setup.mjs`, `backend.mjs` and `manage.mjs` take `root` from `env.mjs` (SCR-10).

## [0.12.58] - 2026-11-03

Browser-test tooling fixes from the review sweep
(`openspec/changes/archive/2026-11-03-e2e-config-review-fixes/`; no spec change, `skip_specs`;
`Bug_Backlog.md` batch 47). Test tooling only: no app, backend or API change, no ranking change.
`/simplify` and the fix-diff `/code-review` were skipped (owner). `/security-review` of
`frontend/e2e/` and its configs found nothing. E2EC-2, E2EC-5 accepted.

### Fixed

- A data-changing browser test run with `--repeat-each` reused the already-changed seeded user,
  and CLI `--retries` failed with "attempt N"; both now fail at sign-in naming the cause and the
  supported way (`RETRIES` in `playwright.config.ts`, a fresh `npm run e2e`) (E2EC-1).
- The `E2E_DEV_SERVER=1` dev server listened on every interface; it now uses localhost only, like
  the preview (E2EC-3).
- Vitest's `exclude` replaced Vitest's default list; it now extends it and skips `dist-e2e/`
  (E2EC-6).
- The CSP canary failed on a duplicate console entry; it now checks every entry names `img-src`
  (E2EC-7).

### Changed

- The fixture comment says read-only seeded users may record views (E2EC-4). README "End-to-end
  tests" lists the unsupported Playwright flags.

## [0.12.57] - 2026-11-03

Issue detail fixes from the review sweep
(`openspec/changes/archive/2026-11-03-issue-detail-review-fixes/`; spec deltas to
`issue-matching`, `recommendation-feedback`, `web-client`; `Bug_Backlog.md` batch 46). Frontend
plus one backend test: no migration, OpenAPI stays `1.0.0`, no ranking change. `/simplify` and
the fix-diff `/code-review` were skipped (owner). `/security-review` of `features/issues/` found
nothing. FI-5, FI-8, FI-9 false positives. One `/simplify` (batch 51) and one fix-diff
`/code-review` (batch 52, all fixed) over the combined 0.12.55–0.12.57 code ran before release;
their fixes are included here.

### Changed

- Opening a repository or an issue on GitHub with the middle mouse button now records
  `opened_repository` / `opened_issue` like a click; `feedback_report` counts more open events
  from this release on (FI-6).
- The issue page names the category of the label that decided the contribution type ("From a
  documentation label"), never a label the issue may not carry (FI-1).
- One `Fact` component and one date formatter for the detail pages, the saved list and skill
  evidence; recommendation detail values are now right-aligned like the issue page's (FI-10).

### Fixed

- A failed background refetch replaced the issue being read with "no longer among your relevant
  issues"; it now stays shown, and only a 404 ends the page (FI-3).
- An unknown difficulty signal showed its raw key, and malformed evidence could crash the page;
  a backend test keeps the page's wordings equal to the signals the classifier writes (FI-2,
  FI-4).
- An issue that mentions no technology said "Not enough evidence"; it now says "No technologies
  mentioned" (FI-7).
- The recommendation detail page, the saved and hidden lists, the discovery card and the
  recommendation list also replaced shown content after one failed refetch; they now keep it,
  through one shared `Loaded` component where the page shape allows (CR-1, CR-2, CR-5).
- "From a enhancement label" now reads "From an enhancement label", and malformed difficulty
  evidence no longer crashes the issue page (CR-3, CR-4).
- The sign-in page shows "Loading…" while the identity loads instead of a blank page, and a
  failed navigation to sign-in keeps the identity, so the next 401 still shows the
  session-ended notice (CR-6, CR-7).

## [0.12.56] - 2026-11-03

Route fixes from the review sweep (`openspec/changes/archive/2026-11-03-routes-review-fixes/`;
spec delta to `web-client`; `Bug_Backlog.md` batch 45). Frontend only: no migration, OpenAPI
stays `1.0.0`, no ranking change. `/simplify` and the fix-diff `/code-review` were skipped
(owner). `/security-review` of `frontend/src/routes/` found nothing.

### Fixed

- One failed sync status poll replaced the dashboard or onboarding with "Could not load…"; a
  failed developer profile refetch replaced the summary, skills, interests and languages. Shown
  data now stays until a later fetch succeeds (ROUTE-2, ROUTE-3).
- Skills, interests or repositories that failed to load looked like an empty list; they now say
  they could not be loaded (ROUTE-4).
- Back to the first page never refreshed the data versions, and a state-only navigation (after a
  dismiss) refreshed them twice (ROUTE-1, ROUTE-7).
- Onboarding showed no wait for a sync cooldown, and the dashboard's "in N minutes" went stale;
  both now say from what time a refresh is possible (ROUTE-5, ROUTE-6).
- A signed-in user opening `/` or an unknown path briefly saw "Continue with GitHub" (ROUTE-10;
  a not-found page is left to the interface revamp).

### Changed

- The signed-in identity reaches the pages through the route outlet (`useSignedInUser`); the
  impossible "no identity" branches are gone (ROUTE-8). Onboarding redirects to the dashboard
  once (ROUTE-9).

## [0.12.55] - 2026-11-03

Query client and session fixes from the review sweep
(`openspec/changes/archive/2026-11-03-app-review-fixes/`; spec delta to `web-client`;
`Bug_Backlog.md` batch 44). Frontend only: no migration, OpenAPI stays `1.0.0`, no ranking
change. `/simplify` and the fix-diff `/code-review` were skipped (owner). `/security-review` of
`frontend/src/app/` found nothing. APP-7 and APP-8 accepted.

### Fixed

- Deleting GitHub data no longer counts the vanished sync job as a finished one, which asked for
  the deleted data again (APP-1).
- A status fetch that is cancelled (by a refetch of the same status, or by leaving the signed-in
  pages) no longer refreshes; status requests now pass the query's abort signal, so a cancelled
  and restarted fetch refreshes once and sign-out stops them (APP-2, APP-3).
- Starting a sync while a status fetch was in flight could replace the new job with the older
  answer and stop polling, so its finish went unseen (APP-4).
- A 401 that arrived while a sign-out was pending was dropped when the sign-out then failed,
  leaving the user on signed-in pages with a dead session (APP-5).
- If going to the sign-in page failed, later 401s were ignored (APP-6).

### Changed

- The data versions refresh invalidates every changed area in one pass (APP-10).
- A test fails when a `['profile', ...]` query key is not covered by a data versions area
  (APP-9).

## [0.12.54] - 2026-11-03

Profiling fixes from the review sweep
(`openspec/changes/archive/2026-11-03-profiling-review-fixes/`; spec delta to `skill-detection`;
`Bug_Backlog.md` batch 43). No migration. OpenAPI stays `1.0.0`; baselines unchanged.
`TAXONOMY_VERSION` 2026.11.1: stored profiles change on their next analysis
(`npm run manage -- reanalyze_profiles` applies it at once). One `/simplify` and one fix-diff
`/code-review` over the combined 0.12.51–0.12.54 code (`Bug_Backlog.md` batch 50, FD2-1…FD2-9)
ran before release; their fixes are included here and in 0.12.53. `/security-review` of
`services/profiling/` found nothing. Specs "README skill evidence" and "Experience level" were
edited directly after the review.

### Changed

- Contributions to forked repositories no longer give skill or interest evidence, nor count
  toward the experience level (PROF-8, FD2-5, owner decision).
- Analyses no longer rewrite the shared skill and interest catalog rows on every run; only
  missing or renamed rows are written (PROF-9).

### Fixed

- Text with look-alike letters (dotless `ı`, long `ſ`, Kelvin sign) crashed profile analysis,
  recommendation generation and issue analysis; matching now case-folds and never raises
  (PROF-1).
- README: commented-out sections and badges gave skills or interests (also after an
  unterminated `<!--`, which GitHub hides to the end); `#` comments in code blocks, including
  nested longer fences, were read as headings (inventing or cutting sections); `## C#` lost its
  `#` (PROF-2, PROF-3, PROF-7, FD2-2, FD2-3).
- Manifests: a pyproject string where a list belongs was read one letter at a time; a
  `name @ URL` requirement lost its name; commented-out `pom.xml` and Gradle dependencies
  counted, while globs and URLs inside Gradle strings are kept (PROF-4, PROF-5, PROF-6, FD2-1).
- Issue difficulty and profile READMEs now strip HTML comments the same way (FD2-3).

## [0.12.53] - 2026-11-03

Feedback fixes from the review sweep
(`openspec/changes/archive/2026-11-03-feedback-review-fixes/`; no spec change;
`Bug_Backlog.md` batch 42). No migration. OpenAPI stays `1.0.0`; baselines unchanged.
The fix-diff review of 0.12.51–0.12.54 (batch 50) is folded in; spec "Recording feedback" was
edited directly for FD2-6. `/security-review` of `feedback/` found nothing.

### Changed

- Feedback, save and dismiss requests read the recommendation once: the ownership check loads
  only its id and repository (FB-5).
- An `opened_issue` for an issue closed or dropped since the page loaded stores no event and is
  not an error, like a recommendation gone meanwhile; only an issue of another repository is
  rejected with 400 (FD2-6, owner decision).

### Fixed

- An `opened_issue` event could be stored for an issue a concurrent generation had just dropped:
  relevance is now checked in the service under the recommendation lock (FB-1).
- Unsave on a card or the detail page failed with 404 once a background generation had dropped
  the recommendation, and the project stayed saved; it now unsaves by repository
  (`DELETE /api/v1/saved/{repository_id}`) (FB-3).
- Dismissing a project whose repository was deleted meanwhile (delete-data) answered 500; it is
  now 404 (FD2-4).

## [0.12.52] - 2026-11-03

Recommendation fixes from the review sweep
(`openspec/changes/archive/2026-11-03-recommendations-review-fixes/`; no spec change;
`Bug_Backlog.md` batch 41, SIM-8). No migration. OpenAPI stays `1.0.0`; baselines unchanged.
`/simplify` and the fix-diff `/code-review` were skipped by the owner. `/security-review` of
`recommendations/` found nothing.

### Changed

- The recommendation and feedback admins are view-only: staff can no longer delete
  recommendations (with their reasons and issues), saves, dismissals or feedback history;
  changelists load related rows in one query (REC-1, REC-6, SIM-8).
- Scoring configurations cannot be added or deleted in the admin; seed migrations store them
  and only the description stays editable (REC-2).
- The recommendation status endpoint runs one query fewer (REC-9).

### Fixed

- A deleted scoring configuration can no longer be saved back with other numbers (REC-4).
- `evaluate_ranking --top-n` below 1 is refused instead of using the default or dropping the
  last repositories (REC-3).
- `benchmark_sheet` and `import_judgments` report a malformed export as an error instead of a
  traceback, and `benchmark_sheet` writes nothing then (REC-7).
- The README excerpt keeps a word that ends exactly at its limit, keeps `_` and `~` inside
  words and paths, and shows HTML entities as their characters (REC-8, REC-10).

## [0.12.51] - 2026-11-03

Issue data fixes from the review sweep
(`openspec/changes/archive/2026-11-03-issues-review-fixes/`; no spec change;
`Bug_Backlog.md` batch 40). No migration. OpenAPI stays `1.0.0`; baselines unchanged.
`/simplify` and the fix-diff `/code-review` were skipped by the owner. `/security-review` of
`issues/` found nothing.

### Changed

- Both issue admins are view-only: staff can no longer delete an issue (with its cascade into
  every developer's recommended issues) or a recommended issue, which left the difficulty and
  contribution-type filters counting issues that were gone (ISS-1, ISS-2, ISS-8).
- The issue changelist loads repositories in one query (ISS-5).
- The issue detail's technology source choices come from the detector's constants; the API is
  unchanged (ISS-7).

### Accepted

- The issue detail may show skills matched against the current profile, or an issue assigned,
  locked or transferred since generation, until the freshness sweep regenerates (ISS-3, ISS-4,
  ISS-6).

## [0.12.50] - 2026-11-02

Repository data fixes from the review sweep
(`openspec/changes/archive/2026-11-02-repositories-review-fixes/`; spec `repository-analysis`;
`Bug_Backlog.md` batch 38). No migration. OpenAPI stays `1.0.0`; baselines unchanged.
One `/simplify` over the combined 0.12.48–0.12.50 diff (`Bug_Backlog.md` batch 39); the
fix-diff `/code-review` was skipped by the owner.

### Changed

- Every repository admin is view-only: staff can no longer change a repository's lifecycle or
  eligibility, edit its languages, topics or dependencies, or delete repositories, candidates
  or snapshots with their cascade; lists load related rows in one query (REPO-5, REPO-6,
  REPO-7).
- A refresh that schedules a retry keeps its repository marked as queued until the retry has
  had its chance (REPO-4).
- One view-only admin base (`core.admin.ViewOnlyAdmin`) for the jobs, developer and repository
  admins; shared admin test helpers; the stalled notice has one text (batch 39, `/simplify`).

### Fixed

- A repository refresh that fails with an unexpected error logs its traceback (REPO-1).
- With tasks running inline, a rate-limited or transient refresh fails once instead of
  retrying inline without backoff (REPO-2).
- A refresh the broker refuses no longer leaves its repository marked as queued; the rest of
  the batch is still sent (REPO-3). Each refused send is logged with its traceback.

## [0.12.49] - 2026-11-02

Developer profile fixes from the review sweep
(`openspec/changes/archive/2026-11-02-developers-review-fixes/`; no spec change;
`Bug_Backlog.md` batch 37). Migration `developers.0002` (ordering only, no SQL). OpenAPI stays
`1.0.0`; baselines unchanged. One `/simplify` over the combined 0.12.48–0.12.50 diff
(`Bug_Backlog.md` batch 39); the fix-diff `/code-review` was skipped by the owner.

### Changed

- The developer admins are view-only: no add, change or delete, so a catalog skill or a profile
  can no longer be deleted with its cascade from the admin; lists load related rows in one
  query, and interest evidence is shown (DEV-1, DEV-2, DEV-9).
- `reanalyze_profiles` skips deactivated users and users whose sync is running (reported as
  "syncing"); `--user` names an inactive user (DEV-4, DEV-5).
- A test fails once the skill or interest catalog outgrows one profile page (DEV-6).

### Fixed

- Evidence without a date is listed after dated evidence, not before the newest (DEV-3).
- Skills and interests with equal scores keep one order across pages (DEV-7).
- The interests list returns no rows during schema generation, like every other list (DEV-8).

## [0.12.48] - 2026-11-02

Job fixes from the review sweep (`openspec/changes/archive/2026-11-02-jobs-review-fixes/`;
specs `sync-jobs`, `web-client`; `Bug_Backlog.md` batch 36). Migration `jobs.0007` (index
only). OpenAPI stays `1.0.0` (additive field); baselines unchanged. One `/simplify` over the
combined 0.12.48–0.12.50 diff (`Bug_Backlog.md` batch 39); the fix-diff `/code-review` was
skipped by the owner.

### Added

- Every job the API returns carries `stalled`: RUNNING with no heartbeat for
  `SYNC_STALE_AFTER_SECONDS`, the rule recovery already uses. Reading a status changes nothing
  (JOB-3).
- The dashboard and onboarding say when background work stopped and resumes automatically, and
  let you start a sync over a stalled one (Refresh, Try again); the stalled job is still polled
  (JOB-3).

### Changed

- The jobs admin is view-only: no add, change or delete, and its list loads users in one query
  (JOB-1, JOB-2, JOB-5).
- Partial index `syncjob_active_updated_idx` for the recovery scan, and recovery runs that
  waited a whole interval expire (JOB-8, in part).
- The active statuses have one definition (`jobs.models.ACTIVE_STATUSES`), used by the unique
  constraint too; the unused `SyncJob.is_active` is removed (JOB-4, JOB-6, JOB-7).

### Fixed

- Adding a job in the admin no longer fails with a 500, and saving a job there can no longer
  overwrite a worker's update or make a dead job look alive (JOB-1, JOB-2).

## [0.12.47] - 2026-11-02

Sign-in and sign-out fixes from the review sweep
(`openspec/changes/archive/2026-11-02-auth-review-fixes/`; spec `web-client`; `Bug_Backlog.md`
batch 34). Frontend only; no migration. OpenAPI stays `1.0.0`; baselines unchanged. The
fix-diff review is batch 35 (see 0.12.45).

### Changed

- Log out, disconnect and account deletion leave the signed-in app through one path: nothing is
  refetched on the way and no user data stays cached afterwards (AUTH-4, AUTH-5).
- Only one account action (log out, disconnect, delete data, delete account) runs at a time;
  the others are disabled meanwhile (AUTH-8).

### Fixed

- A sign-in error code such as `__proto__` in the link no longer breaks the sign-in page
  (AUTH-1).
- A failed background refresh of the signed-in identity keeps the pages instead of replacing
  them with an error (AUTH-2); a 401 on that refresh shows the session-ended notice (AUTH-3).
- Deleting GitHub data leaves the dashboard before its data is removed, and navigates to
  onboarding from the action itself (AUTH-6, AUTH-7).
- The disconnect test answers `revocation: 'queued'`, as the backend does (AUTH-9).

## [0.12.46] - 2026-11-02

API client fixes from the review sweep (`openspec/changes/archive/2026-11-02-api-client-review-fixes/`;
spec `web-client`; `Bug_Backlog.md` batch 33). Frontend only; no migration. OpenAPI stays `1.0.0`;
baselines unchanged. Fix-diff review: batch 35 (see 0.12.45).

### Changed

- Every failed API call is an `ApiError` with a status and a code: `network_error` (status 0) when
  no response arrived, `invalid_response` when a success body is not JSON (API-1).
- Only `network_error` and 5xx are retried; an unreadable success body or a bug in a query
  function is not (API-1).

### Added

- `apiFetch(path, { json })` sends a JSON body with its `Content-Type`; the feedback calls use it
  (API-9).

### Fixed

- An error without the JSON envelope keeps its `Retry-After` wait (API-2).
- A failed CSRF token request reports its own status and code instead of status 0
  `csrf_unavailable` (API-3).
- Concurrent mutations share one CSRF token request (API-4), and a `keepalive` request (feedback
  events) sends it with `keepalive` too (API-5).

## [0.12.45] - 2026-11-02

GitHub service fixes from the review sweep
(`openspec/changes/archive/2026-11-02-github-services-review-fixes/`; spec `github-data-sync`;
`Bug_Backlog.md` batch 32), with the fix-diff review of 0.12.45–0.12.47
(`openspec/changes/archive/2026-11-02-fix-diff-review-fixes/`; spec `github-authentication`;
batch 35). No migration. OpenAPI stays `1.0.0`; baselines unchanged.

### Added

- `GITHUB_ETAG_MAX_BYTES` (default 256 KiB, check `core.E020`): GitHub response bodies larger
  than it are served but not cached, so big READMEs no longer grow Redis (GHS-8).

### Changed

- Contributions observed under two names of one repository (renamed or transferred) are counted
  together (GHS-5).
- A contributed repository that is still observed but unreadable (403, 451) keeps its contributor
  link and previous counts; a 404 or a repository the user now owns still drops it (GHS-6).

### Fixed

- The sync stores owned repositories in GitHub ID order, the order of every bulk repository lock,
  so it cannot deadlock with another user's discovery (GHS-1).
- Languages and dependencies are replaced under the repository row lock, so a concurrent analysis
  no longer makes the sync fail (GHS-2).
- A next-page link is followed only to the API origin (scheme, host and port), like a redirect;
  one Link-header parser serves pagination and counts (GHS-3, GHS-10).
- A rate-limited (403/429) token revocation is retried instead of failing for good, also
  when GitHub asks for a wait longer than `GITHUB_MAX_RETRY_DELAY` (GHS-4, FD-1).
- `httpx` decoding and URL errors become GitHub errors (transient or client), never an
  unclassified failure (GHS-7).
- A retried dependencies step reads the repositories its first attempt chose (GHS-9).
- One date parser (`client.parse_dt`) and one `API_VERSION`; the status → error mapping is
  `errors.error_for_response`, shared by the client and the revocation (GHS-10, FD-8).

## [0.12.44] - 2026-10-31

Service fixes from the review sweep (`openspec/changes/archive/2026-10-31-services-review-fixes/`;
specs `recommendation-engine`, `sync-jobs`; `Bug_Backlog.md` batch 31). Migration
`feedback.0006`. OpenAPI stays `1.0.0`; baselines unchanged.

### Changed

- A generation requested while one runs now follows it also when that run fails (SVC-5).
- The `recommendations` data version also moves when the user saves, unsaves, dismisses or
  restores a repository, so another tab refreshes its lists (SVC-9). Partial index
  `feedback_list_change_idx` serves it.

### Fixed

- Account deletion purges the deleted user's cached GitHub responses; every deletion purges once
  more after cancelled workers have stopped (SVC-1, SVC-6 narrowed).
- Feedback events snapshot the recommendation as stored under the lock, and an `opened_issue`
  event for an issue deleted meanwhile is skipped instead of failing (SVC-2, SVC-7).
- Orphan cleanup locks repositories in GitHub ID order before deciding, and counts from the
  delete (SVC-3, SVC-10, SVC-11).
- Ending jobs locks them in pk order; a job deleted right after its claim is not claimed (SVC-4,
  SVC-8).

## [0.12.43] - 2026-10-31

Browser-test seed fixes from the review sweep
(`openspec/changes/archive/2026-10-31-e2e-seed-review-fixes/`; spec `web-client`;
`Bug_Backlog.md` batch 30). No migration. OpenAPI stays `1.0.0`; baselines unchanged.

### Fixed

- The browser-test seed refuses any database but `contribfinder_e2e`, besides needing the
  end-to-end settings (SEED-1).
- A retried browser test that changes data starts from seeded data: save, dismiss and delete-data
  each own a user, seeded once per attempt (`--attempts`, from Playwright's `RETRIES`), and the
  sessions file says which users are per attempt. Retry copies are named `<user>-retry<n>`
  (SEED-2, SEED-11…SEED-13, SEED-16).
- The seed also clears sessions and audit entries, finishes each job in one fenced write and
  fails if it cannot, and its snapshots agree with the repositories' push times
  (SEED-5, SEED-7, SEED-10).
- `CREATE DATABASE` quotes the name; jobs are built by one `services.jobs.new_job`;
  `make_issue` returns `Issue`; `add_candidate` keeps a candidate as recent as its records and
  first found no later than them (SEED-3, SEED-4, SEED-8, SEED-9, SEED-15, SEED-17, SEED-19).
- A backend test seeds, resets and seeds again (SEED-6).

## [0.12.42] - 2026-10-31

GitHub app fixes from the review sweep (`openspec/changes/archive/2026-10-31-github-review-fixes/`;
specs `data-controls`, `sync-jobs`; `Bug_Backlog.md` batch 29). No migration. OpenAPI stays
`1.0.0`; baselines unchanged.

### Fixed

- Deleting GitHub data and recording it happen in one transaction: a failing audit write leaves
  the data in place (`services/accounts.delete_github_data`) (GH-3).
- The GitHub account and profile admins have no add or delete: a connection is removed by
  disconnect (which revokes the token), data by delete-data. The admin therefore also refuses to
  delete a user who has GitHub data; account deletion is the path (GH-2, GH-9).
- Without a worker (eager mode) a revocation is tried once and a failure recorded, never retried
  inline inside the request; the rule is shared with tracked jobs
  (`services/github/retry.attempt_number`) (GH-5, supersedes ACC-17's acceptance).
- A revocation failing on an unexpected error logs its traceback (never the token); GitHub
  refusing does not (GH-1, GH-10).
- The dashboard lists every synced repository: it follows `next`, and the repository list's page
  cap follows `GITHUB_SYNC_MAX_REPOS` (never below 100) (GH-4, GH-13).
- The repository list no longer runs `SELECT DISTINCT`; both GitHub admins load users in one
  query (GH-7, GH-8).

## [0.12.41] - 2026-10-30

Account fixes from the review sweep (`openspec/changes/archive/2026-10-30-accounts-review-fixes/`;
specs `github-authentication`, `data-controls`; `Bug_Backlog.md` batch 28). Migrations
`accounts.0004`, `accounts.0005`. OpenAPI stays `1.0.0`; baselines unchanged.

### Changed

- Disconnect and account deletion no longer wait on GitHub: the stored token is deleted at once
  and the revocation runs in the background after the transaction commits (`github.revoke_later`,
  token encrypted only). Temporary failures are retried by the shared GitHub retry policy; a final
  failure is audited (`github_revocation_failed`, no token). A user who signs in again before
  the revocation runs keeps the new token: only the old one is revoked. A broker outage never
  stops a disconnect, an account deletion or a sign-in. The disconnect response's `revocation` is
  now `queued` (or `not_connected`); `revoked` and `failed` stay in the schema but are no longer
  returned (ACC-9, ACC-11…ACC-20).

### Fixed

- A deactivated user can no longer sign in with GitHub: nothing is stored, no sync starts, the
  user's GitHub grant is revoked in the background, and the refusal is audited (ACC-1, ACC-16).
- An unexpected error after the GitHub code exchange redirects to the sign-in error page
  (`failed`) and is audited, instead of showing a raw JSON 500 (ACC-2).
- Account deletion records its audit entry, anonymizes the trail and deletes the user in one
  transaction (ACC-3).
- Audit entries are read-only in the admin: no adding or deleting (ACC-5).
- The sign-in callback is no longer throttled, so a busy network never shows a raw 429 page
  there (the start of sign-in stays throttled) (ACC-6).
- Expired sessions are removed daily (`accounts.clear_expired_sessions`) (ACC-7).
- The audit admin list loads users in one query; `AuditEvent` has an index on `-created_at`
  (ACC-10). Migrations `accounts.0004` (index), `accounts.0005` (audit action choice).

### Changed (internal)

- Disconnect and account deletion live in `services/accounts.py` (`disconnect_github`,
  `delete_account`, sharing `_leave`); the views only call them and end the session (ACC-8).
  ACC-4 accepted.
- `/simplify` of the 0.12.40–0.12.41 diff: the deactivated-user check moved into
  `link_github_account` (`AccountInactive`, one query fewer per sign-in); tests reuse the shared
  helpers. Two broader ideas went to `ideas.md` §15.

## [0.12.40] - 2026-10-30

Core fixes from the review sweep (`openspec/changes/archive/2026-10-30-core-review-fixes/`; spec
`api-platform` ("Configuration validated at startup"); `Bug_Backlog.md` batch 27). No API,
model, migration or frontend change; baselines unchanged.

### Fixed

- The production startup gate ignores checks listed in `SILENCED_SYSTEM_CHECKS` at every level,
  as `manage.py check` does, and also runs Django's deployment checks (their warnings are logged,
  never blocking) (CORE-1, CORE-5).
- New startup rules: `NUM_PROXIES` must be a non-negative integer (a negative count broke or
  spoofed client-IP detection), `DISCOVERY_QUERY_SHARES` must add up to more than 0, Content
  Security Policy values may not contain control characters (Django refused them on every
  response), and `REPO_STALE_AFTER` values must be positive (CORE-2, CORE-4, CORE-6, CORE-8).
- A wrongly typed setting is reported as a configuration error instead of crashing the checks
  (CORE-7). The checks read the discovery strategies and repository parts from the services
  instead of copies (CORE-10).
- The log redaction backstop also masks prefixed names (`GITHUB_CLIENT_SECRET=`,
  `encrypted_access_token=`), session and CSRF cookies, `password`, `secret` and
  `TOKEN_ENCRYPTION_KEYS` values (CORE-3).
- Management commands write JSON through a temporary file swapped in atomically: an interrupted
  write keeps the old file, and unserializable data fails before any file is touched (CORE-9).

## [0.12.39] - 2026-10-30

Settings fixes from the review sweep (`openspec/changes/archive/2026-10-30-config-review-fixes/`,
no spec change, `skip_specs`; `Bug_Backlog.md` batch 26), plus files for publishing the
repository. No API, model, migration or frontend change; baselines unchanged.

### Added

- `LICENSE` (MIT) and `SECURITY.md` (report vulnerabilities privately through GitHub's private
  vulnerability reporting; scope, supported versions, how tokens are handled).

### Removed

- The two Software Requirements Specification files are no longer tracked (kept locally,
  gitignored); `CLAUDE.md` and `openspec/specs/` hold what was built from them.

### Fixed

- Local tests see CI's settings: the test settings take only `DATABASE_URL` from the repo-root
  `.env` (`DJANGO_READ_DOTENV=DATABASE_URL`, parsed by django-environ in `base.py`), so a
  developer's `REDIS_URL`, `NUM_PROXIES` or `DISCOVERY_*` values no longer change test results
  (CFG-1).
- A Celery publish on a stalled Redis connection no longer hangs the HTTP request: the broker has
  a read/write timeout (`REDIS_SOCKET_TIMEOUT`, at least 2 s for the worker's 1 s BRPOP) and a
  `visibility_timeout` above the longest retry delay (CFG-2, CFG-5, CFG-17).
- Persistent database connections are health-checked, so one dropped by a PostgreSQL restart
  reconnects instead of failing the next query (CFG-3).
- JSON settings name themselves when wrong: `env_json` / `env_mapping` raise
  `ImproperlyConfigured` naming the setting for invalid JSON or a non-object (the eight object
  settings, `DISCOVERY_STAR_BANDS`, `DISCOVERY_EXCLUDED_TOPICS`); a blank value means the default
  (CFG-4, CFG-16).
- An API error with a dict detail keeps a readable message and puts the detail in `details`; a
  list detail becomes the message (CFG-6, CFG-19).
- `LOG_LEVEL` now applies to Django's logger too; SQL (`django.db.backends`) is never logged with
  its parameters, whatever the level (CFG-9, CFG-13).
- `GITHUB_OAUTH_SCOPES` accepts commas as well as spaces (`env_words`) (CFG-10).
- Review of the fix (CFG-11…CFG-20) fixed before release; CFG-7 and CFG-8 accepted.

## [0.12.38] - 2026-10-30

Browser tests on the production build (`openspec/changes/archive/2026-10-30-e2e-production-build/`;
spec `web-client` ("End-to-end coverage of the main flows"); `ideas.md` §14). No app, API,
backend or dependency change; baselines unchanged.

### Changed (internal)

- `npm run e2e` (and CI's `e2e` job) now builds the SPA (`vite build --outDir dist-e2e`) and
  serves it with `vite preview` on :5174, instead of the Vite dev server: the tests run what
  ships, with its Content Security Policy, bundling and lazy chunks. `dist-e2e/` is gitignored
  and a local `dist/` is left alone. `E2E_DEV_SERVER=1` keeps the dev server for local runs
  (no policy); CI never sets it.
- New auto fixture `policyViolations` (`e2e/fixtures.ts`): any Content Security Policy
  violation reported by any page of the test fails it, naming the directive and the blocked
  URL. A canary test (`e2e/policy.spec.ts`) blocks a foreign image and asserts it is recorded,
  so a change in Chromium's wording fails instead of going silent.
- `vite.config.ts` shares one `/api` proxy between the dev server and `vite preview`; the e2e
  preview listens on `localhost` only (`--host localhost`). The build's output shows in the e2e log.
- Review fixes (`Bug_Backlog.md` batch 25): E2E-1, E2E-2, E2E-5, E2E-7; E2E-6 documented.
- `/simplify` (E2E-10…E2E-13): port and output folder written once in `playwright.config.ts`;
  `--host localhost` on the e2e preview command instead of `vite.config.ts`; the fixture yields
  `{ seen, take() }` and the canary takes its expected `img-src` from `CONTENT_SECURITY_POLICY`.
- Local runs: 9 passed in about 45 s on the production build (build under 5 s), 8 passed and
  the canary skipped in about 42 s on the dev server.

## [0.12.37] - 2026-10-30

Route-level id validation (`openspec/changes/archive/2026-10-30-route-id-validation/`; no spec
change, `skip_specs`; `ideas.md` §14). Frontend refactor: same messages and dead ends; the
detail page now remounts when the route moves to another id. No API, backend or dependency
change; baselines unchanged.

### Changed (internal)

- `RouteId` (`src/routes/RouteId.tsx`) validates a detail route's `:id` once with `positiveId`:
  an invalid id gets the route's dead end and no request, a valid one renders the page with a
  plain number, remounted per id (scroll-to-hash and page state reset, as on a full navigation). `/app/recommendations/:id` and `/app/issues/:id` use it.
- `RecommendationDetailPage({ id })` and `IssueDetailPage({ id })` take the id as a prop (no
  `useParams`, no `id ?? 0` sentinel, no invalid-id branch); `useRecommendation` and `useIssue`
  drop their `enabled` guard.
- Tests: a `RouteId` unit test (valid id; a remount when the route moves to another id; `abc`,
  `0`, `1.5`, `0x1f`, `%207` (decoded to ` 7`), unsafe integer) and one `viewed` event per id.
- Review fixes (`Bug_Backlog.md` batch 24): RT-1, RT-2, RT-6 (recorded then as R-1, R-2, R-6).
- `positiveId` moved from `src/lib/utils.ts` into `RouteId.tsx`, its only caller (`/simplify`).

## [0.12.36] - 2026-10-30

Released-name refresh (`openspec/changes/archive/2026-10-29-released-name-refresh/`; spec
`repository-analysis` ("Background refresh"); `ideas.md` §13). No API, model, migration,
setting or scoring-config change; baselines unchanged.

### Changed

- A repository that gives up its name to another GitHub ID (renamed away, or deleted and
  recreated) and is in a developer's pool now has its refresh queued as soon as the storing
  transaction commits (`backlog.queue_released`), instead of waiting for the hourly stale sweep
  and the 15-minute backlog. It drops out of recommendations (`name_released`) for minutes, not
  over an hour. Stamped as queued, so the backlog does not queue it twice; a rolled-back
  transaction queues nothing.
- Holders that are FAILED, already queued or in no pool keep the existing paths. Without app
  client credentials, or when tasks run inline (no worker), nothing is queued: the periodic
  refresh stays the fallback, and storing a repository never runs another repository's analysis.
- Review fixes (`Bug_Backlog.md` batch 23): an analysis that loses the name while fetching
  (`lifecycle.NameChanged`, a `ClaimLost`) queues the holder again instead of leaving it for the
  sweep (L-1); rejected app credentials (`backlog.AUTH_INVALID`) within
  `REPO_REFRESH_RETRY_MINUTES` hold the immediate refresh back (L-2); `queue_batch` and
  `queue_released` share one locked pick (L-4).

## [0.12.35] - 2026-10-28

Labeled-issue fetch (`openspec/changes/archive/2026-10-28-labeled-issue-fetch/`; spec
`issue-ingestion`; `ideas.md` §7). No API, model, migration or scoring-config change;
baselines unchanged (the benchmark stores issues as data).

### Changed

- A repository with more open issues than the fetch budget (`ISSUES_MAX_PAGES`, one page of
  100) now also fetches one page of open issues per entry label, `good first issue` and
  `help wanted` by default (`ISSUES_ENTRY_LABELS`; empty turns it off; check `core.E041`).
  Older entry issues of big repositories are no longer cut off, so their issue fit and relevant
  issues can rise. Two more conditional requests per capped repository; none for smaller ones.
  A failed labeled listing fails the issue fetch and keeps the stored issues.
- Local measurement before release (read-only): 50 of 473 pooled repositories were capped and
  held 84 entry issues; 24 of them gain 550 more (390 updated within the 365-day limit). Stored
  issues change on each repository's next issue refresh (6 h).
- Review fixes (`Bug_Backlog.md` batch 22): label names are trimmed (`good first issue, help
  wanted` in `.env` no longer requests ` help wanted`; `core.E041` refuses surrounding spaces),
  and each labeled request checks for cancellation and renews the analysis claim first.
- Every comma-separated setting (`ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`,
  `TOKEN_ENCRYPTION_KEYS`, `ISSUES_ENTRY_LABELS`) is read trimmed, with empty items dropped:
  `localhost, 127.0.0.1` no longer yields a host " 127.0.0.1" that matches nothing.

## [0.12.34] - 2026-10-28

Dependency audit (`openspec/changes/archive/2026-10-28-dependency-scanning/`; spec
`developer-tooling`; `ideas.md` §5). No API, interface, data or migration change; baselines
unchanged.

### Added

- `npm run audit:deps` (`scripts/audit.mjs`): audits `apps/backend/uv.lock` with `pip-audit`
  2.10.1 and the frontend and root npm lockfiles with `npm audit`, from the locked versions
  only. Any Python advisory and any high or critical npm advisory fails; low and moderate npm
  advisories are listed. A package pip-audit skips fails; environment markers are ignored, so
  Windows-only packages are audited on Linux CI too. Exit 2 when an audit cannot run.
- `audit-accepted.json`: advisories accepted with a reason and a date (empty).
- CI workflow `audit.yml`: on pull requests, pushes to `main`, weekly (Monday) and on demand.

### Security

- Backend: certifi 2026.10.23 (PYSEC-2026-4320), djangorestframework 3.18.3
  (CVE-2026-114136, CVE-2026-114137, CVE-2026-114138).
- Root runners: concurrently 10.0.6 with shell-quote 1.12.0 (GHSA-pqg4-j6r4-53mv, critical).
- Frontend: vite 8.3.5 (GHSA-587h-7wmj-h5pm), zod 4.6.7 (GHSA-mrhx-c7xc-m3w5), undici 8.12.3
  (GHSA-xjj6-f33q-929c, GHSA-4w7w-5xrc-9h26, GHSA-2m5v-pch6-74hx, GHSA-qrxm-fqhp-jwvm),
  source-map-js 1.2.2 (GHSA-68fv-2mgg-jv7q), with vitest 5.0.5, postcss 8.5.32 and rolldown
  1.2.15. Every audit now reports no findings.

### Changed (internal)

- Review of 0.12.32–0.12.34 (`Bug_Backlog.md` batch 21, M-1…M-15): a malformed pip-audit
  report is a clean audit error like a malformed npm report; `contribution_type` drops a
  redundant tie-break index; `import_judgments` passes its path to `write_json` as given.

## [0.12.33] - 2026-10-28

JSON report writer (`openspec/changes/archive/2026-10-28-json-report-writer/`;
`Bug_Backlog.md` T-14, `ideas.md` §15). No API, interface, data or migration change; baselines
unchanged.

### Changed

- Management commands write JSON through one helper, `core/reports.py` (`json_text`,
  `write_json`): `evaluate_ranking`, `feedback_report` and `discovery_report` (`--json`),
  `export_benchmark_developer`, `import_judgments`, `build_benchmark` and `e2e_seed`.
- Every JSON file they write keeps non-ASCII text unescaped and ends with a newline (the
  reports and the e2e sessions file escaped it before; data unchanged).
- A failed write reads "<what> not written to <path>: <reason>" in every command; `e2e_seed`
  reports it as a command error instead of a traceback.

## [0.12.32] - 2026-10-28

Signal fixes (`Bug_Backlog.md` B-6, D-11 of batch 8 and T-11 of batch 19; no OpenSpec change,
the `issue-matching` spec edited directly for T-11). No API, interface or migration change;
baselines unchanged.

### Fixed

- The internal experience level is now the rounded mean of its signal scores, as documented:
  scores (1, 1, 0) are intermediate, not beginner, and a mean of 1.4 is intermediate, not
  experienced (B-6). It feeds issue difficulty fit only. Benchmarks store each developer's
  level, so baselines do not move; stored profiles change on their next analysis (or run
  `npm run manage -- reanalyze_profiles`).
- An issue's contribution type from its title now follows the keyword that comes first, so
  "[Bug]: docs build crashes" is a bug fix, not documentation (D-11). `ISSUE_TAXONOMY_VERSION`
  2026.10.4; stored issues change on their next fetch, and baselines do not move.
- An issue is relevant, and counts as mentioning the developer's technologies, only through a
  part that adds to its score: with an issue weight of 0, that part no longer makes it relevant
  (T-11; spec `issue-matching`). No stored configuration has a weight of 0, so nothing moves.

### Changed

- Ranking changes no longer wait for judged real developers (K-1 is optional). They still must
  win on the selection benchmark and not regress on a fresh holdout.
- `Bug_Backlog.md` P-1 (why the WSL keep-alive once exited `0xC000013A`) accepted: the runner's
  restart covers it; a retest from a cold distro stayed up.

## [0.12.31] - 2026-10-27

Data versions fixes (OpenSpec change `data-versions-fixes`, `Bug_Backlog.md` batch 20: review
of 0.12.24–0.12.30). No ranking, API or interface change; no migration.

### Fixed

- A sync that fails after storing data now moves the `github` data version, so pages refresh
  the GitHub data it stored (U-1).
- The hidden list is refreshed with the recommendations when their repositories change (U-2).
- Discovery records the number of candidates its `not_code` cleanup actually removed, not the
  number it flagged (U-3).
- Two jobs finishing together no longer refetch the changed data twice (U-6); a finished
  discovery no longer asks for the data versions (U-5); deleting GitHub data resets the
  versions without detaching the page that watches them (U-7).

### Changed (internal)

- `/simplify` pass over 0.12.24–0.12.31: the data versions read the two job times in one
  query (three reads instead of four), and the web client compares versions when its cached
  value changes, not inside the fetch. The rank repair is tested on the real upgrade path
  instead of by dropping constraints, and the data-versions tests reuse
  `make_recommendation`.

## [0.12.30] - 2026-10-27

Content Security Policy (OpenSpec change `content-security-policy`, `ideas.md` §5). No ranking,
API or interface change; no migration.

### Security

- Every backend response carries a `Content-Security-Policy` header: API responses allow
  loading nothing; the admin and error pages allow resources from their own origin only.
  Both policies are settings, and the startup checks refuse an empty one (`core.E060`).
- The production build of the web app declares a policy in `index.html`: scripts and API
  calls from the same origin only, images also from GitHub avatars, no plugins, no `<base>`.
  The development server is unchanged.

## [0.12.29] - 2026-10-27

Rank constraint (OpenSpec change `rank-constraint`, `Bug_Backlog.md` T-12). No ranking, API or
interface change.

### Fixed

- The database refuses a rank of 0 for recommendations, their matched issues and feedback
  events (an event's rank stays empty when it had no recommendation). Ranks were always
  written from 1, but the columns accepted 0, which only the feedback report read as "no
  rank".

### Migration

- `recommendations.0005`, `issues.0002`, `feedback.0005` add the constraints after repairing
  stored rows: a group of recommendations or matched issues with a rank 0 moves up by one
  (order kept), an event's rank 0 becomes empty. Nothing is deleted.

## [0.12.28] - 2026-10-27

New seeds stored inactive (OpenSpec change `new-seeds-inactive`, `ideas.md` §15). No ranking,
API or interface change; no migration.

### Added

- `recommendations/migrations/_seeding.py`: `store_inactive` and `remove_unused` for scoring
  configuration seeds after `v2-deterministic`. A later seed stores its version inactive and
  never changes which configuration is active; its reversal deletes the version only while it
  is inactive and produced no recommendations. Activation stays `activate_scoring_config`.
- A test fails when a migrated database has any configuration other than `v2-deterministic`
  active, or stores an invalid configuration.
- README: how to add a configuration (seed inactive, evaluate, activate).

## [0.12.27] - 2026-10-27

Data versions (OpenSpec change `data-versions`, `ideas.md` §14, `Bug_Backlog.md` Y-6). No
ranking change; no migration. Additive API change (OpenAPI stays `1.0.0`).

### Added

- `GET /api/v1/sync/versions`: when the signed-in user's GitHub data, developer profile and
  recommendations last changed (the recommendations time includes background refreshes of
  the repositories they show or that are saved). Read-only, built from stored times.

### Changed

- The web client asks for the data versions when a signed-in page loads, on window focus, on
  every page change and after a finished job, and refetches only the areas whose time
  changed. Data changed with no job the page watches (a background repository refresh, an
  analysis whose discovery failed) no longer stays cached up to 5 minutes (Y-6).
- A finished generation no longer refetches the profile, skills and interests unless the
  profile was re-analyzed (S-8 narrowed).

## [0.12.26] - 2026-10-26

Post-analysis pool cleanup (OpenSpec change `post-analysis-pool-cleanup`, `ideas.md` §11,
`Bug_Backlog.md` X-9). No ranking, API or interface change; no migration.

### Changed

- A discovery run ends its analysis step by removing from the pool every candidate it analyzed
  that is now not a code project (a suspected list without manifest dependencies), instead of
  leaving it until the next run's pool step. The job records `analysis_not_code` and the pool
  size and band counts again; the shared repository row is kept. Fenced like the pool step: a
  cancelled run removes nothing.
- The ids analyzed successfully are kept in the job metadata (`analysis_succeeded`), so a
  resumed analysis step still cleans up.

## [0.12.25] - 2026-10-26

Discovery yield report (OpenSpec change `discovery-search-yield`, `ideas.md` §12). No ranking,
API or interface change; no migration.

### Added

- Every discovery run records the yield of each search query in its job metadata
  (`query_yield`, keyed by query key): strategy, star band, results, rejections per reason
  (pre-filter and `not_code` found while storing), candidates recorded, or `refused` for a 422.
  No query text. The run totals (`rejections`, `results_found`) are unchanged.
- `PlannedQuery.band`: the star band's label with more than one band configured (`""` with one;
  plans stored by older runs load with `""`).
- `npm run manage -- discovery_report [--since DAYS] [--json OUT]`: per strategy, per star band
  and per strategy and band over finished runs: requests, refused, results, rejections per
  reason, recorded, results per request and recorded share. Runs without per-query yield are
  counted on their own line. Aggregates only, read-only.

## [0.12.24] - 2026-10-26

Setup readiness (OpenSpec change `setup-readiness`, `ideas.md` §8). No ranking change; OpenAPI
stays `1.0.0` (additive).

### Added

- Repository analysis records four setup facts from the root listing it already fetches for
  manifests: CI (GitHub Actions workflows, or another service's root configuration), tests (a
  root test directory or test-runner configuration), dev environment (`.devcontainer`,
  `.devcontainer.json`, `.gitpod.yml`) and Docker Compose. At most one extra request per
  repository (`.github/workflows`, only with a `.github` directory and no other CI marker).
  Refreshed with the dependencies (weekly); repositories analyzed earlier show them as unknown
  until then. Migration `repositories.0009`, no backfill.
- Recommendation list items and the detail return `setup` (`ci`, `tests`, `dev_environment`,
  `docker_compose`: true, false or null).
- Cards show the facts found ("CI · tests"); the detail page has a "Setup" group with Found /
  Not found / Not available. Detection looks at the root only, so absence reads "Not found",
  never "No".

### Changed

- `GitHubClient.list_contents(full_name, path)`; `list_root_contents` delegates to it.
  `read_manifests` accepts a root listing the caller already has.

## [0.12.23] - 2026-10-26

Dismiss reasons (OpenSpec change `dismiss-reasons`, `ideas.md` §4). No ranking change; OpenAPI
stays `1.0.0` (additive).

### Added

- Dismiss with a reason: next to Dismiss, a small menu offers "Not my stack", "Too big",
  "Inactive" and "Already know it" (keyboard: Enter or ArrowDown opens, arrows move, Escape
  closes). Dismiss itself is unchanged: one click, the same request, the same Undo.
- `POST /api/v1/recommendations/{id}/dismiss` accepts an optional `{"reason": ...}`
  (`DismissReasonEnum`); an unknown reason is 400 `validation_error` and dismisses nothing.
  The reason is stored on the hidden entry and its `dismissed` feedback event (migration
  `feedback.0004`, no backfill). `GET /api/v1/dismissed` returns `reason` (null when none), and
  the hidden list shows it.
- `feedback_report` prints `dismiss reasons: ...` per configuration (`none` = without a
  reason); the JSON gains `dismiss_reasons`. Shares are unchanged.

### Changed

- Privacy page: hidden projects and feedback events keep the optional dismiss reason.

### Fixed

Code review of the uncommitted 0.12.14–0.12.23 work. No ranking change.

- The reason menu closes while a dismiss is in flight, so it cannot send a second request.
- `feedback_report` lists the reasons of dismissals without a recommendation snapshot on their
  own line (JSON `unattributed_dismiss_reasons`), and counts an event with rank 0 as
  unattributed instead of in `21+`.
- Issue reasons: an unknown difficulty reads "Difficulty not estimated" (unknown also means
  signals that disagree, not only too few), and a part whose weight is 0 gets no reason, as
  repository reasons already did.
- `ScoringConfig.save` compares the fixed fields as stored JSON: a description edit on a
  configuration built with tuples no longer raises `ImmutableConfig`.
- `ISSUE_DIFFICULTY.min_votes` above `classify.MAX_LEVEL_VOTES` (4) fails `core.E040`; such a
  value left every issue unknown. New warning `core.W004` when it leaves a level unreachable
  (3 or 4: intermediate has only two voters). Capacities come from `classify.LEVEL_VOTERS`,
  which a test checks against the classifier.

### Changed (internal)

Cleanups from `/simplify`. No output changes; `evaluate_ranking` prints the same intervals.

- `feedback_report`: one accumulator and row builder for buckets and labels, one table printer
  in the command; `load` streams events unordered (no sort of the whole event log).
- Bootstrap: one set of resamples per comparison, shared by its five metrics
  (`bootstrap.draws`); `Interval.as_dict` replaces the command's own rounding.
- `DeveloperResult.metrics` is derived from `values`; `KeysetPagination` builds one response
  for both modes; issue reasons read one per-part contributions dict, and `MatchedIssue`
  carries `mentions_technology`; `ranking.config.SUM_TOLERANCE`; `ImmutableConfig` lists
  fields with `join_names`.

## [0.12.22] - 2026-10-24

Documentation and housekeeping. No code, API, UI or ranking change.

### Changed

- `Bug_Backlog.md`: open items, known gaps and the release index come first, then the fix-batch
  plan (nearly all shipped), the totals and the review history (oldest first). No row changed.
- `ideas.md`: open ideas grouped by when they can ship: first those that change no ranking, then
  those that wait for K-1 (†). The priority table lists items in suggested order and drops
  shipped ones; section numbers §1–§17 are unchanged.
- `.gitignore`: `reports/` (and `apps/backend/reports/`) for `evaluate_ranking --json` and
  `feedback_report --json` outputs; feedback reports hold real-use aggregates.
- README, CLAUDE.md and `features.txt` point to the new layout; the planned list in
  `features.txt` drops ideas that shipped in 0.12.11–0.12.13 and lists Y-6.

## [0.12.21] - 2026-10-24

Match-label calibration (OpenSpec change `feedback-report-labels`, `ideas.md` §4). No API, UI,
ranking or data change.

### Added

- `feedback_report` shows, per scoring configuration, one row per match label (Strong, Good,
  Partial) with counts, users and the positive share, and a calibration verdict: `ordered`,
  `not ordered` (naming the first pair out of order) or `not enough data`. Label shares are not
  adjusted for rank. The JSON report gains `labels` and `calibration` per configuration.

## [0.12.20] - 2026-10-24

Feedback report (OpenSpec change `feedback-report`, `ideas.md` §4). No API, UI, ranking or data
change.

### Added

- `npm run manage -- feedback_report`: how users acted on recommendations, per scoring
  configuration version and rank bucket (1-5, 6-10, 11-20, 21+), from the stored feedback events.
  Per group: each action's count, distinct users and the positive share (saved and opened out of
  those plus dismissed; there is no "shown" event, so not a click-through rate). Per
  configuration: raw and position-adjusted shares. Groups under `--minimum` (10) decisive actions
  show no share. `--since`, `--config`, `--json`. Aggregates only.

## [0.12.19] - 2026-10-24

Evaluation confidence (OpenSpec change `evaluation-confidence`, `ideas.md` §3). No API, UI or
ranking change; `baselines.json` untouched.

### Added

- `evaluate_ranking` prints, for every configuration after the baseline, a paired bootstrap
  block: per metric the difference from the baseline, its 95% interval over developers and the
  share of resamples in which it is not better, with `*` when the interval excludes 0.
  Reproducible (fixed seed); `--resamples` and `--seed` change it; `--json` writes it under
  `comparisons`.
- On `benchmark-v1`, v2 vs v1: NDCG@10 +0.0195 [-0.0023, +0.0501] (not better in 8.2% of
  resamples), Precision@5 -0.0333 [-0.1000, +0.0000]: neither is conclusive with six developers.

### Unchanged

- The improvement rule, `--require-improvement`, activation and the regression baseline do not
  read the intervals. Whether a ranking change must also be significant is decided with K-1.

## [0.12.18] - 2026-10-24

Activation by command only (OpenSpec change `activation-command-only`): S-6 from the review of
0.12.13/0.12.14 (batch 18). No API, UI or ranking change.

### Removed

- The Django admin action "Activate the selected configuration". It ran the benchmark
  comparison inside the web request (S-6). Activate a scoring configuration with
  `npm run manage -- activate_scoring_config <version>` (`--force --reason "..."` for a
  deliberate exception); the rule is unchanged.

### Changed

- A configuration's admin page shows the command that activates it, or that it is active.
- Activation audit entries always record `via: "command"`; entries made by the admin action keep
  `"admin"`.

## [0.12.17] - 2026-10-24

Saved and hidden list links (OpenSpec change `keyset-paging-links`): S-7 from the review of
0.12.13/0.12.14 (batch 18). No ranking change; OpenAPI stays `1.0.0`.

### Changed

- `GET /api/v1/saved` and `GET /api/v1/dismissed` page forward only: `previous` is always
  null. A page-number request (`?page=2`) used to return a page-number `previous` next to a
  cursor `next`, so a client following both could repeat or skip entries (S-7). The SPA never
  read `previous`.
- A request with both `cursor` and `page` is rejected with 400 `cursor_with_page`; `page` used
  to be ignored silently.
- The OpenAPI document lists the 400 error for both list operations (`invalid_cursor` has
  answered 400 since 0.12.12).

## [0.12.16] - 2026-10-24

Signal and explanation accuracy (OpenSpec change `signal-explanation-accuracy`): D-8, D-9, D-15,
D-16, D-17 and D-18 of batch 8. No API schema change (OpenAPI `1.0.0`); v1 and v2 score and rank
every benchmark dataset as before (`baselines.json` untouched).

### Changed

- The `issue_availability` reason says how its issues matched: "N open issues mention
  technologies you use", "N open issues are labeled good first issue or help wanted", or
  "N relevant open issues, M mentioning technologies you use". It no longer claims a profile
  match for issues that matched only by label (D-9). Stored reasons change on the next
  generation; older evidence keeps the technology wording until then.
- An issue of unknown difficulty whose difficulty fit counts in its score gets the reason
  "Difficulty not estimated (too few signals)" (D-16). Issue scores are unchanged.
- The relevance gate needs a relevance signal with a value and a configured weight above 0,
  for the final cut and for choosing whose issues are matched (D-8). No seeded configuration
  weights a relevance signal 0.
- A stored scoring configuration's version, weights and params never change: the admin shows
  them read-only for every saved row and `ScoringConfig.save` refuses a change; new numbers need
  a new version (D-15). Activation and description stay editable.
- `ISSUE_DIFFICULTY` gains `several_technologies` (default 2) and `min_votes` (default 2), with
  `core.E040` checks; the defaults equal the former fixed values, so analyses are unchanged
  (D-18).

### Fixed

- Openness points must sum to at most 1; a larger sum used to cap the signal silently (D-17).
  v1 and v2 sum to exactly 1.

### Documentation

- The specs now state rules shipped earlier without a spec change: reasons only for signals
  that add to the score (D-7, 0.12.14), description length without HTML comments (D-12) and
  bracketed label scopes (D-13, both 0.12.15).
- `Bug_Backlog.md`: batch 8 keeps only B-6 and D-11 (both wait for K-1).

## [0.12.15] - 2026-10-23

Bug fixes that need no spec change: D-12 and D-13 of batch 8, and S-9…S-11 from the review of
0.12.13/0.12.14 (batch 18). No API change; benchmark numbers are unchanged (`baselines.json`
untouched).

### Fixed

- Issue difficulty no longer counts issue-template instructions (HTML comments) as description
  length, so a short issue filled into a long template is not voted advanced (D-12).
- `[Type] Bug`-style labels map to their category like `Type: Bug` (D-13; issue taxonomy
  2026.10.3). Both apply when an issue is next fetched.

### Changed

- Job status queries live under `['jobs']` (`['jobs', 'recommendations']`,
  `['jobs', 'discovery']`), so a finished generation refreshes every profile-derived query with
  one invalidation and a new one cannot be missed; a finished sync also refreshes `['jobs']`
  (S-9).
- Lazy components load through one registry (`src/app/lazyLoaders.ts`) that the test setup
  preloads entirely, so a new one cannot bring back the random test timeouts of P-3 (S-10).
- Indexes for the saved and hidden list order (`feedback.0003`, S-11).

### Documentation

- `Bug_Backlog.md`: S-7 needs an OpenSpec change (design D2 of `freshness-paging-seed` keeps the
  page link as `previous`); S-6 needs a decision (tracked job, or the admin points to the
  command).

## [0.12.14] - 2026-10-23

Signal and explanation fixes that need no spec change (`Bug_Backlog.md` B-14, B-15, B-16, D-7,
from batch 8), plus fixes from the review of 0.12.13 and 0.12.14 (S-1…S-5, batch 18). The code now does what the specs already say. No API or UI change, and the
benchmark numbers are unchanged (`baselines.json` untouched).

### Fixed

- Profile README badges inside HTML attributes (`&amp;` in the URL) lost every parameter after
  the first, so a later `logo=` was never read (B-14).
- shields.io badges named their skill only through the first path segment; a skill in the
  message (`/badge/-Python-3776AB`, `/badge/language-Rust-orange`) was missed. Every segment but
  the color now counts (B-15).
- Interest evidence from a contributed repository was dated by the repository's last push
  instead of the contribution, as skill evidence already is (B-16).
- A signal the scoring configuration weights 0 no longer gets a recommendation reason; only
  signals that add to the score are explained (D-7).
- shields.io badge messages count only when the badge has no label or a technology label
  (`language`, `made with`); free text such as `code style-black` or `platform-linux` no longer
  adds README skills, and an encoded `%2D` is no longer a separator (S-5, review of B-15).
- `activate_scoring_config --force` works when the benchmark or the active configuration is
  unusable (the audit records "not compared"); `forced` is audited only when the improvement rule
  was not met; an activation fails when the active configuration changed while it was judged;
  the benchmark verdict uses the pinned baseline minimum score and top N, not local settings
  (S-1…S-4, review of 0.12.13).

### Changed

- Cleanup without behavior change: contribution evidence dates come from one
  `ContributionInput.observed_at`; the saved/hidden list paginator applies its own order; the v2
  seed migration drops two exclusions its early return made dead; one shared test helper for
  active configurations. The new `accounts` migration is stored with LF line endings.

### Documentation

- `recommendation-evaluation` spec: activation uses the pinned baseline minimum score and top N,
  a forced activation proceeds when the comparison cannot run, `forced` means the rule was
  overridden, and a concurrent change of the active configuration fails the activation.
- `Bug_Backlog.md` batch 18 (S-1…S-11): S-6, S-7 open; S-8 accepted; `/simplify` skips S-9…S-11
  (`ideas.md` §17).

## [0.12.13] - 2026-10-22

Config activation and loose ends (OpenSpec change `config-activation-loose-ends`,
`Bug_Backlog.md` P-3, Q-10, `ideas.md` §15). No ranking, API or UI change.

### Added

- `npm run manage -- activate_scoring_config <version>` switches the active scoring
  configuration. It refuses an unknown or invalid configuration and one that is not an
  improvement over the active one on the selection benchmark, printing the failed metrics;
  `--force --reason "..."` makes a deliberate exception such as a rollback. Every activation is
  recorded in the audit log (new action `scoring_config_activated`) with both versions, the
  reason and the failed metrics.

### Changed

- The admin "Activate" action applies the same rule (never forced): a refusal shows the failed
  metrics and points to the command.
- Library scripts (`scripts/child.mjs`, `env.mjs`, `stack.mjs`, `uv.mjs`, `restarts.mjs`) exit 1
  with a message when run directly, instead of exiting 0 having done nothing.

### Fixed

- Flaky frontend tests (P-3): the lazily loaded language chart blocked the event loop for about
  a second inside whichever test was running when it first loaded. The test setup now preloads
  it.

### Not changed

- Q-10 (newest-snapshot prefetch sort) is accepted: the cost is bounded by the snapshot history
  and measured at 0.4 ms; a `DISTINCT ON` rewrite still sorts on PostgreSQL 18.

## [0.12.12] - 2026-10-22

Freshness, paging and seed (OpenSpec change `freshness-paging-seed`, `Bug_Backlog.md` Y-6, Y-7,
Z-1). No ranking or UI change; the API change is additive (OpenAPI stays `1.0.0`).

### Fixed

- The saved and hidden lists no longer repeat or skip a project when one is saved, unsaved,
  dismissed or restored (for example in another tab) between "Show more" clicks.
  `GET /api/v1/saved` and `GET /api/v1/dismissed` continue after the previous page's last entry
  through an opaque `cursor` in `next`; `count` and `page` keep working, and an unreadable cursor
  answers 400 `invalid_cursor` (Y-7).
- Profile changes from an analysis no sync started (`reanalyze_profiles`) show on an open
  dashboard when the generation that follows finishes: a finished generation also refetches the
  developer profile, skills and interests, instead of waiting up to 5 minutes (Y-6, in part).
- Re-applying the `v2-deterministic` seed after a rollback no longer re-activates v2 over
  `v1-deterministic`: when v2 is already stored, the seed changes no activation. Re-activate v2
  with `activate_scoring_config v2-deterministic --force --reason ...` (0.12.13) (Z-1; spec
  `recommendation-engine` changed).
- CI's `e2e` job no longer hangs after the last browser test: the e2e backend runner keeps
  Django in Playwright's process group, so Playwright's `SIGKILL` stops it and its output pipe
  closes. Every CI job now has a `timeout-minutes` limit.

## [0.12.11] - 2026-10-22

Tooling and data hygiene (OpenSpec change `tooling-data-hygiene`, backlog batch 16 and Q-10…Q-12).
No ranking, API or UI change.

### Fixed

- The Redis runner no longer takes the whole stack down when the WSL keep-alive ends: it starts
  a new one (at most 3 times in 5 minutes) and logs the exit code in decimal and hex. An
  intended stop never restarts it (P-1, in part: the cause is still unknown).
- `.gitattributes` checks text files out with LF on every OS, so `npm run format:check` passes
  on Windows. Earlier Windows checkouts refresh their working files once (README) (P-2).
- `npm run api:sync` finds `uv` without PATH, like every other backend command (P-4).

### Changed

- Runner scripts are linted (ESLint) and format-checked (Prettier) in CI: `npm run
  lint:scripts`, `npm run format:scripts`. The Prettier config moved to the repository root and
  is shared with `apps/frontend` (P-5).
- The snapshot index includes the `id` tie-break (migration `repositories.0008`), and one
  ordering constant replaces three copies; single-repository newest-snapshot reads no longer
  sort (Q-10 in part, Q-11).
- The `_update_metadata` wrappers are gone, and tests import the seed builders from
  `e2e.builders` (Q-12).

### Not changed

- P-3 (two frontend tests that failed once under load) did not reproduce in 8 runs; it stays
  open in `Bug_Backlog.md`.

## [0.12.10] - 2026-10-22

Performance and cleanup (OpenSpec change `performance-cleanup`, backlog batch 11). No ranking,
API behavior or UI change.

### Fixed

- A worker job no longer fails when the GitHub response cache (Redis) cannot be reached: the
  request goes out without its ETag condition, and the process skips the cache for
  `GITHUB_CACHE_BACKOFF_SECONDS` (new, default 30) (A-16).
- A 304 from GitHub renews the cached response's lifetime, so an unchanged resource keeps
  getting cheap conditional requests instead of a counted refetch (A-17).
- `npm run stop` reads its records before the process list, so a runner starting at that
  moment is never dropped as stale; the WSL keep-alive is recorded only with a real process id;
  on Linux processes are named by their executable, not by `ps comm` (Z-4, Z-5, Z-8).

### Changed

- The unread `github:ratelimit:*` cache entry is no longer written or purged (A-16).
- Fewer queries and writes:
  - the health check reuses one Redis client per process (A-20);
  - the profile read counts skills and interests without joining them (B-17);
  - the recommendation freshness sweep filters due developers in SQL (D-21);
  - discovery merges only changed metadata keys after each analysis (C-20);
  - the saved list, recommendations and feature loading load only each repository's newest
    snapshot (E-10);
  - completing an analysis no longer reads back the topics and dependencies it just stored
    (X-11);
  - `npm run stop` ends every matched process with one `taskkill` (Z-9).
- OpenAPI: `ineligible_reason` on discovery candidates is read-only (non-breaking).
- Code and tests: one app-credentials check, one name-joining helper, issue label constants
  from one module, `score_candidate` uses `weighted_score`; shared test fixtures and `ids`
  helper, browser-test builders in `e2e/builders.py` (no import of test code), one frontend
  `callsTo` helper (B-20, C-21, C-23, D-19, D-20, X-12, Y-9, Y-10, Z-10).

- Review follow-ups Q-1, Q-2, Q-4, Q-5, Q-7, Q-8: profile sync and generation summaries merge
  their metadata too, `score_candidate` computes contributions once, recommendation reasons use
  the shared name-joining helper, data deletion still purges `github:ratelimit:{pk}` keys from
  before the upgrade (one release), and `npm run stop` on Linux names a process by its
  `/proc/<pid>/exe` link (paths with spaces).

- `/simplify` pass: the freshness filter compares one `GREATEST` of the change times, so each
  correlated subquery runs once per profile; `merge_metadata` writes through `save_progress`;
  `Backoff.call` is the one try-or-skip wrapper (throttles and the GitHub client); tests reset
  every backoff and the health client centrally and share one fake down cache.

### Not changed

- A-18 (cache a profile sync's public endpoints in the shared scope) is wontfix: those entries
  would outlive "delete my data".

## [0.12.9] - 2026-10-21

Dev scripts, checks and migrations (OpenSpec change `dev-scripts-checks`, backlog batch 10). No
ranking, API or frontend behavior change.

### Fixed

- `npm run stop` stops only this checkout's stack. Runners record themselves in the gitignored
  `.run/`, and a recorded process is stopped only while it still runs the recorded program;
  Django, Celery and Vite still match by repository path. Another project's or another
  checkout's `scripts/start.mjs` and friends keep running, and a reused process id is left
  alone and its record discarded (G-1).
- The WSL keep-alive that holds Redis awake is recorded and stopped by `npm run stop`, and the
  Redis runner also stops on SIGHUP, so closing the console no longer leaves WSL and Redis
  awake (G-2).
- A runner whose child already exited no longer throws in its signal handler, and a program that
  cannot be started (for example a wrong `UV_BIN`) prints `Could not start <cmd>: <message>` and
  exits 1 instead of a stack trace (G-3).
- Port waits keep their deadline against a host that drops packets: each connection attempt
  times out within the remaining time (G-4).
- Each checkout has its own Celery beat schedule file (`contribfinder-celerybeat-<hash>` in the
  OS temp dir), so two checkouts or worktrees no longer share one (G-7).
- CI cancels an older run only on pull requests; every push to `main` is checked (G-8).
- `npm run check:version` also checks `packages[""].version` of both npm lockfiles and names
  the failing entry (G-9).
- `npm run setup` installs with `npm ci` at the root and in `apps/frontend`, so it never rewrites
  a lockfile (G-10).
- Startup checks cover the remaining numeric settings: sync and job settings, GitHub caps and
  timeouts, OAuth state limits, repository grace and retry windows,
  `DISCOVERY_ANALYSIS_CONCURRENCY`, `REPEATED_CONTRIBUTION_MIN_PRS`, `SESSION_COOKIE_AGE` and
  `REDIS_SOCKET_TIMEOUT` (`core.E020` positive integer, `core.E050` non-negative integer,
  `core.E051` positive number), and `EXPERIENCE_THRESHOLDS` (`core.E014`: known signals, each a
  pair of non-negative numbers in order). A recovery interval of 0 no longer loops; a scalar
  threshold no longer fails every analysis (H-7).
- Seeding `v2-deterministic` no longer replaces an operator-activated configuration; it is then
  stored inactive (H-10). Re-applying the `v1-deterministic` seed after a rollback no longer
  leaves no configuration active (H-11). Databases already migrated keep their current state.
- Review follow-ups (Z-2, Z-3, Z-6, Z-7): pushes to `main` get a CI concurrency group per commit,
  so a queued run is no longer replaced by a newer push; `check:version` and `wait-port` run
  their CLI also when started through a symlink or junction (`check:version` used to print
  nothing and pass); reversing both seeds while v2 has recommendations keeps v1 as the active
  configuration instead of leaving none; the beat schedule test hashes real Windows paths.

### Added

- `npm run test:scripts` (also in CI): Node built-in tests for the runners' process matching,
  port waits, beat schedule name and version check.
- Tests for seed migrations in both directions, for every user-linked model being either deleted
  with GitHub data or deliberately kept, and for the privacy page naming each deleted category
  (H-19).

### Changed

- Celery no longer stores task results (`CELERY_TASK_IGNORE_RESULT`); nothing read them (H-20).
- Stacks started before this release have no process records: stop them once with the old
  `npm run stop` before upgrading.
- Internal cleanup with no behavior change: runner records carry their own match marker (no
  runner list to keep in sync; runners call `recordProcess()`), `npm run stop` reads the records
  once, scalar setting checks share one helper (`_rule_errors`), `EXPERIENCE_THRESHOLDS` uses
  the shared mapping check and the signal names from `services.profiling.experience.SIGNALS`.

## [0.12.8] - 2026-10-21

Frontend correctness (OpenSpec change `frontend-correctness`, backlog batch 9). No ranking or
API change. New browser tests and a CI job `e2e`.

### Fixed

- The dashboard no longer refetches skills, interests, repositories, recommendations and saved
  projects on every window focus or return from a detail page. Data derived from a job is
  refreshed when that job newly finishes, once per status fetch, however many components show
  the status (F-1, F-9). Derived data stays fresh for 5 minutes otherwise; status queries still
  refetch on focus.
- Errors that a retry cannot fix show at once: only network failures and 5xx responses are
  retried, twice. A `404 not_analyzed` no longer shows "Loading…" for about 7 seconds (H-5).
  Unit tests use the same client as the app.
- An expired session returns to the sign-in page with "Your session ended. Sign in again to pick
  up where you left off." from any request, including Save, and drops the cached data (F-7).
- `?page=N` past the last page shows page 1 instead of a dead error; dismissing the last card on
  a page shows the previous page instead of the empty state (F-3).
- "N relevant issues" opens the recommendation scrolled to its relevant issues, with keyboard
  focus there; the scroll is instant under reduced motion (F-5).
- A recommendation or issue link whose id is not a positive integer says it doesn't point to
  anything, instead of "Loading…" forever (F-6).
- Saved and hidden projects load 50 at a time with "Show more", so more than 100 can be seen and
  restored (F-2).
- Changing a filter no longer restarts the 10-second Undo window after a dismissal (F-8).
- The languages chart computes every share, "Other" included, from bytes. Many small languages
  no longer vanish, and a language under 1% shows "<1%", not "0%" (H-17).
- Review follow-ups (Y-1…Y-5, Y-8): logging out, disconnecting or deleting the account while a
  status poll is in flight no longer shows "Your session ended"; a finished job's refresh no
  longer holds up its status (a slow derived request could freeze polling); a malformed link
  hash no longer blanks the page; a failed dismissal of a page's last card keeps that page;
  ids such as `0x1f` or `1e2` are rejected; the browser tests take only `DATABASE_URL` from a
  local `.env` (the runner sets `DJANGO_READ_DOTENV=0`, which `base.py` honors), so they see
  CI's settings.

### Added

- Playwright browser tests (`npm run e2e` in `apps/frontend`) against the real Django backend
  and PostgreSQL (database `contribfinder_e2e`). They cover sign-in start, onboarding, the
  dashboard, save, dismiss and undo, the relevant-issues link, session end and data deletion
  (H-18). Seeded users sign in through sessions created by `e2e_seed`, a command in the `e2e`
  app that only `config.settings.e2e` installs; GitHub is unreachable there.

### Changed

- CI caches the Playwright browser download between runs (keyed on the frontend lockfile).
- Internal cleanup with no behavior change: `createQueryClient` takes `navigate` and handles a
  401 itself (no copied wiring in the app and tests), status hooks share
  `fetchStatusAndRefresh` without a job selector, `isActive` has one import path, and the
  e2e seed signs users in with `force_login`.

## [0.12.7] - 2026-10-21

Discovery and repository data (OpenSpec change `discovery-repository-data`, backlog batch 7,
with its review follow-ups X-1…X-6). No ranking change: scores, order and the benchmark
baselines are unchanged. Migration `repositories.0007` backfills `lifecycle_changed_at` and
adds `refresh_queued_at`. Discovery job steps now run queries → search → interactions → pool
→ analysis.

### Fixed

- A repository whose name another GitHub ID takes is no longer deleted (which cascaded to every
  user's candidates, recommendations, saves and dismissals). It gives the name up
  (`org/tool~<id>`) and its next analysis finds it by GitHub ID (new
  `GitHubClient.get_repository_by_id`); a lookup by name that answers 404 or another
  repository falls back to the ID too (C-2).
- Search results update a repository's fields but no longer count as a metadata fetch, so
  frequently found repositories get their languages and metadata refreshed (C-8).
- Analysis decides eligibility from the locked current row, including search updates stored
  while it fetched (C-14). Data fetched under a name that changed meanwhile is discarded.
- A FAILED repository's retry fetches every data type, whatever the queued task asked for, so
  a deleted repository is never made eligible again (C-5). A task for particular data types
  fetches only those still stale (C-15).
- Each query's results are stored in GitHub ID order, so concurrent discovery runs no longer
  deadlock (C-7).
- The pool step re-checks every eligibility rule on stored data through the lifecycle (new
  `recheck_eligibility`): settings changes apply without waiting for a refresh (R-12), and a
  FAILED or in-progress repository is no longer overwritten as `not_code` (R-4).
- `not_code` no longer rejects real code. A repository without a language is still rejected
  at search. An `awesome-*` name or a list topic only marks a suspected list, which is
  `not_code` after analysis unless it has manifest dependencies (`awesome-lint` is code). A
  list already decided is rejected at search without a new analysis (R-5).
- Discovery steps are queries → search → interactions → pool → analysis: the analysis
  budget is spent only on kept candidates (C-11). The analysis list is chosen once per job, so
  a resumed step keeps its cap and total (C-12).
- Discovery records a run did not see again are pruned (C-13). Stored query text no longer
  includes the star band (R-6).
- One pool order (previously interacted, best rank, most recently found, name) for the pool
  cap, the analysis and the candidate list (C-17).
- `pool_bands` counts a repository in the band that holds its stars, or under `other` (R-9).
- The backlog does not queue a repository again while its queued refresh can still run
  (`Repository.refresh_queued_at`), and its selection lives in
  `services/repositories/backlog.py` (C-15, C-16).
- `Repository.lifecycle_changed_at` is always set (default, backfilled) (C-18).
- The default star bands follow `DISCOVERY_MIN_STARS`, so setting only the minimum no longer
  stops Django (R-3). `DISCOVERY_STAR_BANDS` now defaults to unset and the bands are derived
  when used, so an overridden minimum always moves them. New warning `core.W003` for a query budget that is not a multiple of the
  band count (R-10). Topic reads use prefetching (R-11).
- Review follow-ups (X-1…X-6): a repository that gave up its name is ineligible
  (`name_released`) until resolved, never recommended under a wrong name and link; pruning
  keeps records when a run searched nothing or GitHub rejected the query; the pool step's
  writes are fenced by `job_write`; a queued refresh with nothing stale left changes nothing;
  the better rank wins when one query finds a repository in both bands; overlapping backlog
  runs never queue the same repository twice.

## [0.12.6] - 2026-10-21

Recommendation consistency (OpenSpec change `recommendation-consistency`, backlog batch 6).
No ranking change: scores, order and the benchmark baselines are unchanged.

### Fixed

- Stale is not gone: repositories marked stale or being refreshed stay recommended from their
  stored data, so the staleness sweep no longer removes recommendations or changes their ids
  (D-1). A staleness mark alone no longer triggers a regeneration.
- Generation, save, unsave, dismiss, restore, view recording and data deletion take one lock
  order, starting with the developer profile row: a dismiss is never missed or undone by a
  running generation, and dismiss/generation and issue refresh/generation no longer deadlock
  (D-2, D-3, D-4). An issue refresh locks every issue it touches, by pk, before deleting or
  updating any (W-3).
- A save racing a dismiss, or of a dismissed repository, answers 404 and leaves no hidden save
  (E-5); dismissing a saved repository records an `unsaved` event (E-6); simultaneous views are
  recorded once (E-7). A dismiss or view of a recommendation a regeneration dropped meanwhile
  no longer fails at commit; views lock only their recommendation, never waiting for a
  generation (W-1, W-2, W-9, W-10).
- Dismissals made during a generation are dropped before the top N is taken, so the list stays
  full (D-10).
- If a matched issue is deleted or re-analyzed before the result is stored, the generation
  ranks again (up to 3 attempts, then fails `issues_changed` keeping the previous result):
  stored counts, signals, labels and reasons always match the stored issues (D-6, W-8).
- Starting a generation while one is running makes it run again once it completes, so a
  restore or a discovery that finishes mid-run is always reflected (D-5). A retry clears the
  request (it reloads its inputs), and the freshness sweep never asks a running generation to
  run again (W-4, W-5).
- A developer whose candidate pool became empty no longer keeps old recommendations (D-14).
- Freshness also compares the repositories' data fetch times, so an analysis followed by a
  staleness mark is not missed (W-6), and after a failed generation the sweep waits
  `RECOMMENDATION_FAILED_RETRY_MINUTES` (default 360) instead of retrying every 30 minutes
  (W-7).
- The benchmark export holds the pool generation would score, stale repositories included,
  plus dismissed repositories (E-4).
- The Save button is disabled while a save or unsave is in flight, so a double click can no
  longer leave it showing the opposite of the stored state (F-4).

### Changed

- New `services/locks.py` (`lock_developer`) documents the lock order. `rank` and `rank_pool`
  accept `top_n=None`; generation cuts after dropping dismissals.
- `start_recommendations(user, rerun_if_running=False)` returns a running generation without
  asking it to rerun (used by the freshness sweep). Repository data parts and their timestamp
  fields live in one map (`staleness.PART_FIELDS`), shared by staleness and freshness. A
  generation retry re-ranks without reloading candidates; an issue refresh reads its issues
  once.
- A migration adds `SyncJob.rerun_requested` (internal, not serialized). New setting
  `RECOMMENDATION_FAILED_RETRY_MINUTES` (checked by `core.E020`). The API and OpenAPI schema
  are unchanged.

## [0.12.5] - 2026-10-21

GitHub error resilience (OpenSpec change `github-error-resilience`, backlog batch 5).
No ranking change.

### Fixed

- A 403 or 429 that reports a secondary rate limit (or the older abuse-detection message) with
  no `Retry-After` is now a rate limit with a 60-second wait, not "forbidden": contributor
  counts are no longer reported as unknown and shared repositories are no longer marked FAILED
  for every user (A-2, C-6).
- Renamed repositories are followed: 301/302/307/308 redirects are followed up to 3 hops, only
  to the API's own origin (scheme, host and port) and with the same credentials. A redirect
  anywhere else, including plain HTTP on the same host, is a client error and is never
  requested (A-4, C-1, V-2).
- A stored token that can no longer be decrypted (after a key rotation drops its key) fails
  jobs as `github_auth_invalid`, so the user is asked to sign in again (A-6).
- A 403, 451 or other non-retryable error on one repository's languages skips that repository,
  keeps its earlier languages and lists it in job metadata `languages_skipped`, instead of
  failing every sync (A-3). The same errors on the profile README mark the step `skipped` and
  keep the stored README (A-5). A repository deleted before the topics step no longer fails
  the sync (A-11).
- A sync now refreshes the account's username and avatar, so `/auth/me` shows a GitHub rename
  without signing in again (A-13).
- A non-JSON or incomplete `GET /user` response during sign-in (including a `null` login)
  redirects with `auth_error=failed` and is audited, instead of a JSON 500 (A-14, V-7).
- A deeply nested manifest yields no dependencies instead of raising `RecursionError` (B-13).
- Repository analysis records repository-specific failures on the repository and lets
  discovery continue: an unexpected GitHub 4xx is FAILED `client_error`, a response the client
  cannot read is FAILED `invalid_response` (C-1). The client raises `GitHubInvalidResponse`
  for a body that is not the JSON it expects, so a `KeyError` or `TypeError` in
  ContribFinder's own code still propagates as a bug (V-1). Rate limits, transient and auth
  errors, cancellation, lost claims and database errors still release the claim and propagate.
- A background refresh that fails without a retry, including rejected app credentials,
  records its error code and `refresh_failed_at` on the repository, keeps its state, and is
  not requeued until `REPO_REFRESH_RETRY_MINUTES` (default 60) has passed (C-9, V-4). It
  leaves alone a repository another analysis completed meanwhile (V-5), and the delay never
  holds back FAILED retries or dead-worker recovery (V-6).
- The API keeps working while Redis is down: throttles log one warning and count in process
  memory for `THROTTLE_CACHE_BACKOFF_SECONDS` (default 30), so limits still apply per process
  without waiting on Redis, and sessions use the database engine instead of `cached_db`
  (H-1, V-3). Existing sessions stay valid.

### Changed

- Owned repositories' topics are stored by the repositories step; the topics step only marks
  progress, and job metadata no longer copies the topics (V-9).
- A migration adds `Repository.refresh_failed_at` (nullable). New settings
  `REPO_REFRESH_RETRY_MINUTES` and `THROTTLE_CACHE_BACKOFF_SECONDS` are checked by `core.E020`.
  The API and OpenAPI schema are unchanged.

## [0.12.4] - 2026-10-19

Job lifecycle and claim fencing (OpenSpec change `job-claim-fencing`, backlog batch 4).
No ranking change.

### Fixed

- A worker whose job was reclaimed can no longer write: every job claim gets a token, and
  heartbeats, progress, guarded writes, retries and the final state require it. A reclaimed
  worker stops quietly and never starts a follow-up job (B-2).
- Repository analyses hold a fenced claim too, renewed between data types, so an analysis
  longer than `SYNC_STALE_AFTER_SECONDS` is not reclaimed while running and a reclaimed one
  changes nothing (C-3, C-4, C-19).
- A claim and its release no longer count as a lifecycle transition: a rate limit during a
  retry no longer restarts the FAILED retry delay or the DISCOVERED grace period (C-10).
- PENDING and RETRYING jobs whose task was lost are requeued after
  `SYNC_STALE_AFTER_SECONDS + GITHUB_MAX_RETRY_DELAY`, so a lost message no longer blocks the
  user forever (B-1). Abandoned RUNNING jobs move to RETRYING and are requeued once, not on
  every recovery run (B-12).
- Broker redelivery stops at `SYNC_MAX_ATTEMPTS` with `worker_lost` (B-10).
- With `REDIS_URL` empty, a retryable GitHub error fails the job instead of retrying inline in
  a hot loop (B-9).
- A FAILED or CANCELLED job never shows a step as running (B-11).
- Starting a job ignores and expires stale RUNNING jobs for every job type, and no longer
  fails with HTTP 500 when the conflicting job finished meanwhile (B-7, B-8).
- Concurrent profile analyses no longer deadlock on the shared skill and interest catalog
  (B-3), and an analysis of older data no longer overwrites a newer profile (B-5).

### Changed

- The four job start functions share one helper, and the profile analysis task runs through
  `run_tracked_job` (B-18, B-19). `SyncJob.heartbeat()` is replaced by
  `services.job_guard.heartbeat(job)`; `job_write` and `finish_job` take the job, and
  `ProfileAnalysisService` takes `job=`.
- Repository analysis saves its final state once instead of passing ANALYZED and INDEXED as
  separate saves (C-22).
- One stale cutoff (`job_guard.stale_before`) for job heartbeats and repository claims, and
  one way to end a job (`_end_jobs`) for every terminal state. `evaluate_ranking
  --write-baseline` takes the dataset file names from `services/evaluation/dataset.py`.
- Migrations add `SyncJob.claim_token`, `Repository.claim_token` and `Repository.claimed_at`
  (backfilled from `lifecycle_changed_at` for repositories being analyzed).

## [0.12.3] - 2026-10-19

Evaluation tooling integrity (OpenSpec change `evaluation-tooling-integrity`, backlog batch 3).
No ranking change: the recorded metrics are identical.

### Changed

- `evaluation/baselines.json` is format 4: each dataset records the top N its metrics were
  computed at. Formats 1–3 are still read.
- `evaluate_ranking --write-baseline` without `--dataset` rewrites `benchmark-v1`, every other
  recorded dataset whose file exists, and the selection benchmark, printing a report for each;
  `--require-improvement` covers every dataset.
- `--write-baseline` merges: configurations evaluated in the run replace their entries, the
  others keep theirs. A run at a different top N must cover every configuration recorded for
  that dataset.
- `--write-baseline` refuses `--min-score`.
- Imported judging sheets set the developer's description to "Real developer judged blind from
  a judging sheet." instead of the export's request to add judgments.

### Fixed

- `--write-baseline` never refreshed the `benchmark-v1` entry CI checks once `benchmark-v2`
  existed, and `--config v2-deterministic` dropped v1 from the file.
- One global top N in the baseline file made the test compare metrics computed at different
  top N values.
- Sheet import dropped `#` lines inside quoted multi-line descriptions (losing or misattributing
  grades), failed on blank rows saved by spreadsheets, and let a repeated repository win
  silently. Repeated repositories and grades without a repository now fail naming the row.
- `benchmark_sheet` crashed on languages without byte counts; they count as 0, and a repository
  with no counts lists its languages without shares.
- `build_benchmark` crashed on an input that is not a dataset object (e.g. an evaluation
  report) and merged inputs of another format version; both now fail naming the input.
- `evaluate_ranking --json` crashed when the output folder was missing; it creates the folder
  and reports write errors as a command error.

## [0.12.2] - 2026-10-19

Privacy and deletion finality (OpenSpec change `privacy-deletion-finality`, backlog batch 2).

### Added

- `services/job_guard.job_write`: job transactions that write a user's data lock the job row and
  require it to be RUNNING. Sync, profile analysis, discovery and recommendation writes use it,
  so a job running during a deletion can no longer write the deleted data back.
- `export_benchmark_developer --include-interacted`. By default the export now leaves out
  repositories the user contributed to or interacted with, since that set identifies them.

### Changed

- Disconnect ends the user's sessions on every device (the session auth hash is rotated).
- "Delete GitHub data", disconnect and account deletion clear the display name taken from GitHub.
- Account deletion removes the GitHub ID, GitHub username and address hash from the user's audit
  entries; action, outcome, time, reasons and counts are kept.
- A returning sign-in that gets a new token revokes the one it replaces: single-token
  revocation, best effort, in the Celery task `github.revoke_replaced_token`, so sign-in never
  waits on GitHub. An unchanged token queues nothing.
- The privacy page lists the GitHub account ID (kept until account deletion), candidate projects
  and search queries, sync history, sessions, and the audit address hash.
- `JobCancelled` moved to `services/errors.py`. Job progress writes go through
  `job_guard.save_progress`, so a cancelled or deleted job ends as a cancel, never a failed save
  (recommendation generation and the analysis task included). Per-item sync and discovery
  progress is saved in the same transaction as the item's data.

### Fixed

- Deleted data could reappear when a sync or analysis step finished after the deletion.
- Disconnect and account deletion cancelled the user's jobs twice.

## [0.12.1] - 2026-10-19

Security hardening (OpenSpec change `security-hardening`, backlog batch 1).

### Added

- `Bug_Backlog.md`: full codebase review, 147 findings verified against the code (115 confirmed,
  31 partial, 1 false positive) and grouped into 11 fix batches. This release is batch 1.
- `NUM_PROXIES`: number of trusted proxies in front of Django. Throttling, the audit IP hash and
  HTTPS detection (`X-Forwarded-Proto`) trust forwarded headers only through it; default 0.
  System check `core.W002` warns when the SSL redirect is on and no proxy is trusted.
- Production web server, Celery worker and beat run Django system checks at startup and refuse
  to start on errors (`RUN_STARTUP_CHECKS`).
- JSON error envelope for Django-level 400 (`bad_request`) and 403 (`permission_denied`).
- Sign-in from several tabs: each session keeps up to `OAUTH_STATE_MAX_PENDING` (5) single-use
  states for `OAUTH_STATE_TTL_SECONDS` (600).

### Changed

- **Breaking for deployments behind a proxy:** set `NUM_PROXIES`; `X-Forwarded-For` is no longer
  used as the client identity by default. `.env.example` sets 1 for the Vite dev proxy.
- `config/celery.py` defaults to production settings like `wsgi.py`; the npm runners
  (`scripts/env.mjs`) set development, and the backend image sets production explicitly.
- HSTS `includeSubDomains` and `preload` are opt-in (`SECURE_HSTS_INCLUDE_SUBDOMAINS`,
  `SECURE_HSTS_PRELOAD`).
- `/api/v1/health/` is not throttled and is exempt from the HTTPS redirect.
- Compose: the frontend container no longer receives `.env`; Redis and Postgres bind 127.0.0.1.

### Fixed

- Rate limits could be bypassed by sending a different `X-Forwarded-For` on each request.
- Log redaction missed quoted `key='value'` forms, `state` in dicts and JSON, and non-GitHub
  `Authorization` values; a malformed log call raised into the caller.

## [0.12.0] - 2026-10-15

Discovery project-size mix (OpenSpec change `discovery-size-mix`): the candidate pool now holds
smaller projects as well as the most popular ones, and curated lists or documentation
repositories no longer become candidates. **No ranking change**: scoring configurations, signals
and `baselines.json` are unchanged. The re-exported `real-a` pool (40 candidates) has a median of
56.5 contributors (was 906) and 19 candidates under 50 (was 2 of 39).

### Added

- Star bands: each search query runs once per band in `DISCOVERY_STAR_BANDS` (default `20..999`
  and `1000+`). Search ranks restart in each band, so the pool cap keeps a mix of sizes. A system
  check validates the bands (ascending, non-overlapping, only the last open-ended, first lower
  bound equal to `DISCOVERY_MIN_STARS`, budget at least the number of bands).
- Reason `not_code` in pre-filtering and eligibility: repositories named `awesome` or `awesome-*`,
  tagged with a `DISCOVERY_EXCLUDED_TOPICS` topic, or without a detected primary language.
- The pool step re-checks `not_code` on stored data, so lists found by earlier runs leave the pool
  and become ineligible (job metadata `pool_not_code`).
- Discovery job metadata `pool_bands`: pool candidates per band, plus `below` the lowest band.

### Changed

- `DISCOVERY_MAX_QUERIES` counts search requests (one query in one band); the default rises from
  10 to 20, so a run still makes 10 distinct queries. Provenance query text includes the band.

### Known limitations

- Documentation-style repositories with a code language and no list topic
  (`system-design-primer`, `developer-roadmap`) still pass; ranking and the judge handle them.
- Judging `real-a` and building `benchmark-v2` is still open (carried over from 0.11.0).

## [0.11.0] - 2026-10-14

Benchmark tooling for real developers (OpenSpec change `benchmark-real-judgments`): real,
anonymized developers can now be judged blind by a person who knows them and merged into a
selection benchmark, so the ranking is no longer judged only by its author. **No ranking change.
The judging itself is carried over: `benchmark-v2` was not built, so `benchmark-v1` remains the
selection benchmark.**

### Added

- Developer kind in datasets: `persona` (default) or `real`. Reports on a dataset with both kinds
  also show the persona and real means (`evaluate_ranking` rows "persona only" / "real only", and
  `subsets` in the JSON report).
- `benchmark_sheet`: a blind judging sheet (CSV with a grading guide) for an exported developer,
  one row per candidate in alphabetical order with description, languages, topics, contribution
  files, activity and open issue count, and nothing a scoring configuration computed.
- `import_judgments`: reads the graded sheet back into the export (grades 0, 1, 2 or blank; at
  least one relevant), marks the developer `real` and validates; nothing is written on an error.
- `build_benchmark`: merges datasets and judged exports into one benchmark. Duplicate developer ids
  fail; a repository described differently by two inputs fails unless `--on-conflict first`.
- Selection benchmark: `evaluate_ranking` defaults to `evaluation/benchmark-v2.json` once it holds a
  judged real developer, otherwise `benchmark-v1`. The replacement rule uses the same benchmark.
- README "Judging real developers": consent, bigger local pool, export, sheet, import, build.
  Exports and sheets go in the repository's `judging/` folder, which is gitignored.

### Changed

- `baselines.json` format 3, keyed by dataset; `--write-baseline` rewrites only the evaluated
  dataset's entry (`benchmark-v1` values unchanged). The baseline test checks every recorded
  dataset present on disk, so a local-only `benchmark-v2` is skipped.

### Fixed

- `export_benchmark_developer` and the new commands create the output folder and report write
  errors as command errors instead of tracebacks.

### Known limitations

- Judging is unfinished: the first real export (`real-a`, 39 candidates) has 3 graded rows.
- Discovery bias found while judging: almost every candidate is a very large project (median 906
  contributors, 2 of 39 under 50), several are lists or documentation. Search uses GitHub best
  match with only a star minimum, and the pool cap keeps the best-ranked. Fix the size mix in its
  own change, then re-export and judge.

## [0.10.0] - 2026-10-14

Ranking experiment (OpenSpec change `ranking-min-score-config`): the minimum score moves into the
scoring configuration and the relevance-scaled v3 candidates are re-run with it. **No candidate
qualified, so there is no ranking change: `v2-deterministic` stays active and v1/v2 score
bit-for-bit as before.** Full results:
`openspec/changes/archive/2026-10-14-ranking-min-score-config/candidates/RESULTS.md`.

### Added

- Configuration minimum score: `params.min_score` (0..1) with `params.min_score_basis` `score`
  (whole score) or `relevance` (skill, language, framework and interest contributions only, which
  relevance scaling never changes). Without them, `RECOMMENDATION_MIN_SCORE` applies. Generation
  and evaluation resolve it the same way; validation rejects out-of-range values, unknown bases and
  a basis without a minimum.
- `evaluate_ranking --min-score` is now an explicit override of every configuration's minimum;
  the output and the JSON report show each configuration's effective minimum, basis and whether it
  was overridden.
- Fresh acceptance holdout `apps/backend/evaluation/holdout-v2.json`: four persona developers
  (C#/.NET, PHP/Laravel beginner, D3 data visualization, Ansible DevOps), with weak-but-relevant
  candidates near the cut and busy off-topic ones, hashed before any candidate ran.
- Holdout rule: a holdout whose results for a search were recorded cannot accept a later search's
  candidate. `holdout-v1` and `holdout-v2` are both used; the next search adds `holdout-v3`.

### Changed

- `baselines.json` format 2: each configuration's effective minimum score and basis next to its
  metrics (v1/v2 values unchanged; the baseline test reads formats 1 and 2).

### Experiment results

16 predeclared candidates (the eight relevance-scaled v3 candidates × {min score 0.05 on score,
0.10 on relevance}). None was an improvement over both v1 and v2 on `benchmark-v1`; every one
scored exactly like its v3 base.

- **Correction to 0.9.0:** relevance scaling does not collide with the minimum score. The two
  relevant repositories it drops for the beginner persona have a relevance part near 0.008; under
  v2 they reach the list only because activity, openness and issue signals lift them over 0.10.
  v2's Recall@10 advantage on `benchmark-v1` rests on those two judgments.
- On the fresh `holdout-v2` every candidate beats v2 (Precision@5 +0.10, NDCG@10 up to +0.0193, no
  recall loss), and `holdout-v1` agrees. Holdouts only accept or reject, so nothing was activated.

### Known limitations

- Next step is data, not tuning: review `benchmark-v1`'s judgments, preferably by adding real,
  hand-judged developers via `export_benchmark_developer`, in a change of its own.

## [0.9.0] - 2026-10-14

Ranking experiment (OpenSpec change `ranking-v3-deterministic`): an attempt to find a
`v3-deterministic` that beats v2 on the benchmark. **No candidate qualified, so there is no ranking
change: `v2-deterministic` stays active and v1/v2 score bit-for-bit as before.** Full results:
`openspec/changes/archive/2026-10-14-ranking-v3-deterministic/candidates/RESULTS.md`.

### Added

- Holdout benchmark `apps/backend/evaluation/holdout-v1.json`: four persona developers (Java/Spring,
  Python ML, beginner Python, Vue) over 27 fictional repositories, judged before any candidate
  was evaluated and used only to accept or reject a configuration, never to choose one.
- Replacement rule (spec `recommendation-evaluation`): a configuration replaces the active one only
  when it improves on every stored configuration on `benchmark-v1` and does not regress on
  `holdout-v1` beyond the tolerance.
- Optional scoring parameters, off in every stored configuration:
  - `params.issues.difficulty_fit_mode`: `best` (default, v2 behavior) or `weighted` (score-weighted
    mean fit of the relevant issues, scaled by issue fit, so one weak fitting issue no longer
    scores 1.0);
  - `params.relevance_scaling`: activity, openness, issue fit and difficulty fit count in proportion
    to the candidate's relevance strength (weighted mean of skill, language, framework, interest).
  Reason weights follow the same (scaled) contributions as the score. Unknown values are rejected
  by validation.

### Experiment results

15 predeclared candidates (difficulty mode × relevance scaling × 4 weight vectors) on
`benchmark-v1`; none was an improvement over both v1 and v2.

- Relevance scaling fixes the targeted failure (off-topic repositories leave the Django persona's
  top 5; Precision@5 reaches 0.9333 for every scaled candidate) but collides with the global
  `RECOMMENDATION_MIN_SCORE` (0.10): weak but relevant repositories fall under it, and Recall@10
  drops to 0.8998–0.9206 (v2: 0.9554).
- Weighted difficulty fit alone barely changes the rankings (best: `c11`, ties v2 except NDCG@10
  −0.0009).
- On `holdout-v1` (recorded after the choice) no candidate regresses against v2 and the scaled
  ones gain up to +0.0359 NDCG@10; the holdout has few weak matches near the minimum score.

### Known limitations

- Next step: make the minimum score part of the scoring configuration (or apply it to the
  relevance part only) and re-run the scaled candidates in a new change with its own grid.
- Holdout and benchmark judgments are by the same author; real hand-judged exports would be
  stronger evidence.

## [0.8.0] - 2026-10-14

Phase 8b: Recommendation evaluation (OpenSpec change `phase-8b-evaluation`; SRS-2 §30, §61). Offline
and deterministic: no GitHub, LLM or embedding calls, no API, model or migration changes.

### Added

- Benchmark dataset format (JSON, format 1): benchmark developers as frozen matching inputs
  (skills, interests, experience level), a candidate pool per developer (repository data, activity
  snapshot, search rank, eligible issues with their analysis) and graded judgments (0, 1, 2).
  Loading validates the whole file and names the developer and field of every error.
- Seed benchmark `apps/backend/evaluation/benchmark-v1.json`: six persona developers (Django
  backend, React/TypeScript frontend, Rust systems, data engineer, Go infrastructure, beginner web)
  over 40 fictional `bench/` repositories, judged from the persona descriptions before any
  evaluation run. No real GitHub user data.
- Metrics: Precision@5, Precision@10, Recall@10, MRR and NDCG@10 (gain `2^grade - 1`) per
  developer and as the mean over developers, plus unjudged results in the top 10.
- `evaluate_ranking` command: scores stored configurations and unsaved ones from a JSON file
  against a dataset, prints dataset-level metrics with deltas against the first (baseline)
  configuration and every developer's top 10; `--json` report; `--require-improvement` exits
  non-zero unless NDCG@10 is higher and no other metric drops by more than `--tolerance` (0.01).
- `export_benchmark_developer` command: exports one user's stored features and candidate pool as
  an anonymized, unjudged benchmark developer (no username, email, GitHub id or token).
- Regression baseline `apps/backend/evaluation/baselines.json` (pinned min score 0.10, top N 50):
  a test recomputes v1 and v2 metrics on `benchmark-v1` and fails when the ranking moves;
  `evaluate_ranking --write-baseline` updates it deliberately.

### Changed

- Recommendation generation ranks through `services/ranking/pipeline.rank_pool`, the stage
  evaluation also uses. Behavior is unchanged (a parity test compares the two).

### Benchmark results (`benchmark-v1`)

| Config | P@5 | P@10 | R@10 | MRR | NDCG@10 |
|---|---|---|---|---|---|
| v1-deterministic | 0.9333 | 0.6333 | 0.9276 | 1.0000 | 0.9459 |
| v2-deterministic | 0.9000 | 0.6500 | 0.9554 | 1.0000 | 0.9654 |

Under the improvement rule, v2 is **not** an improvement over v1: NDCG@10 rises (+0.0195) but
Precision@5 drops by 0.0333 (an off-topic repository with open issues enters two personas' top 5).
v2 stays active; this is recorded, not tuned, in this release.

### Known limitations

- The seed judgments come from persona descriptions, not real developers; add real exports to
  strengthen the benchmark.
- Evaluation covers repository ranking only: issue-level relevance, discovery (which repositories
  enter the pool) and feedback-based online metrics are not measured.

## [0.7.0] - 2026-10-13

Phase 7: Issues (OpenSpec change `phase-7-issues`; FR-ISSUE-001..005, MVP+). Issue analysis and
matching are deterministic and rule-based: no LLM or embedding calls.

### Added

- New `issues` app. `Issue` stores the open issues of every pooled repository once, shared by all
  developers: GitHub fields (title, plain-text body capped at `ISSUE_BODY_MAX_CHARS`, raw labels,
  locked, assignee, comments, times) plus ContribFinder analysis with its evidence.
  `RecommendedIssue` holds each recommendation's relevant issues (rank, internal score, reasons)
  and is rebuilt with it.
- Issue ingestion (FR-ISSUE-001): `GitHubClient.list_open_issues` (most recently updated first,
  `ISSUES_MAX_PAGES` pages of 100, pull requests dropped, truncation recorded, 410 = issues
  disabled). Issues are a repository analysis part with their own staleness
  (`REPO_STALE_AFTER["issues"]`, 6 h); the backlog queues the new task
  `repositories.sync_repository_issues` when only issues are stale. Each fetch replaces the
  stored set, so closed issues disappear; a failed fetch keeps them and is recorded.
- Label normalization (FR-ISSUE-002): an alias table with scope-prefix stripping (`Type: Bug`,
  `kind/docs`, `good-first-issue`) maps raw labels to 13 canonical categories
  (`ISSUE_TAXONOMY_VERSION`). Raw labels are kept as sent.
- Contribution type (FR-ISSUE-003): code, documentation, testing, bug fix, feature, DevOps,
  design or unknown, from label priority first and title keywords second, with the deciding
  label or keyword recorded.
- Difficulty (FR-ISSUE-004): beginner, intermediate, advanced or unknown from signal votes
  (difficulty labels, description length, technologies mentioned, documentation work, discussion
  size; thresholds in `ISSUE_DIFFICULTY`). A level needs two agreeing votes and no contradiction,
  so a label alone never decides. Every vote is stored as evidence.
- Issue technologies: the skill catalog detects technologies in an issue's title, labels and body
  (ambiguous words only in labels; HTML and CSS left out).
- Issue matching (FR-ISSUE-005): eligible issues (open, unlocked, unassigned, updated within
  `ISSUE_MAX_AGE_DAYS`) are scored per developer from technology match, difficulty fit with the
  internal experience level and approachability labels. Up to 5 relevant issues per
  recommendation, each with reasons built only from those parts.
- Two repository signals, `issue_fit` and `difficulty_fit`, with reason types
  `issue_availability` and `difficulty`. Issues alone never make a project a recommendation.
- API: `relevant_issue_count` on recommendation list items; `difficulty` and `contribution_type`
  filters; relevant issues on the recommendation detail; `GET /api/v1/issues/{id}` with GitHub
  data and ContribFinder analysis as separate objects (404 unless relevant to one of the user's
  recommendations). `opened_issue` feedback now requires `issue_id` and stores the issue and a
  number snapshot.
- Frontend: "N relevant issues" on cards, the two new filters, a "Relevant issues" section on
  the repository detail page, and the issue page `/app/issues/:id` ("From GitHub" vs
  "ContribFinder analysis", description as plain text, "Not enough evidence" for unknown values,
  GitHub link recording `opened_issue`).
- Settings `ISSUES_MAX_PAGES`, `ISSUE_BODY_MAX_CHARS`, `ISSUE_MAX_AGE_DAYS`, `ISSUE_DIFFICULTY`
  with system check `core.E040`.

### Changed

- **Ranking change:** new scoring configuration `v2-deterministic` (skill 0.35, language 0.15,
  interest 0.15, framework 0.10, activity 0.10, openness 0.05, issue fit 0.05, difficulty fit
  0.05, plus issue matching parameters) is activated by migration. The freshness sweep
  regenerates every user's recommendations under it. Projects without relevant issues score a
  little lower than under v1 (for example Strong can become Good). `v1-deterministic` stays
  stored and can be re-activated from the admin; it scores the issue signals as 0.
- Issue difficulty and the profile's preferred difficulty share one choice set (OpenAPI
  `DifficultyEnum`).

### Known limitations

- One page of the most recently updated issues per repository: older good first issues in large
  repositories can be missed (truncation is recorded).
- Rule-based difficulty is often `unknown` (shown as "Not enough evidence").
- Every issue refresh (6 h) makes the pool's recommendations due for regeneration.
- Docker Compose verification remains future scope.

## [0.6.0] - 2026-10-01

Phase 8a: Feedback and data controls (OpenSpec change `phase-8a-feedback-data-controls`;
FR-FEEDBACK-001..004, FR-DATA-002, FR-DATA-003). Completes the MVP definition of done. Feedback
is recorded for analytics and evaluation only: it does not change ranking.

### Added

- New `feedback` app: `RecommendationFeedback` (viewed, saved, unsaved, dismissed, undismissed,
  opened repository, opened issue), stored independently of the recommendation with snapshots of
  the repository name, match label, rank and scoring config version. It survives regenerations
  and repository deletion (`SET_NULL`). Views are de-duplicated per recommendation within
  `FEEDBACK_VIEW_DEDUP_MINUTES` (30, system check `core.E020`).
- Save: `SavedRepository` (unique per user and repository). Saved projects survive regenerations
  and stay listed when they are no longer recommended. Recommendation list and detail carry a
  `saved` flag.
- Dismiss: `DismissedRepository`. Dismissing deletes the recommendation and any save, and the
  repository is excluded from every later ranking run (`load_candidates`, and re-checked inside
  the generation transaction so a dismissal during a run is honored). Restoring it starts a new
  generation.
- Feedback API: `POST /recommendations/{id}/feedback`, `POST|DELETE /recommendations/{id}/save`,
  `POST /recommendations/{id}/dismiss`, `GET /saved`, `DELETE /saved/{repository_id}`,
  `GET /dismissed`, `DELETE /dismissed/{repository_id}`.
- Data deletion (`services/data_deletion.py`), one routine for every path: cancels the user's
  jobs, deletes the GitHub profile and README, repository links, developer profile (skills,
  interests, evidence, candidate pool, recommendations), saves, dismissals, feedback and job
  history, removes shared repositories no one references any more, and purges the user's cached
  GitHub responses.
- `DELETE /api/v1/profile/github-data`: deletes GitHub-derived data and keeps the account and the
  GitHub connection, so the user can sync again.
- `DELETE /api/v1/auth/account`: revokes the GitHub grant (a failure is recorded, deletion still
  proceeds), deletes the data and the account, and ends the session.
- Audit actions `github_data_deleted` and `account_deleted` (with deletion counts). Audit entries
  survive account deletion without the user reference.
- Dashboard: Save/Saved and Dismiss (with Undo) on cards and the detail page; `viewed` and
  `opened_repository` events (never blocking); `/app/saved` page with saved projects ("No longer
  recommended" note) and hidden projects with Restore; a pipeline stage line next to Refresh
  (syncing, analyzing, finding projects, preparing recommendations); a "Your data" section with
  confirmed delete actions.
- Public `/privacy` page: what is stored, why, how long, and how to delete it. Linked from the
  landing page and "Your data".

### Changed

- **Behavior change:** disconnecting GitHub now also deletes all GitHub-derived data (SRS-2 §66),
  keeping only the account and its audit trail. Reconnecting starts from scratch. The disconnect
  dialog says so, and its audit entry records the deletion counts.

### Fixed

- Ctrl+C now stops `npm start` in an interactive Windows console (Anaconda Prompt, cmd). The
  `wsl.exe` processes that start and keep Redis alive switched the shared console's input to raw
  mode; `scripts/redis.mjs` now gives each one its own hidden console.
- The dashboard kept showing "No suitable projects yet" after a refresh when the recommendation
  generation finished between two status polls; the list now reloads whenever a new finished
  generation appears.
- The "Hidden … Undo" notice did not appear after dismissing a project: the card is removed
  before the request returns, which dropped the success callback.

### Known limitations

- Feedback does not influence ranking yet (post-MVP); evaluation arrives with Phase 8b.
- `opened_issue` is accepted but has no source until issues arrive (Phase 7).
- Docker Compose verification remains future scope.

## [0.5.0] - 2026-09-29

Phase 5: Recommendation engine, deterministic (OpenSpec change `phase-5-recommendation-engine`;
FR-REC-001..006). No LLM or embedding calls; scoring reads stored data only.

### Added

- Repository technologies (`services/matching/technologies.py`): the skill catalog maps a
  repository's languages (byte share), topics and dependency manifests to skills, with the source
  of each detection.
- Six relevance signals (`services/matching/signals.py`), each 0..1 with the evidence it used:
  skill match (weighted stack coverage), language match (code share × confidence), framework match
  and interest match (noisy-OR), activity signal (activity label) and contribution openness
  (contributing guide, issue templates, good-first-issue and help-wanted labels).
- Versioned scoring configuration (`ScoringConfig`, one active): weights, match-label bands and
  signal parameters, validated on save. Seeded `v1-deterministic` (skill 0.40, language 0.20,
  interest 0.15, framework 0.10, activity 0.10, openness 0.05; strong ≥ 0.55, good ≥ 0.35),
  marked experimental. Admin "Activate" action; configs in use cannot be edited or deleted.
- Ranking (`services/ranking/`): weighted score, Strong/Good/Partial labels, tie-break by search
  rank then name, top N (`RECOMMENDATIONS_TOP_N`, 50) above `RECOMMENDATION_MIN_SCORE` (0.10).
  A candidate needs at least one skill, language, framework or interest match: activity and
  openness alone never make a recommendation.
- `Recommendation` (non-null FK to the config that produced it, per-signal scores, technologies,
  activity, size) and `RecommendationReason` (type, text, contribution, JSON detail), built only
  from non-zero signals. Texts use words, never percentages.
- Generation job `recommendation_generation` (task `recommendations.generate_recommendations`):
  starts after every completed discovery, writes in one transaction, upserts per repository so ids
  stay stable, and keeps the previous results on failure or cancellation.
- Freshness: beat task `recommendations.refresh_recommendations` (every 30 minutes) regenerates
  when the profile, a pooled repository or the active config changed since the last generation.
- API: `GET /api/v1/recommendations` (rank order; filters `language`, `framework`, `activity`,
  `size`, `match`; 400 on unknown values), `GET /api/v1/recommendations/{id}` (language breakdown,
  README excerpt, contribution facts, activity signals) and `GET /api/v1/recommendations/status`.
  No score or rank is exposed.
- Dashboard "Recommended projects": cards with match label, top reasons, technologies (matched
  highlighted), activity and a GitHub link; URL-backed filters shown when there is more than one
  page (20) or a filter is active; pagination; generating and empty states.
- Repository detail page (`/app/recommendations/:id`) separating "From GitHub" (overview, topics,
  languages, activity, contribution guidelines, README) from "ContribFinder analysis" (why it
  matches, technologies, activity label, size).
- Settings `RECOMMENDATIONS_TOP_N`, `RECOMMENDATION_MIN_SCORE`, `REPO_SIZE_THRESHOLDS`,
  `RECOMMENDATION_REFRESH_INTERVAL_SECONDS`, `RECOMMENDATION_README_EXCERPT_CHARS`, with a system
  check (`core.E030`–`E032`).

### Changed

- Disconnecting GitHub also cancels an active recommendation generation.
- `jobs.recover_stale_jobs` also requeues recommendation generation jobs.

### Known limitations

- Save, dismiss and feedback on recommendations arrive with Phase 8a.
- Difficulty fit, issue fit and the difficulty and contribution-type filters arrive with issues
  (Phase 7).
- With the local pool capped at 10 (`.env`), at most 10 recommendations are generated.
- Ctrl+C still does not stop `npm start` in an interactive Windows console (Anaconda Prompt): use
  `npm run stop`. Carried to the next phase.
- Docker Compose verification moved to future scope.

## [0.4.0] - 2026-09-29

Phase 4: Repository discovery (OpenSpec change `phase-4-repository-discovery`; FR-REPO-001..004).
Builds a per-developer candidate pool. Nothing is ranked or recommended yet (Phase 5).

### Added

- Query generation (`services/discovery/queries.py`): the developer's top skills, interests,
  languages and repository topics become GitHub search queries in four strategies (language,
  skill, interest, topic) within a per-run budget (`DISCOVERY_MAX_QUERIES`, default 10). Every
  query carries the hard filters: not archived, not a fork, public, pushed recently, minimum
  stars, not the user's own repositories.
- Repository discovery job (`repository_discovery`, task `repositories.generate_candidates`) with
  resumable steps queries → search → interactions → analysis → pool. It starts automatically
  after a completed profile sync or profile analysis. Repositories the user contributed to join
  as `previously_interacted`.
- Candidate provenance: `RepositoryCandidate` (one per developer and repository) and
  `CandidateDiscovery` (source, query, search rank, first/last seen).
- Filtering as its own stage: a pre-filter on search results and an eligibility check on analyzed
  data, each rejection recorded with a reason code (`archived`, `fork`, `inactive`, `no_license`,
  `few_stars`, `own_repository`, `repository_unavailable`).
- Shared repository analysis (`services/repositories/`): metadata, languages, topics, README (stored
  raw, truncated at a cap), community files (CONTRIBUTING, code of conduct, issue/PR templates),
  `good first issue` / `help wanted` labels and dependency manifests, each with its own refresh
  timestamp.
- Repository lifecycle: `discovered → fetching → analyzed → indexed → recommendable`,
  `stale → refreshing`, and `failed` with an error code. Eligibility is stored separately.
- Activity signals (`services/matching/activity.py`): days since push, commits and pull requests
  in 90 days, contributors, latest release, open issues → `RepositorySnapshot` with a label
  `recently_active | moderately_active | low_activity`. Thresholds are configuration.
- Celery beat: `mark_stale_repositories` (hourly), `process_repository_backlog` (every 15 minutes,
  app client credentials, public data only), `jobs.recover_stale_jobs` (every 5 minutes).
- `GET /api/v1/discovery/status` and `GET /api/v1/discovery/candidates` (paginated, filterable by
  source, eligibility and activity; stored data only; no score or rank).
- Profile page "Project discovery" card (state, candidate count, last updated).
- Dead-worker recovery: jobs record a heartbeat between units of work; a RUNNING job without one
  for `SYNC_STALE_AFTER_SECONDS` (default 10 minutes) is requeued, or ends as FAILED
  `worker_lost` once it has used all attempts.
- Parallel repository analysis within a discovery run (`DISCOVERY_ANALYSIS_CONCURRENCY`, default
  4 threads, each with its own GitHub client and database connection).
- Local tooling: `scripts/beat.mjs` (Celery beat), `scripts/frontend.mjs` (Vite without `npm.cmd`),
  `scripts/child.mjs` (runners kill their whole process tree and stop when `npm start` is gone),
  and `npm run stop` (kills a leftover local stack of this repository).

### Changed

- The candidate list is ordered eligible → awaiting analysis → ineligible, then previously
  interacted, best search rank and name (the order the job analyzes them), instead of by
  last-found time.
- The pool cap keeps the best candidates in analysis order and evicts the rest (previously: the
  least recently found). With `DISCOVERY_MAX_POOL` equal to `DISCOVERY_MAX_ANALYSES_PER_RUN`, the
  pool is exactly the analyzed top N.
- `SYNC_STALE_AFTER_SECONDS` default lowered from 30 to 10 minutes.
- On Windows the local Celery worker runs `--pool=threads --concurrency=4` (was `--pool=solo`),
  so discovery, syncs and backlog refreshes run side by side.
- Repository storage helpers moved from `services/github/sync.py` to `services/github/storage.py`;
  the job retry/finish loop moved to `services/jobs.run_tracked_job`.

### Fixed

- A job killed together with its worker stayed RUNNING for up to an hour (Redis visibility
  timeout), and the discovery card kept spinning.
- Redis calls had no socket timeout, so a stalled connection (a sleeping WSL distro) could hang a
  worker; `REDIS_SOCKET_TIMEOUT` (default 5 s) now applies to the cache and the broker connect.
- Repository claims were stamped with the discovery job's start time, so after 10+ minutes other
  workers saw them as abandoned. Claims now use the wall clock, and the backlog also takes over
  claims left by a dead worker.
- Flaky frontend tests: under parallel load a first render could outlast Testing Library's 1 s
  default for `findBy*`/`waitFor`. The shared setup now allows 5 s (`asyncUtilTimeout`), and
  Vitest's per-test timeout is 15 s.
- The changelog was missing its `0.2.0` heading.

### Known limitations

- Ctrl+C does not stop `npm start` in an interactive Windows console (Anaconda Prompt, cmd); use
  `npm run stop` from a second prompt. Tracked in CLAUDE.md §6 Known issues and carried to Phase 5.
- Docker Compose is still unverified (no Docker on the development machine); carried to Phase 5.
- `npm run api:sync` needs `uv` on PATH (`api:export` calls it directly).

## [0.3.0] - 2026-09-29

Phase 3: Developer profile, deterministic (OpenSpec change `phase-3-developer-profile`;
FR-PROFILE-001..005). No LLM or embedding calls.

### Added

- Skill and interest catalog (`services/profiling/taxonomy.py`, `TAXONOMY_VERSION`): 170 skills
  in 7 categories (language, framework, library, database, cloud, devops, tool) with aliases,
  GitHub language names, topics, badge/icon tokens and per-ecosystem dependency names; 16
  interests with synonyms and topics. Ambiguous words ("Go", "Rust", "Spring") only count in
  README tech sections, badges and skill icons.
- Two new sync steps:
  - `dependencies`: root manifests (requirements.txt, pyproject.toml, package.json, go.mod,
    Cargo.toml, pom.xml, build.gradle/.kts) of up to 30 recently pushed non-fork repositories,
    stored as `RepositoryDependency` names (raw files are not stored);
  - `contributions`: merged pull requests (search API) and recent public pushes to other
    people's repositories. Up to 20 of those repositories are stored with languages and topics
    and linked to the user as `contributor`. A 422 from search skips the step.
- Evidence collectors for README (sections, shields.io badges, skillicons.dev, devicon, alt
  text), repository languages, topics, dependencies, pull requests, pushes and repeated
  contributions. Every skill and interest has relational evidence rows (source, supporting
  repository, detail, observed date).
- Configurable confidence: `EVIDENCE_WEIGHTS` (SRS-1 §15 defaults) with diminishing returns per
  source and a 0.99 cap, so one README mention stays at 0.20. A system check refuses to start
  with invalid weights. Each profile records the weights and catalog version it used.
- `DeveloperProfile`: summary from fixed templates (computed signals only), language breakdown,
  default preferences, and an internal experience level (never shown or returned by the API).
- Analysis runs as the final `analysis` sync step and as a standalone `profile_analysis` job.
  `manage.py reanalyze_profiles [--user ID]` rebuilds profiles from stored data without GitHub
  calls. A failure (`analysis_failed`, not retried) keeps the previous profile.
- API: `GET /api/v1/profile` (404 `not_analyzed`), `GET /api/v1/profile/skills` (evidence,
  `?category=`), `GET /api/v1/profile/interests`.
- Frontend: `/app` is now the profile page: summary, skills grouped by category with bars labeled
  by evidence ("8 repositories · dependencies · README", never a percentage), expandable evidence
  with repository links, interests, and a Recharts languages chart (loaded lazily). Onboarding
  shows all eight steps.
- `npm run manage -- <command>` runs Django management commands without uv on PATH.
- Tests: 306 backend and 31 frontend. Verified end to end with a real account, including
  `reanalyze_profiles` on a Celery worker.

### Changed

- `GET /api/v1/profile/repositories` lists only repositories the user owns.
- Sync jobs report steps missing from older jobs as `pending`.
- `claim_job` / `finish_job` moved to `services/jobs.py` for reuse by all job types.

## [0.2.0] - 2026-09-28

Phase 2: GitHub data ingestion (OpenSpec change `phase-2-github-ingestion`; FR-GH-001..007, FR-DATA-001).

### Added

- Background GitHub sync fetches the user's profile, profile README (stored raw), public owned
  repositories (up to 100, most recently pushed), their languages (bytes) and topics into
  PostgreSQL. Later phases read this stored data instead of calling GitHub.
- GitHub client (`services/github/client.py`):
  - follows pagination (with a page cap) and uses ETag conditional requests (a 304 reuses the
    cached body);
  - handles primary and secondary rate limits (`Retry-After` / reset time) and maps errors to
    typed exceptions;
  - only follows pagination links on the API host.
- Tracked, resumable jobs (`SyncJob`): PENDING → RUNNING → COMPLETED / FAILED / RETRYING /
  CANCELLED, with per-step progress, attempt count and a safe error code.
  - A database constraint allows only one active job per user.
  - Retries never repeat completed steps.
  - Rate-limit waits and exponential backoff are capped.
  - A token rejected by GitHub (401) fails the job immediately, without retrying.
- API:
  - `POST /api/v1/profile/sync` returns 202, or 409 `github_not_connected`, or 429 `sync_cooldown`
    with `Retry-After`;
  - `GET /api/v1/sync/status`;
  - `GET /api/v1/profile/github`;
  - `GET /api/v1/profile/repositories` (paginated, `page_size` up to 100).
- The first sign-in starts a sync automatically. Disconnecting GitHub cancels any sync in progress.
- Frontend:
  - an onboarding screen with live per-step progress and messages for each failure;
  - a dashboard with profile, language breakdown, repositories, last-synced time and Refresh
    (with a cooldown message).
- Local development uses real background processing: `npm start` now also starts the WSL Redis
  service (Windows) and a Celery worker (`--pool=solo`). `REDIS_URL` defaults to
  `redis://localhost:6379/1`.
- `npm run check:version` also checks the three lockfiles.
- Tests: 142 backend and 22 frontend. Verified end to end with real GitHub: the first sync
  completed on the first attempt (~9s), and the Refresh cooldown works.

### Changed

- Custom API exceptions keep their own error code; for example `not_synced` is no longer reported
  as `not_found`.
- Logout moved into a shared signed-in layout. The disconnect text now says that synced data is
  kept until data deletion ships.

### Fixed

- Test isolation: respx routes registered outside an active mock leaked into later tests. Tests now
  use the `respx_mock` fixture, and an autouse guard resets the global router.
- `npm start` / `npm run setup` failed with "uv not found" when uv was installed via
  `pip install --user` (not on PATH) and `python` was the Microsoft Store stub. The runner now
  also checks standard install folders (`%APPDATA%\Python\Python3xx\Scripts`, `~/.local/bin`,
  `~/.cargo/bin`), accepts a `UV_BIN` override, and lists everything it tried.

### Known limitations

- Synced GitHub data is kept after disconnect until data deletion ships (FR-DATA-003, Phase 8a).
- No automatic periodic refresh yet; syncs run on first sign-in or on Refresh.
- The Docker Compose stack is still unverified (no Docker on the development machine).

## [0.1.0] - 2026-09-28

Phase 1: Foundation (OpenSpec change `phase-1-foundation`; FR-AUTH-001..003).

### Added

- Monorepo: `apps/backend` (Django 5.2, DRF, Celery) and `apps/frontend` (React 19, TypeScript,
  Vite, Tailwind v4, shadcn/ui, TanStack Query, React Router).
- GitHub sign-in through an OAuth App with no scopes (public data only). The flow uses a single-use
  `state`, and the user is matched by GitHub ID, so signing in again after disconnecting reuses the
  same user.
- GitHub access tokens are encrypted at rest (MultiFernet with key rotation). They are never
  returned to the client, and a log filter masks them as a backstop.
- Session auth with HTTP-only cookies and CSRF protection. New endpoints:
  `GET /api/v1/auth/github`, `GET /api/v1/auth/github/callback`, `GET /api/v1/auth/csrf/`,
  `GET /api/v1/auth/me`, `POST /api/v1/auth/logout`, `POST /api/v1/auth/github/disconnect`.
- Disconnect revokes the grant on GitHub and deletes the stored credential, even when the
  revocation call fails.
- Audit log for sign-in, failed sign-in, logout and disconnect. Metadata keys are allowlisted and
  client IPs are stored only as salted hashes.
- API platform:
  - every endpoint lives under `/api/v1/` and returns errors as `{"error": {code, message, details}}`;
  - unauthenticated requests get 401;
  - rate limiting returns 429 with `Retry-After`;
  - CORS allowlist and security headers;
  - `GET /api/v1/health/` checks the database and Redis;
  - OpenAPI schema at `GET /api/v1/schema/`.
- Frontend: landing page with messages for each sign-in error, a route guard, and a signed-in page
  with logout and a confirmed disconnect. API types are generated from the OpenAPI schema
  (`npm run api:sync`).
- Local development without Docker: `npm run setup` and `npm start` (Django on :8000, Vite on
  :5173) against a local PostgreSQL. Redis is optional; without it the cache is in-process, Celery
  tasks run inline, and health reports Redis as `not_configured`.
- Docker Compose stack: Postgres with pgvector, Redis, backend, Celery worker and beat, frontend.
- CI (GitHub Actions):
  - backend: ruff, strict mypy, migration check, pytest on Postgres;
  - frontend: eslint, prettier, tsc, vitest, build;
  - checks that the committed API schema matches the backend, and that the version is consistent
    across `VERSION` and the manifests.
- Tests: 60 backend and 12 frontend.

### Security

- Production settings refuse to start without `REDIS_URL` and force HTTPS, HSTS and Secure
  cookies.
- System check `core.E001` blocks startup when `TOKEN_ENCRYPTION_KEYS` is missing or invalid.

### Known limitations

- The Docker Compose stack and the Celery worker in Docker have not been verified yet (no Docker on
  the development machine). This is carried over to Phase 2.
- The API contract version (`/api/v1`, OpenAPI `1.0.0`) is versioned separately from the app
  version.
