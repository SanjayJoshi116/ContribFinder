## Context

See proposal.md (Why). Current state that shapes the approach:

- `services/github/client.py` has no issue listing. `_paginate` follows `Link` headers with a page cap and reports truncation. `_get` does ETag conditional requests cached under `github:etag:{scope}:…` (24 h). `search_merged_pull_requests` is the only `/search/issues` caller.
- `RepositoryAnalysisService.run(repo_id, parts)` fetches and stores per data type (`PARTS = metadata, readme, community, dependencies, activity`), with `stale_parts()` driven by `REPO_STALE_AFTER` (hours). Labels are fetched as names only, and just two booleans are stored (`has_good_first_issue_label`, `has_help_wanted_label`). Discovery runs this service in-process with the user's token and `PUBLIC_SCOPE`; the background backlog uses `GitHubClient.for_app()` and queues `sync_repository` or `sync_repository_readme`.
- `services/matching/signals.compute()` returns six signals. `services/ranking/config.validate()` requires exactly those six keys. `Recommendation.signal_scores` is JSON, so the signal set can grow without a column change. `RecommendationReason.type` is `max_length=20`.
- Freshness (`services/ranking/freshness.py`) regenerates when `candidates__repository__lifecycle_changed_at` is newer than the last generation, or when the active config changed.
- `DeveloperProfile.experience_level` (beginner, intermediate, experienced, unknown) is computed and internal. `preferred_issue_difficulty` is never computed and stays `unknown`.
- Free-text skill detection exists: `services/profiling/text.PhraseMatcher` plus `plain_text()` over the skill catalog with its ambiguous-word rules.
- `FeedbackAction.OPENED_ISSUE` exists, but the event has no issue reference and the frontend never sends it.

## Goals / Non-Goals

**Goals:**
- Issues behave like every other repository data type: shared, fetched in the background, with per-type freshness, and failures recorded as state.
- Issue analysis is a pure, separately tested stage (labels → type → difficulty → technologies). Issue matching is a separate stage inside generation, feeding two ordinary signals.
- All new numbers (issue weights, thresholds, difficulty table) live in the versioned `ScoringConfig` or in settings. None are constants in code.

**Non-Goals:**
- LLM or embedding classification, and semantic issue matching (Phase 6).
- A global issue feed or `GET /issues` list, issue search, and notifications about new issues.
- Setting `preferred_issue_difficulty` from the UI. Difficulty fit uses the internal experience level.
- Linked pull requests, issue timelines, reactions, maintainer response times, and comment bodies.
- Issues of repositories that are not in any pool.

## Decisions

### D1. Data model (new `issues` app)
- `Issue` fields:
  - `repository` FK (CASCADE), `github_id` (unique), `number`; unique (repository, number);
  - from GitHub: `title`, `body` (plain text, truncated to `ISSUE_BODY_MAX_CHARS`), `raw_labels` (JSON list of names), `state`, `is_locked`, `has_assignee`, `comments`, `html_url`, `github_created_at`, `github_updated_at`;
  - analysis: `labels` (JSON list of canonical categories), `contribution_type` with `contribution_type_evidence`, `difficulty` with `difficulty_evidence`, `technologies` (JSON `[{slug, source}]`), `analyzed_at`.
- Analysis results sit on the issue row itself, not in a separate table: they are 1:1 and recomputed with each fetch.
- `RecommendedIssue`: `recommendation` FK (CASCADE), `issue` FK (CASCADE), `rank`, `score` (internal), `reasons` (JSON list of `{type, text, detail}`); unique (recommendation, issue).
  - Why JSON reasons rather than reusing `RecommendationReason`: issue reasons are read only with their issue and never filtered. A table would double the write volume per generation for no query benefit.
- `Recommendation` gains snapshot fields: `relevant_issue_count`, `issue_difficulties` (JSON list of distinct values) and `issue_contribution_types` (JSON list). This mirrors the existing `technologies`/`activity_label`/`size` snapshots, so the filters stay single-table `__contains` lookups and the list query count stays constant.
- `Repository` gains `issues_synced_at` and `issues_truncated`.
- `RecommendationFeedback` gains `issue` FK (`SET_NULL`, nullable) and `issue_number` (snapshot).

### D2. Fetching (`GitHubClient.list_open_issues`)
- Calls `GET /repos/{full_name}/issues?state=open&sort=updated&direction=desc&per_page=100` through `_paginate` with `max_pages=ISSUES_MAX_PAGES` (default 1). Returns `Page[IssueData]`.
  - Items carrying a `pull_request` key are dropped.
  - `IssueData` is a frozen dataclass normalized from the API (label names only, `assignee`/`assignees` collapsed to `has_assignee`).
- Why one "most recently updated" page instead of per-label queries (`labels=good first issue`): label names vary by repository (we only know normalized presence), the labels filter is AND-only, and recency already correlates with relevance. Alternative kept for later: one extra page filtered by the repository's actual good-first-issue label name.
- The ETag cache makes unchanged refreshes cost a conditional 304.

### D3. Issues as an analysis part
- `PARTS` gains `issues`. `part_timestamps` maps it to `issues_synced_at`. `REPO_STALE_AFTER["issues"] = 6` (hours).
- `RepositoryAnalysisService` fetches the page and stores it in one transaction:
  - upsert by `github_id`;
  - delete the repository's issues not in the fetched set;
  - run issue analysis (D4) on the stored rows;
  - set `issues_synced_at` and `issues_truncated`.
- A fetch error follows the existing per-part handling: the stored issues are untouched and the lifecycle records the failure. A 410 (issues disabled) counts as an empty set.
- Backlog: `process_repository_backlog` queues the new `repositories.sync_repository_issues(repo_id)` when the stale parts are only `["issues"]`, like the README-only path. Otherwise `sync_repository` includes issues.
  - The task uses `for_app()` and the same `decide_retry` translation.
- Discovery's analysis step needs no change: never-analyzed repositories get all `PARTS`.
- Completing a refresh updates `lifecycle_changed_at`, so the existing freshness sweep picks up issue changes without new logic.

### D4. Issue analysis (`services/issues/`)
Pure functions over an `IssueInput` dataclass, unit-tested without a database.
- **`labels.normalize(raw) -> list[str]`**:
  - strip a scope prefix matching `^[a-z ]{1,20}[:/]\s*` (`type:`, `kind/`, `area/`, `good first issue` untouched);
  - apply the existing `normalize_label` (lowercase; spaces, hyphens and underscores collapsed);
  - look up an alias table → canonical category. The table is a module constant, versioned by `ISSUE_TAXONOMY_VERSION`, like the skill catalog: it is a catalog, not a weight.
- **`classify.contribution_type(labels, title)`**:
  - label priority: `bug`→`bug_fix`, `documentation`, `testing`, `infrastructure`→`devops`, `design`, `enhancement`→`feature`, then `refactoring|performance|security|frontend|backend`→`code`;
  - then title keyword rules (`docs`, `readme`, `typo` → documentation; `test`, `coverage` → testing; `ci`, `docker`, `workflow` → devops; `bug`, `crash`, `error`, `fails` → bug_fix; `bug` covers the common `[Bug]:` title prefix);
  - otherwise `unknown`. Evidence is `{"by": "label"|"keyword", "value": …}`.
- **`classify.difficulty(...)`**: each signal votes `beginner`, `intermediate`, `advanced` or abstains.
  - difficulty labels (beginner: `good_first_issue` category, `easy`, `beginner`, `starter`; intermediate: `medium`, `intermediate`; advanced: `hard`, `complex`, `expert`);
  - body length (beginner under `short_body`, advanced over `long_body`; an empty body abstains);
  - technology count (beginner = 1, intermediate 2 to `many_technologies` − 1, advanced ≥ `many_technologies`; none abstains). Without the intermediate vote only a label could point to intermediate, so it could never win;
  - contribution type (documentation votes beginner);
  - comments (advanced ≥ `long_discussion`).
  - Rule: a level wins when it has at least 2 votes and no other level has any. Otherwise the result is `unknown`.
  - Thresholds come from settings `ISSUE_DIFFICULTY` (`short_body` 600, `long_body` 4000, `many_technologies` 3, `long_discussion` 15).
  - The stored evidence lists every vote and abstention.
  - Why votes over a weighted score: the spec forbids a label alone deciding, and a 2-vote/no-conflict rule is easy to explain and test. A score would hide that.
- **`technologies.detect(title, labels, body)`**: `PhraseMatcher` over the skill catalog with the existing ambiguous-word rules, run on title, raw labels and `plain_text(body)`, keeping the first source per slug. Markup (HTML, CSS) is excluded: almost every web issue mentions it, so it would inflate technology matches and the difficulty technology count (found in manual testing).

### D5. Issue matching (`services/matching/issues.py`)
Runs inside `RecommendationService` after the repository signals are computed for each kept candidate, and before persistence.
- Load eligible issues: open, `not is_locked`, `not has_assignee`, `github_updated_at` ≥ now − `ISSUE_MAX_AGE_DAYS` (365). Use one query for all candidate repositories (`repository_id__in`), grouped in Python.
- Score each issue = `w_tech·tech + w_diff·diff_fit + w_appr·approach`, with weights from the active config's `params.issues.weights` (v2: 0.6, 0.25, 0.15).
  - `tech`: confidence-weighted share of the issue's technologies the developer has, reusing the skill-confidence lookup from `features`.
  - `diff_fit`: `params.issues.difficulty_fit[experience_level][difficulty]`.
  - `approach`: `params.issues.approachability` of the issue's best label (v2: 1.0 with `good_first_issue`, 0.6 with only `help_wanted`), else 0.
- Relevant means score ≥ `params.issues.min_score` (0.3) and (`tech` > 0 or `approach` > 0). Keep the top `params.issues.per_recommendation` (5), ordered by score, then `github_updated_at` descending, then number.
- Repository signals:
  - `issue_fit = min(1, Σ relevant scores / params.issues.saturation)` (saturation 3.0). Evidence: count and counts by contribution type.
  - `difficulty_fit = max(diff_fit over relevant issues with known difficulty)`, or 0. Evidence: counts by difficulty plus the experience level used (internal, never serialized).
- Issue reasons are built from the non-zero parts: matched technologies, the difficulty estimate and its fit, approachability labels.
- Signal order matters: the relevance gate (skill/language/framework/interest > 0) is evaluated first. Issue matching runs only for candidates that pass the gate, which bounds the work by top N.

### D6. Scoring configuration v2
- `SIGNALS` gains `issue_fit` and `difficulty_fit`.
- `validate()` checks the new eight-signal shape and a `params.issues` block (weights sum to 1; `min_score` in [0,1]; `per_recommendation` ≥ 1; `saturation` > 0; `approachability` values for `good_first_issue` and `help_wanted` in [0,1]; a complete difficulty table for 4 experience levels × 4 difficulties, values in [0,1]).
- Stored configs are not re-validated. `score()` treats a missing weight as 0, so `v1-deterministic` keeps working if re-activated, and skips issue matching when `params.issues` is absent.
- Seed migration `recommendations/0003_seed_v2_deterministic` holds a frozen copy:
  - weights skill 0.35, language 0.15, interest 0.15, framework 0.10, activity 0.10, openness 0.05, issue_fit 0.05, difficulty_fit 0.05; v1's bands and params plus `issues`;
  - deactivates the current active config and activates v2 in the same migration (the partial unique constraint requires that order).
  - Why activate on migrate: the spec requires it, and the freshness sweep's "outdated config" rule then regenerates everyone without a manual step.
- Difficulty table (rows = experience level):

  | | beginner | intermediate | advanced | unknown |
  |---|---|---|---|---|
  | beginner | 1.0 | 0.5 | 0.0 | 0.3 |
  | intermediate | 0.7 | 1.0 | 0.5 | 0.4 |
  | experienced | 0.4 | 0.8 | 1.0 | 0.5 |
  | unknown | 0.8 | 0.7 | 0.4 | 0.4 |

### D7. Explanations
- `ReasonType` gains `issue_availability` (18 characters; fits `max_length=20`) and `difficulty`.
- `explain.ORDER` and `TEMPLATES` gain both:
  - `issue_availability`, for example "3 open issues match your skills, including 1 documentation issue";
  - `difficulty`, for example "Some issues look beginner-level (estimated)".
- Texts avoid numbers other than counts and never mention experience level.

### D8. Persistence and API
- `_persist` (one transaction) upserts recommendations as today. It then replaces each recommendation's `RecommendedIssue` rows (delete + bulk create) and writes the three snapshot fields. Dismissed repositories are dropped before this, as today.
- `GET /recommendations`:
  - items add `relevant_issue_count`;
  - filters `difficulty` (`issue_difficulties__contains=[value]`) and `contribution_type` (`issue_contribution_types__contains=[value]`) use `ChoiceFilter` so unknown values give 400.
- `GET /recommendations/{id}` adds `issues` (`prefetch_related` of `recommended_issues__issue`, ordered by rank).
- `GET /api/v1/issues/{id}` (new `issues/api.py`): looks up `RecommendedIssue` with `issue_id=id, recommendation__developer__user=request.user` and takes the first by rank. Returns 404 when there is none. The serializer nests `github` and `analysis` objects.
- Feedback: `FeedbackRequest` gains optional `issue_id`. It is required for `opened_issue` and must match a `RecommendedIssue` of that recommendation (400 otherwise). `record()` stores the issue and its number.
- Everything is declared for drf-spectacular. Types are regenerated with `npm run api:sync`.

### D9. Frontend
- Card: "N relevant issues" chip when N > 0.
- `RecommendationDetailPage`: a "Relevant issues" section with title, contribution type, estimated difficulty and top reason, each linking to `/app/issues/:id`. It goes under ContribFinder analysis, because the selection is analysis.
- New `features/issues/IssueDetailPage.tsx` at `/app/issues/:id` (inside `RequireAuth`):
  - two regions, "From GitHub" and "ContribFinder analysis";
  - the body is rendered in a `<pre className="whitespace-pre-wrap">`-style block as text (React escapes it; no markdown or HTML rendering);
  - `unknown` is shown as "Not enough evidence";
  - the GitHub link calls `recordFeedback(recId, 'opened_issue', {issue_id})` with keepalive.
- Filters: `FILTER_KEYS` gains `difficulty` and `contribution_type`, with labels from the spec lists.

### D10. Settings
`ISSUES_MAX_PAGES` (1), `ISSUE_BODY_MAX_CHARS` (10000), `ISSUE_MAX_AGE_DAYS` (365), `ISSUE_DIFFICULTY` (JSON thresholds) and `REPO_STALE_AFTER["issues"]` (6). Each has an env override, an `.env.example` entry and a system check (positive values, complete threshold keys).

## Risks / Trade-offs

- **[GitHub request volume: every pooled repository refreshes issues every 6 h]** → One conditional request per repository (304 when unchanged), batched by the existing backlog (50 per 15 minutes), on the app's credentials. The interval is configurable.
- **[Regeneration churn: issue refreshes bump `lifecycle_changed_at`, so users regenerate about every 6 h]** → Generation reads stored data only and is fast. The beat sweep already runs every 30 minutes. Acceptable at current scale; revisit if the generation count grows.
- **[One page of recent issues misses older good-first issues in big repositories]** → Truncation is recorded. Per-label fetching is the documented next step (D2).
- **[Rule-based difficulty is often `unknown`]** → This is intended by the spec. `unknown` contributes nothing to `difficulty_fit` and a neutral value to issue scores, and the UI says "Not enough evidence".
- **[Label alias table drift across ecosystems]** → It is a versioned catalog with tests per alias. Unknown labels are kept raw, so nothing is lost.
- **[Issue bodies are untrusted user content]** → Stored and served as plain text, rendered escaped, never as HTML. Length is capped.
- **[Ranking changes for every user when v2 activates]** → Expected. Weights are marked experimental. v1 stays stored and can be re-activated from the admin. Phase 8b evaluation decides future weights.

## Migration Plan

1. Additive migrations:
   - the `issues` app tables;
   - `Repository.issues_synced_at`/`issues_truncated`;
   - the `Recommendation` snapshot fields (defaults 0 / `[]`);
   - `RecommendationFeedback.issue`/`issue_number`;
   - then the v2 seed migration that activates v2.
2. Deploy the backend, then the frontend (regenerated types).
3. Existing repositories have `issues_synced_at = NULL`, so `stale_parts` reports issues as stale. The hourly stale sweep marks them, and the backlog fetches issues over the next runs. Until then the issue signals are 0 and nothing breaks.
4. Rollback: re-activate `v1-deterministic` in the admin and revert the frontend. The new tables and columns can stay.
