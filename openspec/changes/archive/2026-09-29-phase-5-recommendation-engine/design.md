## Context

See proposal.md for motivation. State this design builds on (v0.4.0):

- Each `DeveloperProfile` has `DeveloperSkill` (catalog `Skill` with `category`, `confidence` 0–1, `SkillEvidence` rows) and `DeveloperInterest` (`strength` 0–1, evidence). README-only skills sit at ≈0.20.
- Each developer has a pool of `RepositoryCandidate`s (`CandidateDiscovery` gives source and search rank). Shared `Repository` rows carry `lifecycle`, `is_eligible`, community flags (`has_contributing`, `has_code_of_conduct`, `has_issue_templates`, `has_pull_request_template`, `has_good_first_issue_label`, `has_help_wanted_label`), `RepositoryLanguage` (bytes), `RepositoryTopic`, `RepositoryDependency`, `RepositoryReadme` and `RepositorySnapshot` (activity signals and label).
- The catalog (`services/profiling/taxonomy.py`) already maps linguist languages, topics and dependencies to skill slugs (`skill_for_linguist`, `skill_for_topic`, `skill_for_dependency`), and topics and synonym phrases to interests (`interest_for_topic`, `interests.SYNONYM_MATCHER`).
- Jobs run through `services/jobs.run_tracked_job` with heartbeat, retries and recovery; job types are `SyncJob.JobType`, one active job per user and type (DB constraint). Discovery completion has no follow-up hook yet.
- `recommendations/` and `services/ranking/` do not exist yet; `services/matching/` holds only `activity.py`.
- Local `.env` caps the pool at 10 candidates.

Constraints (CLAUDE.md §3): separate, testable stages; deterministic scoring; weights as versioned configuration; no LLM or embedding calls; HTTP requests read PostgreSQL only; never show a percentage or "87% match".

## Goals / Non-Goals

**Goals:**
- Pure, independently testable stages: technologies → features → signals → score → rank → explain → persist.
- Every stored number traceable: per-signal values, the config version, and reasons whose detail lists the evidence used.
- Regeneration is cheap (no GitHub), idempotent, atomic and keeps recommendation ids stable for Phase 8a feedback and saves.

**Non-Goals:**
- Difficulty fit, issue fit, issue counts and the difficulty/contribution-type filters (Phase 7).
- Semantic similarity and embeddings (Phase 6).
- Save, dismiss, view tracking and feedback (Phase 8a). Cards reserve space but show no Save button.
- Recommendation history. Only the current set is stored; the config reference covers FR-REC-005.
- Offline evaluation metrics (Phase 8b), though the pure signal functions are built so a benchmark can call them.
- Per-user weights.

## Decisions

### D1. Data model (new `recommendations` app)

- `ScoringConfig`: `version` (unique slug), `description`, `weights` JSON `{signal: float}`, `params` JSON (bands, activity values, openness points, technology source weights), `is_active` (partial unique constraint: at most one `True`), `created_at`. `clean()` validates via `services/ranking/config.validate(weights, params)`: every signal present, no negatives, weights sum to 1 (±1e-6), bands descending in 0–1.
- `Recommendation`: FK `DeveloperProfile` (CASCADE), FK `Repository` (CASCADE), FK `ScoringConfig` (**PROTECT**, non-null), `score` float, `signal_scores` JSON `{signal: float}`, `rank` int, `match_label` (`strong|good|partial`), `technologies` JSON `[{slug, name, category, matched}]`, `activity_label` (blank when the repository has no snapshot), `size` (`small|medium|large|unknown`), `generated_at`. Unique `(developer, repository)`; index `(developer, rank)`.
- `RecommendationReason`: FK `Recommendation` (CASCADE), `type` (`skill|language|framework|interest|activity|openness`), `text`, `weight` (the signal's contribution `w·s`), `detail` JSON, `position`. Ordered by `position`.
- Why JSON for `signal_scores` rather than one column per signal (the SRS-1 sketch): signal sets change with config versions (semantic in Phase 6, difficulty/issue in Phase 7) without schema churn, and nothing filters on individual signal values.
- Why denormalize `technologies`, `activity_label` and `size` onto `Recommendation`: the list filters must not recompute technologies per request. They are snapshots of the generation, refreshed with it. `technologies` uses jsonb containment (`technologies__contains=[{"slug": "django"}]`).
- Seed migration creates `v1-deterministic` (active): weights skill 0.40, language 0.20, interest 0.15, framework 0.10, activity 0.10, openness 0.05; `params`: bands `{strong: 0.55, good: 0.35}`, activity `{recently_active: 1.0, moderately_active: 0.6, low_activity: 0.2}`, openness `{contributing: 0.4, good_first_issue: 0.3, help_wanted: 0.2, issue_templates: 0.1}`, tech sources `{dependency: 1.0, topic: 0.6}` (languages use their byte share). Description says the numbers are experimental.
- New job type `recommendation_generation` (migration in `jobs`).

### D2. Repository technologies (`services/matching/technologies.py`, pure)

`repository_technologies(RepoData) -> dict[slug, Tech(slug, category, weight, sources, share)]`:
- languages: `skill_for_linguist(lang)`, weight = byte share of the repository (markup included in the denominator so share is honest);
- topics: `skill_for_topic`, weight `params.tech_sources.topic`;
- dependencies: `skill_for_dependency(ecosystem, name)`, weight `params.tech_sources.dependency`;
- one entry per slug; weight = max over sources; `sources` keeps every source.

Category comes from the catalog. The same function feeds the signals, the stored `technologies` and the API.

### D3. Features (`services/matching/features.py`)

- `DeveloperFeatures`: `{slug: (confidence, category, repo_count)}` from `DeveloperSkill` plus evidence counts; `{interest_slug: strength}`. Loaded once per generation.
- `RepoData` (frozen dataclass): id, full name, description, languages, topics, dependencies, community flags, latest snapshot (or None), best search rank. `load_candidates(profile)` builds them with a fixed number of queries: candidates filtered to `repository__lifecycle=recommendable, repository__is_eligible=True`, `prefetch_related` languages, topics and dependencies, the latest snapshot through a `Prefetch` ordered by `-captured_at`, and `Min("discoveries__search_rank")`.
- Loading is the only DB-touching part of matching; everything after it is pure.

### D4. Signals (`services/matching/signals.py`, pure)

Each returns `Signal(value: float, evidence: tuple[EvidenceItem, ...])`; `c(s)` is the developer's confidence (0 if absent), `T` the repository technologies with weights `w(s)`:

| Signal | Formula | Evidence |
|---|---|---|
| `skill_match` | `Σ_T w(s)·c(s) / Σ_T w(s)` | matched skills (slug, confidence, sources), top 5 by `w·c` |
| `language_match` | `Σ_lang share(l)·c(l)` over language technologies | languages with share and confidence |
| `framework_match` | noisy-OR `1 − Π(1 − c(f))` over matched frameworks; 0 when the repository has none | matched frameworks with the developer's repo count |
| `interest_match` | noisy-OR over matched interests' strengths; repository interests from `interest_for_topic` on topics and `SYNONYM_MATCHER` on the description | interest slug, matched topic or phrase |
| `activity_signal` | `params.activity[label]`, 0 without a snapshot | label, days since push, commits 90d |
| `contribution_openness` | `min(1, Σ params.openness[flag])` over true flags | present flags |

- Why noisy-OR for frameworks and interests: one strong match ("uses Django, which you use") is meaningful by itself; averaging would punish repositories that also use unrelated frameworks. `skill_match` is the coverage-style counterweight.
- Why `framework_match = 0` without frameworks rather than renormalizing weights: renormalizing makes scores incomparable across repositories and configs. The 0.10 weight bounds the effect (see Risks).
- Values are clamped to 0–1 and rounded to 4 decimals so scores are stable across platforms.

### D5. Score, bands and ranking (`services/ranking/score.py`, pure)

- `score = Σ weights[k] · signal[k].value`.
- `label = strong if score ≥ bands.strong, good if ≥ bands.good, else partial`.
- `rank(scored)`: keep candidates with `score ≥ RECOMMENDATION_MIN_SCORE` and at least one relevance signal (skill, language, framework, interest) above 0; sort by `(-score, best_search_rank or ∞, full_name)`; take `RECOMMENDATIONS_TOP_N`.
- Why the relevance gate: activity (0.10) plus openness (0.05) alone can reach the minimum score, which would recommend an active project in a stack the developer never used. They describe the repository, not the fit, so they order relevant candidates but never qualify one (found while implementing).

### D6. Explanations (`services/ranking/explain.py`, pure)

- One reason per signal with `value > 0`, `weight = w·value`, ordered by weight. Text comes from fixed templates filled only from that signal's evidence, for example:
  - language: "Written mainly in Python, one of your strongest languages" (share ≥ 0.5 → "mainly", ≥ 0.2 → "partly"; confidence ≥ 0.7 → "one of your strongest languages", ≥ 0.4 → "a language you use", else "a language you have touched");
  - framework: "Uses Django and Celery, which appear in 5 of your repositories";
  - skill: "Shares PostgreSQL, Redis and Docker with your profile";
  - interest: "Matches your interest in developer tooling (topic: developer-tools)";
  - activity: "Recently active: last push 3 days ago, 42 commits in 90 days";
  - openness: "Has a contributing guide and a good first issue label".
- No percentages in texts (the UI tests assert that no "%" renders); shares become words.
- `detail` holds the evidence items as JSON (slugs, names, shares, counts) so the frontend can render chips without parsing text.

### D7. Generation service and job (`services/ranking/service.py`)

- `RecommendationService(job).run()`: load the active config (none → `PermanentJobError("no_scoring_config")`), features and candidates, compute signals, score, rank and explain in memory, heartbeat, then persist in **one transaction**:
  - `select_for_update` the developer's existing recommendations;
  - upsert the top N by `(developer, repository)` (ids stay stable);
  - delete the developer's other recommendations;
  - replace the reasons of the kept ones (delete + `bulk_create`).
- A failure before commit leaves the previous set (spec: failure keeps old results). A cancellation is detected by heartbeat before the transaction; the transaction re-checks the job is still RUNNING.
- Metadata: `candidates`, `scored`, `kept`, `config_version`, `label_counts`.
- Task `recommendations.generate_recommendations(job_id)` through `run_tracked_job`. `start_recommendations(user)` mirrors `start_discovery` (needs a profile; returns the active job instead of a second one). The discovery task gains `on_completed=start_recommendations_after`.
- `recover_stale_jobs` maps the new job type to its task.

### D8. Freshness (`recommendations.refresh_recommendations`, beat)

Every `RECOMMENDATION_REFRESH_INTERVAL_SECONDS` (1800): for each profile with a pool, `last = max(generated_at)` of its recommendations, or the completion time of its last generation job when it has none. Start a job when there is no completed generation yet, `profile.analyzed_at > last`, `max(repository.lifecycle_changed_at)` over its recommendable pool `> last`, or any recommendation's config is not the active one. One aggregate query plus a candidate scan; profiles with an active generation job are skipped (`start_recommendations` returns the existing one).

Why a sweep instead of signals on every repository write: repository refreshes are shared and batched by the backlog, so a sweep coalesces many changes into one regeneration per developer.

### D9. API (`recommendations/api.py`, `/api/v1/recommendations…`)

- List: `select_related("repository", "scoring_config")`, `prefetch_related("reasons", "repository__topics")`, ordered by `rank`; django-filter `language` (Exists `RepositoryLanguage` `language__iexact`), `framework` (jsonb containment on the slug), `activity`, `size`, `match` (choice filters → 400 on unknown values through the error envelope). The query count stays constant.
- Detail adds `languages` (name + bytes share as a fraction; the UI renders a bar, not a number), `readme_excerpt` (markdown stripped to plain text with the Phase 3 `plain_text`, capped at `RECOMMENDATION_README_EXCERPT_CHARS` 1500), community facts and the latest snapshot's signals. 404 for other users (queryset scoped to the user).
- Status: latest generation job, `last_generated_at`, `count`, `config_version`.
- The serializers expose no `score`, `rank` or `signal_scores`. The admin shows them for operators.

### D10. Configuration and checks

- Settings: `RECOMMENDATIONS_TOP_N` (50), `RECOMMENDATION_MIN_SCORE` (0.10), `REPO_SIZE_THRESHOLDS` (`{"small": 10, "medium": 100}` contributors), `RECOMMENDATION_REFRESH_INTERVAL_SECONDS` (1800), `RECOMMENDATION_README_EXCERPT_CHARS` (1500), with env overrides and `.env.example` entries.
- `core/checks.py`: `RECOMMENDATIONS_TOP_N ≥ 20`, min score in 0–1, size thresholds ascending. A DB-backed check would run before migrations, so the "exactly one valid active config" rule lives in the model and the generation service instead.
- Admin: an "Activate" action on `ScoringConfig` (deactivates the others in the same transaction). Editing an active config's weights is refused; create a new version instead, so a version always means the same numbers.

### D11. Frontend

- `features/recommendations/`: `useRecommendations(filters)` (TanStack Query, filters from `useSearchParams`), `useRecommendationStatus()` (polls while a job is active, like discovery), `useRecommendation(id)`.
- `RecommendationList` on `/app` below the profile: filters (language and framework selects from a fixed list mirroring SRS-2 §55 mapped to catalog slugs, activity, size, match), cards, pagination, and empty and generating states. Filters show only when `status.count` exceeds one page (20) or a filter is in the URL: with the local pool capped at 10 they would add controls that mostly return nothing.
- `RecommendationCard`: name/owner, description, technology chips (matched ones emphasized), label badge ("Strong match"), top 3 reasons, activity text, GitHub link (`target=_blank`, `rel=noopener noreferrer`).
- Route `/app/recommendations/:id` → `RecommendationDetailPage`: "From GitHub" (overview, topics, README excerpt, contribution files) visibly separated from "ContribFinder analysis" (why it matches, technologies, activity label).
- Types come from `npm run api:sync`. Tests assert no "%" is rendered.

### D12. Carry-overs

- Ctrl+C in an interactive Windows console: run the per-runner bisect from CLAUDE.md §6, fix the culprit, and update the Known issues entry.
- Docker Compose verification stays a carry-over task (needs a machine with Docker).

## Risks / Trade-offs

- [Weights and formulas are guesses] → They are versioned data, not code. Phase 8b benchmarks decide changes, and a new version regenerates everyone through the freshness sweep.
- [Repositories without frameworks lose up to 0.10] → Bounded by the weight. Tests pin the behavior, and a later config can lower the weight.
- [Big multi-stack repositories dilute `skill_match`] → Mitigated by noisy-OR `framework_match` and `language_match`. The reasons show exactly what matched.
- [Language share rewards monolingual repositories] → Intentional: it reflects where the code is. It is only 0.20 of the score.
- [Small local pool (10) means at most 10 recommendations] → Documented in the proposal. The MVP definition of done needs the pool raised to at least 10 eligible candidates.
- [Upsert keeps ids but not history] → FR-REC-005 needs the config reference, not history. History can be added with Phase 8b if evaluations need it.
- [A freshness sweep over all profiles] → One aggregate query. Jobs are cheap (no GitHub) and deduplicated per user.
- [Stored technologies and activity go stale between generations] → The freshness sweep regenerates after repository refreshes. `generated_at` is shown.

## Migration Plan

1. Migrations: create the `recommendations` app tables, seed `v1-deterministic`, and add the job type choice. All additive.
2. Deploy the backend and worker plus beat (the new beat entry). The first freshness sweep generates recommendations for every developer with a pool, and later discoveries chain generation.
3. Frontend deploy after the API (types regenerated).

Rollback: disable the beat entry and revert the frontend. Tables can stay: nothing else reads them.

## Open Questions

- Exact band thresholds (0.55 / 0.35) should be revisited once real score distributions exist. Changing them is a new config version, not a spec change.
