## Why

Since v0.6.0 ContribFinder recommends repositories but stops short of the question a developer actually has next: *what could I work on there?* Repository analysis only records whether a `good first issue` or `help wanted` label exists, so recommendations cannot point at concrete issues, say how hard they look, or filter by difficulty or contribution type. SRS-2 §25–27, §57 and FR-ISSUE-001 to 005 (Phase 7, MVP+) close this gap, and the `difficulty` and `issue_availability` reason types and the `opened_issue` feedback action have been waiting for it since Phases 5 and 8a.

## What Changes

- **Issue ingestion (FR-ISSUE-001)**: repository analysis gains an `issues` part that fetches a capped page of each pooled repository's most recently updated open issues through `GitHubClient.list_open_issues` (pull requests filtered out), stores them in a new `issues` app (`Issue`), and refreshes them on their own, shorter staleness interval (`REPO_STALE_AFTER["issues"]`, hours). Issues that are closed or no longer returned are removed. Task `repositories.sync_repository_issues` refreshes issues only.
- **Label normalization (FR-ISSUE-002)**: raw label names are kept as GitHub sent them and mapped, through an alias table with prefix stripping (`type: bug`, `kind/docs`, `area/frontend`), to canonical categories: good first issue, help wanted, documentation, bug, enhancement, refactoring, testing, frontend, backend, performance, security, infrastructure, design.
- **Contribution type (FR-ISSUE-003)**: each issue gets one of `code, documentation, testing, bug_fix, feature, devops, design` from label rules first and title keywords second, or `unknown` when no rule applies.
- **Difficulty (FR-ISSUE-004)**: each issue gets `beginner, intermediate, advanced` or `unknown`, derived from several recorded signals (labels, description length, number of technologies mentioned, contribution type, discussion size). A label alone never decides it; without enough agreeing evidence the result is `unknown`. Every classification stores the evidence it used.
- **Issue technologies**: the existing skill catalog detects technologies named in an issue's title, labels and body, the same way it does for repositories.
- **Issue matching and evidence (FR-ISSUE-005)**: during recommendation generation, each recommended repository's eligible issues (open, unassigned, unlocked, recently updated) are scored against the developer: technology overlap, difficulty fit with the internal experience level, and beginner/help-wanted signals. The best few are stored as `RecommendedIssue` rows with reasons built only from those signals.
- **Two new repository signals**: `issue_fit` (relevant issues are available) and `difficulty_fit` (their difficulty suits the developer), with reason types `issue_availability` and `difficulty`. They ship in a new scoring configuration `v2-deterministic` that becomes active; `v1-deterministic` stays unchanged for history.
- **API**: recommendation list items gain `relevant_issue_count`; the recommendation detail gains its relevant issues; new `GET /api/v1/issues/{id}` returns one relevant issue, separating GitHub data from ContribFinder analysis, for the requesting user's own recommendations only. New filters `difficulty` and `contribution_type` on `GET /api/v1/recommendations`.
- **Frontend**: the relevant issue count on cards, a "Relevant issues" section on the repository detail page, an issue detail page (`/app/issues/:id`) that separates "From GitHub" from "ContribFinder analysis", the two new filters, and `opened_issue` feedback when an issue is opened on GitHub.
- **Feedback**: `opened_issue` events record which issue was opened (nullable reference plus a number snapshot).
- No LLM or embedding calls: classification is deterministic and rule-based (AI classification stays behind future Phase 6 interfaces).

## Capabilities

### New Capabilities
- `issue-ingestion`: fetching, filtering, storing and refreshing repository issues, and removing closed ones (FR-ISSUE-001).
- `issue-analysis`: label normalization, contribution type, difficulty with evidence, and issue technologies (FR-ISSUE-002 to 004).
- `issue-matching`: per-developer issue relevance, recommended issues with reasons, the issue detail endpoint and page (FR-ISSUE-005).

### Modified Capabilities
- `repository-analysis`: issues become an analysis part with their own freshness interval and refresh task.
- `recommendation-engine`: two new relevance signals (`issue_fit`, `difficulty_fit`) and the `v2-deterministic` configuration.
- `recommendation-explanations`: reason types `issue_availability` and `difficulty`.
- `recommendations-view`: relevant issue count and issues on list and detail, `difficulty` and `contribution_type` filters, the "Relevant issues" section on the repository detail page.
- `recommendation-feedback`: `opened_issue` events reference the issue.

## Impact

- **Backend**:
  - new `issues` app: `Issue` (shared, cascades with its repository) and `RecommendedIssue` (cascades with its recommendation); migrations are additive;
  - `services/github/client.py`: `list_open_issues` and an `IssueData` dataclass;
  - `services/repositories/`: `issues` part in analysis and staleness; `repositories.sync_repository_issues` task; backlog refresh queues it when only issues are stale;
  - new `services/issues/`: `labels` (normalization), `classify` (contribution type, difficulty), `technologies`;
  - `services/matching/`: issue scoring and the two new signals; `services/ranking/`: config keys, explanations, persistence of recommended issues and filter snapshots on `Recommendation`;
  - `recommendations` and new `issues` API; `feedback` gains a nullable issue reference.
- **Frontend**: cards, repository detail, new issue detail route, filters, feedback; API types regenerated.
- **GitHub API usage**: one extra request per pooled repository per issue refresh (one page of 100 by default), on the same client, cache and retry rules as other analysis parts.
- **Ranking**: a new active scoring configuration changes scores and order; the freshness sweep regenerates every user's recommendations once.
- **Privacy**: issues are public repository data, shared across users and removed with their repository; no new per-user data besides recommended issues and the issue reference on feedback, both covered by existing deletion.
