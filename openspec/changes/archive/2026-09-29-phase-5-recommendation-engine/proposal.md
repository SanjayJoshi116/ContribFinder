## Why

Since v0.4.0 every developer has an analyzed candidate pool (repositories found for a reason, with README, community files, labels, dependencies and activity signals), but nothing turns that pool into an answer to "where should I contribute?". Phase 5 closes the core loop's MATCH and EXPLAIN steps (SRS-2 §28–32, FR-REC-001 to 006): score each candidate against the developer's evidence with versioned, configurable weights, rank the pool, explain every match from the signals that produced it, and show the result with filters. It is fully deterministic; semantic matching stays in Phase 6.

## What Changes

- **Repository technologies**: a pure function derives a repository's technology set (skills from the shared catalog, by category) from its languages (byte share), topics and dependency manifests, with the source of each detection.
- **Relevance signals** (`services/matching/`): six independent calculators, each returning a score in `0.0–1.0` plus the evidence behind it: `skill_match`, `language_match`, `framework_match`, `interest_match`, `activity_signal` and `contribution_openness`. Difficulty fit and issue fit arrive with issues in Phase 7.
- **Versioned scoring configuration**: `ScoringConfig` (version, weights, match-label bands and signal parameters, one active at a time). A migration seeds `v1-deterministic` (skill 0.40, language 0.20, interest 0.15, framework 0.10, activity 0.10, openness 0.05), marked experimental.
- **Ranking**: a weighted sum over the signals ranks the developer's eligible, recommendable candidates. The top N (default 50, at least 20) above a minimum score become `Recommendation` rows, each with its per-signal scores, match label and a non-null reference to the config that produced it. Rows are upserted per developer and repository, so ids stay stable across regenerations.
- **Explanations**: `RecommendationReason` rows (type, text, contribution weight, machine-readable detail) generated only from non-zero signals and their evidence. The match label (`strong`, `good`, `partial`) comes from the config's score bands. The API and UI never show a numeric score or a percentage.
- **Generation and freshness**: a per-user `recommendation_generation` job (no GitHub calls) runs after every completed discovery. A beat task regenerates recommendations when the profile, a pooled repository's analysis or the active config is newer than the last generation.
- **API**: `GET /api/v1/recommendations` (paginated, filterable by language, framework, activity, size and match label), `GET /api/v1/recommendations/{id}` (repository detail with README excerpt, technologies, topics, activity signals and contribution guidelines), and `GET /api/v1/recommendations/status`.
- **Frontend**: recommendation cards on the dashboard (name, owner, description, technologies, match label, reasons, activity, GitHub link), filters, and a repository detail page. Save and dismiss wait for Phase 8a.
- **Carry-overs**: Docker Compose verification, and fixing Ctrl+C for `npm start` in an interactive Windows console.

## Capabilities

### New Capabilities
- `recommendation-engine`: repository technologies, the six relevance signals, versioned scoring configuration, the weighted score, ranking and the top-N cut, the generation job, its triggers and freshness (FR-REC-001, FR-REC-002, FR-REC-004, FR-REC-005).
- `recommendation-explanations`: reason generation from signal evidence, reason types, match labels from score bands, and the rule that no reason exists without a supporting signal (FR-REC-003).
- `recommendations-view`: the recommendation list, detail and status endpoints with filters, the dashboard cards, filters and repository detail page (FR-REC-006, SRS-2 §53–56).

### Modified Capabilities
- `sync-jobs`: disconnecting GitHub also cancels an active recommendation generation job.

## Impact

- **Backend**:
  - new `recommendations` app: `ScoringConfig`, `Recommendation`, `RecommendationReason`, a seed migration, admin (config activation), API, serializers, filters and tasks;
  - `services/matching/`: repository technologies, developer and repository feature loading, the six signal calculators (`activity.py` stays);
  - `services/ranking/`: `score.py` (weighted sum, bands), `explain.py` (reasons), and the generation service;
  - `services/jobs.py`: new job type and `start_recommendations`, chained from discovery completion;
  - settings for the top-N size, minimum score, repository size thresholds and the refresh interval, plus a system check that the active config's weights are valid.
  - Migrations are additive; Phase 4 data is reused unchanged.
- **Frontend**: recommendation hooks, cards, filters, a detail route and regenerated API types.
- **GitHub API usage**: none. Scoring reads only stored data.
- **Privacy**: recommendations belong to the developer profile and are deleted with it. No new OAuth scopes.
- **Local config**: `.env` caps the pool at 10, so local runs produce at most 10 recommendations; the MVP target of 10 or more needs the pool cap raised.
