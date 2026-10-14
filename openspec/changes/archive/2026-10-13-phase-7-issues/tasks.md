## 1. Data model and settings (spec: issue-ingestion, issue-analysis, issue-matching; design D1, D10)

- [x] 1.1 Create the `issues` app with `Issue` (GitHub fields, analysis fields, unique `github_id` and (repository, number)) and `RecommendedIssue` (unique (recommendation, issue), rank, score, reasons JSON); add to `INSTALLED_APPS`; read-only admin
- [x] 1.2 Add `Repository.issues_synced_at`/`issues_truncated`, `Recommendation.relevant_issue_count`/`issue_difficulties`/`issue_contribution_types`, `RecommendationFeedback.issue` (SET_NULL)/`issue_number`, and `ReasonType` `issue_availability` and `difficulty`; generate migrations (`--settings config.settings.test`)
- [x] 1.3 Add settings `ISSUES_MAX_PAGES`, `ISSUE_BODY_MAX_CHARS`, `ISSUE_MAX_AGE_DAYS`, `ISSUE_DIFFICULTY`, `REPO_STALE_AFTER["issues"]` with env overrides, `.env.example` entries and system checks
- [x] 1.4 Tests: constraints; issues cascade with their repository (orphan deletion included); recommended issues cascade with their recommendation; feedback keeps its snapshot when the issue is deleted

## 2. GitHub client (spec: issue-ingestion; design D2)

- [x] 2.1 Add the `IssueData` dataclass and `GitHubClient.list_open_issues(full_name)` (state=open, sort=updated, `ISSUES_MAX_PAGES` cap, pull requests dropped, truncation reported, 410 as empty)
- [x] 2.2 Fixture tests (respx): normal page, pull requests filtered, pagination cap and truncation, 304 replay, 410, rate limit and 5xx handled like other calls

## 3. Issue analysis (spec: issue-analysis; design D4)

- [x] 3.1 `services/issues/labels.py`: prefix stripping, alias table → canonical categories, `ISSUE_TAXONOMY_VERSION`
- [x] 3.2 `services/issues/classify.py`: contribution type (label priority, title keywords, evidence) and difficulty (signal votes, 2-vote/no-conflict rule, thresholds from `ISSUE_DIFFICULTY`, full evidence)
- [x] 3.3 `services/issues/technologies.py`: catalog detection over title, raw labels and plain-text body with sources
- [x] 3.4 Unit tests: every alias and prefix form; each contribution-type rule and `unknown`; difficulty scenarios from the spec (beginner with support, label alone, contradicting signals) plus intermediate and advanced; technology detection incl. ambiguous words; determinism

## 4. Ingestion in repository analysis (spec: issue-ingestion, repository-analysis; design D3)

- [x] 4.1 Add the `issues` part to `PARTS`, `part_timestamps` and `stale_parts` (NULL `issues_synced_at` on an analyzed repository counts as stale)
- [x] 4.2 Fetch and store in `RepositoryAnalysisService`: upsert by `github_id`, delete issues not returned, run analysis, set `issues_synced_at`/`issues_truncated`, keep stored issues on failure
- [x] 4.3 Add task `repositories.sync_repository_issues` (app credentials, `decide_retry`) and queue it from `process_repository_backlog` when only issues are stale
- [x] 4.4 Tests: issues stored with analysis; closed issue removed on refresh; failed fetch keeps issues and records failure; issues-only refresh fetches nothing else; stale sweep marks issues-only staleness; discovery analysis of a new repository includes issues; shared across users

## 5. Matching, signals and configuration (spec: issue-matching, recommendation-engine, recommendation-explanations; design D5–D7)

- [x] 5.1 `services/ranking/config.py`: `issue_fit`/`difficulty_fit` signals, `params.issues` validation, missing weights scored as 0 for stored configs
- [x] 5.2 Seed migration `0003_seed_v2_deterministic` (frozen copy; deactivate current, activate v2)
- [x] 5.3 `services/matching/issues.py`: eligible issue loading (one query per generation), issue scoring, relevance rule, top-N per recommendation, issue reasons
- [x] 5.4 Compute `issue_fit` and `difficulty_fit` for gated candidates in generation; keep the relevance gate on skill/language/framework/interest only
- [x] 5.5 Explanations: `issue_availability` and `difficulty` templates and order
- [x] 5.6 Persist `RecommendedIssue` rows and snapshot fields in `_persist` (replace per recommendation, after dismissal filtering)
- [x] 5.7 Tests: eligibility (assigned, locked, old excluded); relevance and cap; difficulty table lookups; issue_fit saturation; difficulty_fit ignores unknown; issues alone don't make a recommendation; reasons only from non-zero parts, no percentages; v1 scores with issue weights 0; seeded configs and activation; regeneration replaces recommended issues; closed issue gone after refresh + regeneration; deterministic

## 6. API (spec: recommendations-view, issue-matching, recommendation-feedback; design D8)

- [x] 6.1 Recommendation list: `relevant_issue_count`; `difficulty` and `contribution_type` filters (400 on unknown values)
- [x] 6.2 Recommendation detail: ordered relevant issues (id, number, title, URL, labels, type, difficulty, reasons; no score)
- [x] 6.3 `GET /api/v1/issues/{id}` with GitHub/analysis sections, 404 unless relevant to one of the user's recommendations, 401 signed out
- [x] 6.4 Feedback: `issue_id` for `opened_issue` (required, must belong to the recommendation, 400 otherwise), stored with number snapshot
- [x] 6.5 Tests: shapes and status codes; filters; list query count constant with issues; another user's issue 404; no score anywhere; feedback validation and snapshot
- [x] 6.6 Regenerate the OpenAPI schema and TypeScript types (`npm run api:sync`)

## 7. Frontend (spec: recommendations-view, issue-matching; design D9)

- [x] 7.1 Relevant issue count on cards; difficulty and contribution type filters
- [x] 7.2 "Relevant issues" section on the repository detail page (empty state)
- [x] 7.3 Issue detail page `/app/issues/:id`: "From GitHub" vs "ContribFinder analysis", body as plain text, "Not enough evidence" for unknown, GitHub link recording `opened_issue`
- [x] 7.4 Tests (Vitest + RTL): card count; filters in URL; detail section and empty state; issue page sections, unknown wording, escaped body (no HTML rendered), feedback call with issue id; 404 state

## 8. Verification, docs and release

- [x] 8.1 Manual end-to-end with `npm start`: issues fetched for the pool, v2 active, regenerated recommendations show issue counts and reasons, repository detail lists issues, issue page renders, filters work, opening an issue records feedback
- [x] 8.2 Release housekeeping per CLAUDE.md §8 at archive time (v0.7.0): versions and lockfiles, CHANGELOG (ranking change under v2 noted), features.txt (Phase 7 items), README status and settings, CLAUDE.md (Phase 7 shipped, layout, deviations, carry-overs)
