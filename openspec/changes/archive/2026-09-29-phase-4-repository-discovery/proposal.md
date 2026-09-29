## Why

Since v0.3.0 ContribFinder knows the developer (skills, interests and their evidence) but nothing about the projects they could contribute to. The recommendation engine (Phase 5) ranks a **candidate pool**: a bounded set of repositories, found for a reason, with enough analyzed data to match against. SRS-2 §18–24 asks for that pool to come from several strategies, to record why each repository entered it, to analyze each candidate and track its processing lifecycle, and to describe activity as observable signals rather than "health". This phase builds that pool deterministically (SRS-2 Phase 4, FR-REPO-001 to 004). Nothing is ranked or shown as a recommendation yet.

## What Changes

- **Query generation**: pure functions turn the developer's top skills, interests and own repository topics into GitHub repository search queries. There are four strategies (language, skill, interest, topic), and a configured per-run query budget. Every query carries the hard filters GitHub can apply (not archived, not a fork, public, pushed recently, minimum stars).
- **Candidate generation**: a new per-user `repository_discovery` job runs the queries with the user's token, stores the found repositories, and adds the repositories the user contributed to (`previously_interacted`). It runs automatically after every successful profile sync and every standalone profile analysis.
- **Candidate provenance**: `RepositoryCandidate` (one per developer and repository) plus `CandidateDiscovery` rows record each source and query that found a repository, with its search rank and dates (FR-REPO-002).
- **Filtering** as its own stage: a pre-filter on the search payload (archived, fork, push age, license, stars, the user's own repositories), and an eligibility check on the analyzed data. Rejections are recorded with a reason and counted, never silently dropped.
- **Repository analysis** (shared across users): README (stored raw, separately), community files (CONTRIBUTING, CODE_OF_CONDUCT, issue and pull request templates), `good first issue` / `help wanted` labels, languages, topics and root dependency manifests (reusing Phase 3 parsers). Each data type has its own refresh timestamp.
- **Repository lifecycle** on `Repository`: `DISCOVERED → FETCHING → ANALYZED → INDEXED → RECOMMENDABLE`, `STALE → REFRESHING`, plus `FAILED` with an error code. Eligibility is stored separately from the processing state.
- **Activity signals** (`services/matching/activity.py`): days since the last push, commits and pull requests in the last 90 days, contributor count, latest release and open issues. They are stored as a `RepositorySnapshot` with a label `recently_active | moderately_active | low_activity`. Thresholds are configuration.
- **Staleness and refresh**: Celery beat marks repositories STALE per data type, and a backlog task refreshes stale or not-yet-analyzed pool repositories in batches, using the OAuth app's client credentials (public data only, never a user's token). `npm start` runs a local beat process.
- **API**: `GET /api/v1/discovery/status` (latest discovery job, pool counts) and `GET /api/v1/discovery/candidates` (paginated; sources, eligibility, activity; filterable). Both read stored data only.
- **Frontend**: the profile page gains a small "Project discovery" card (state, number of candidate projects, last updated). There is no candidate list UI: recommendations arrive in Phase 5.

## Capabilities

### New Capabilities
- `repository-discovery`: query generation, candidate search, provenance, filtering, pool maintenance, the discovery job and its triggers, the discovery API and the profile-page card (FR-REPO-001, FR-REPO-002).
- `repository-analysis`: collection of candidate repository data, the processing lifecycle, per-data-type staleness, background refresh, failure state, and the credentials used for shared repository data (FR-REPO-003).
- `repository-activity`: activity signals, snapshots and activity labels presented as observable signals (FR-REPO-004).

### Modified Capabilities
- `sync-jobs`: a completed profile sync or profile analysis starts a repository discovery job, and disconnecting GitHub cancels every active job of the user, discovery included.

## Impact

- **Backend**:
  - `repositories` gains lifecycle, eligibility, community and per-data-type timestamp fields on `Repository`, plus `RepositoryReadme`, `RepositorySnapshot`, `RepositoryCandidate` and `CandidateDiscovery`;
  - new `services/discovery/` (queries, filters, pool, service), `services/repositories/` (analysis, lifecycle, staleness) and `services/matching/activity.py`;
  - the GitHub client gains repository search, community profile, labels, commit, pull request, contributor and release methods, and an app-credentials constructor;
  - shared repository-storage helpers move out of `services/github/sync.py`;
  - new job type `repository_discovery`, tasks `generate_candidates`, `sync_repository`, `sync_repository_readme`, `mark_stale_repositories` and `process_repository_backlog`, a beat schedule, settings plus a system check, and new endpoints.
  - Migrations are additive.
- **Frontend**: the discovery status card, a hook and regenerated API types.
- **Tooling**: `scripts/beat.mjs`, started by `npm start` when `REDIS_URL` is set.
- **GitHub API usage**: per discovery run, up to 10 search requests on the user's token (30/min search limit), plus about 10 requests per newly analyzed repository, capped at 60 repositories per run. Background refresh uses the app's own rate limit, in capped batches. ETags make refreshes cheap.
- **Privacy**: only public repository data is stored. Candidates belong to the developer profile and are deleted with it. No new OAuth scopes.
- **Carry-over**: Docker Compose verification (needs a machine with Docker) stays in this phase's task list.
