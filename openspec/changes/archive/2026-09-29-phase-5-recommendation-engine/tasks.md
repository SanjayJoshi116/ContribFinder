## 1. Data model (spec: recommendation-engine, recommendation-explanations; design D1)

- [x] 1.1 Create the `recommendations` app (INSTALLED_APPS, apps.py) with `ScoringConfig` (unique `version`, `description`, `weights`, `params`, `is_active` with a partial unique constraint on `True`, `created_at`) and `clean()` calling the config validator
- [x] 1.2 Add `Recommendation` (FK profile CASCADE, FK repository CASCADE, FK config PROTECT non-null, `score`, `signal_scores`, `rank`, `match_label`, `technologies`, `activity_label`, `size`, `generated_at`; unique developer+repository; index developer+rank) and `RecommendationReason` (FK CASCADE, `type`, `text`, `weight`, `detail`, `position`)
- [x] 1.3 Add `SyncJob.JobType.RECOMMENDATION_GENERATION`. Generate migrations (`--settings config.settings.test`), plus a data migration seeding active `v1-deterministic` with the documented weights and params
- [x] 1.4 Admin: `ScoringConfig` with an "Activate" action (one active, in a transaction) and read-only weights on configs in use; read-only `Recommendation` with reasons inline and score/signals visible
- [x] 1.5 Tests: the seed exists, is active and valid; a second active config is rejected by the DB; deleting a config in use raises `ProtectedError`; recommendations and reasons cascade with the profile; unique developer+repository

## 2. Configuration (design D10)

- [x] 2.1 Add `RECOMMENDATIONS_TOP_N`, `RECOMMENDATION_MIN_SCORE`, `REPO_SIZE_THRESHOLDS`, `RECOMMENDATION_REFRESH_INTERVAL_SECONDS` and `RECOMMENDATION_README_EXCERPT_CHARS` with env overrides; add the `refresh-recommendations` beat entry; document them in `.env.example`
- [x] 2.2 Implement `services/ranking/config.py` `validate(weights, params)` (all six signals, no negatives, sum to 1 ±1e-6, bands descending in 0–1, known activity/openness keys) and extend `core/checks.py` (top N ≥ 20, min score in 0–1, size thresholds ascending). Tests for valid and invalid inputs

## 3. Matching stages (spec: recommendation-engine; design D2–D4)

- [x] 3.1 Implement `services/matching/technologies.py` `repository_technologies` (languages by byte share, topics and dependencies by configured source weights, max per slug, all sources kept, catalog category)
- [x] 3.2 Implement `services/matching/features.py`: `DeveloperFeatures` (skill confidence, category and evidence repo count; interest strengths) and `load_candidates(profile)` returning `RepoData` for eligible, recommendable candidates with a constant number of queries (prefetch languages/topics/dependencies, latest snapshot, best search rank)
- [x] 3.3 Implement `services/matching/signals.py`: `skill_match`, `language_match`, `framework_match`, `interest_match` (topics + description synonyms), `activity_signal`, `contribution_openness`, each returning a clamped, rounded value plus evidence items
- [x] 3.4 Tests: Python/Django/Celery repository technologies; empty repository gives empty technologies and zero technology signals; README-only skill counts at its low confidence; no-framework repository gives `framework_match = 0`; missing snapshot gives activity 0 with no evidence; openness sums and caps at 1; interest via topic and via description phrase; determinism; `load_candidates` skips ineligible/failed/unanalyzed repositories and its query count does not grow with the pool

## 4. Ranking and explanations (spec: recommendation-engine, recommendation-explanations; design D5, D6)

- [x] 4.1 Implement `services/ranking/score.py`: weighted score, band label, and `rank` (score desc, best search rank, full name; min score; top N)
- [x] 4.2 Implement `services/ranking/explain.py`: one reason per non-zero signal, weight `w·value`, ordered by weight, texts from fixed templates filled only from the signal's evidence, share and confidence as words (no "%"), JSON detail
- [x] 4.3 Tests: weighted sum with the seed weights; band boundaries (0.60 / 0.40 / 0.20 → strong / good / partial); tie-break by search rank then name; min score and top N cut; zero signal → no reason; reason detail only lists used evidence; ordering by weight; no "%" in any text

## 5. Generation job and freshness (spec: recommendation-engine, sync-jobs; design D7, D8)

- [x] 5.1 Implement `services/ranking/service.py` `RecommendationService(job)`: active config (none → `no_scoring_config`), features, candidates, signals, score, rank, explain, heartbeat, and one transaction that upserts by developer+repository, deletes the rest and replaces reasons; metadata counts
- [x] 5.2 Add task `recommendations.generate_recommendations(job_id)` via `run_tracked_job`, `start_recommendations(user)` and `start_recommendations_after(job)`; chain it from discovery completion; map the job type in `recover_stale_jobs`
- [x] 5.3 Add beat task `recommendations.refresh_recommendations`: start a job for profiles with a pool and no completed generation, or whose profile analysis, latest pooled repository lifecycle change or config is newer/different than the last generation
- [x] 5.4 Tests: end-to-end generation stores ranked recommendations with the config FK, labels and reasons; regeneration keeps ids of kept repositories and drops the rest; failure during write keeps the previous set; cancellation (disconnect) keeps the previous set; no eligible candidates → completed job, no recommendations; discovery completion starts a generation job and an active one is not duplicated; freshness starts jobs for a refreshed repository, a newer profile and a newly activated config, and not when nothing changed; no GitHub request is made (respx)

## 6. API (spec: recommendations-view; design D9)

- [x] 6.1 Implement `GET /api/v1/recommendations` (rank order, pagination, serializer without score/rank/signals, technologies with `matched`, reasons, activity, size, openness facts) and the filters `language`, `framework`, `activity`, `size`, `match` with 400 on unknown values
- [x] 6.2 Implement `GET /api/v1/recommendations/{id}` (language breakdown, plain-text README excerpt, contribution facts, snapshot signals; 404 for others) and `GET /api/v1/recommendations/status`
- [x] 6.3 Tests: shape and no score/rank fields; rank order; each filter and combined filters; invalid filter value → 400 envelope; detail with and without README; 404 for another user's id; status never-generated and after generation; 401 signed out; constant query count; no GitHub request
- [x] 6.4 Regenerate the OpenAPI schema and TypeScript types (`npm run api:sync`)

## 7. Frontend (spec: recommendations-view; design D11)

- [x] 7.1 Add `useRecommendations(filters)`, `useRecommendation(id)` and `useRecommendationStatus()` (polls while a job is active; invalidates the list when it completes)
- [x] 7.2 Add `RecommendationCard` and `RecommendationList` with URL-backed filters (language, framework, activity, size, match), pagination, and generating/empty states on `/app`
- [x] 7.3 Add route `/app/recommendations/:id` with `RecommendationDetailPage` separating "From GitHub" from "ContribFinder analysis"; unavailable README/signals shown as unavailable
- [x] 7.4 Tests (Vitest + RTL): card shows label text, top reasons, technologies, activity text and GitHub link; no "%" anywhere; filter updates the URL and the list; generating → list without reload; empty state; detail page sections and no-README state

## 8. Carry-overs, verification, docs and release

- [ ] 8.1 Ctrl+C carry-over (still open 2026-09-29: repeated Ctrl+C in Anaconda Prompt stops nothing, not even the top process; carried to the next phase): run the per-runner bisect from CLAUDE.md §6 Known issues, fix the runner that breaks console Ctrl+C, verify with a real Ctrl+C in an interactive console, and update or close the Known issues entry
- [x] 8.2 Docker carry-over: moved to future scope (decision 2026-09-29); `docker compose up` verification waits for a machine with Docker
- [x] 8.3 Manual end-to-end with `npm start`: after discovery completes, recommendations appear on the dashboard with labels and reasons; filters work; the detail page renders; activating a new config regenerates on the next freshness run
- [x] 8.4 Release housekeeping per CLAUDE.md §8 at archive time (v0.5.0): versions and lockfiles, CHANGELOG, features.txt, README status, CLAUDE.md (Phase 5 shipped, layout, deviations, carry-overs)
