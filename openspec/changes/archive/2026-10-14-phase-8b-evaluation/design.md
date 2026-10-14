## Context

See proposal.md (Why). Current state that shapes the approach:

- Matching inputs are already frozen dataclasses: `DeveloperFeatures` / `SkillFeature` and `RepoData` / `SnapshotData` (`services/matching/features.py`), `IssueFeature` (`services/matching/issues.py`). `load_developer`, `load_candidates` and `load_issues` are the only database reads of generation.
- `RecommendationService._score` is the only place that strings the in-memory stages together (technologies → `signals.compute` → `load_issues` for candidates past the relevance gate → `match_issues` → `score_candidate`), and `run` then calls `rank(min_score=RECOMMENDATION_MIN_SCORE, top_n=RECOMMENDATIONS_TOP_N)`. The issue loading sits in the middle of that loop.
- `match_issues` and every signal are pure and take no clock: activity uses the snapshot's stored `days_since_push`. Issue eligibility (age, assignee, lock) is applied by the `load_issues` query, not in Python.
- `ScoringConfig` rows `v1-deterministic` and `v2-deterministic` are seeded by migrations, so they exist in the test database. `services/ranking/config.validate(weights, params, stored=...)` validates both.
- `RECOMMENDATIONS_TOP_N` (default 50) and `RECOMMENDATION_MIN_SCORE` (default 0.10) come from settings and may be overridden in a local `.env`.
- The skill and interest catalogs are `SKILLS_BY_SLUG` and `INTERESTS_BY_SLUG` in `services/profiling/taxonomy.py`.
- Management commands live in `<app>/management/commands/` (`developers/.../reanalyze_profiles.py`).

## Goals / Non-Goals

**Goals:**
- Evaluation and generation cannot drift apart: they call the same ranking function.
- Metrics and dataset handling are pure and unit-tested without a database; only configuration lookup and export touch it.
- A ranking change is visible in CI as a failing, named number.

**Non-Goals:**
- Online metrics from `RecommendationFeedback` (save/dismiss rates by rank). Feedback is too sparse to judge rankings yet; it can become a second report later.
- Issue-level evaluation (relevant issues per recommendation). The judgments are per repository; SRS-2 §61 allows repository or issue candidates, and repository ranking is what the configurations change.
- Storing evaluation runs in the database, an API or a UI for them.
- Tuning `v2-deterministic` or proposing a `v3`. This change builds the instrument; a later change uses it.
- Evaluating discovery (whether good repositories enter the pool). The pool is fixed by the dataset.

## Decisions

### D1. One pure ranking stage
New `services/ranking/pipeline.py`:

```python
def rank_pool(dev, candidates, weights, params, issues_for, *, min_score, top_n) -> list[Scored]
```

`issues_for(repo_ids) -> dict[int, list[IssueFeature]]` is called once with the ids of candidates that pass the relevance gate. Generation passes `lambda ids: load_issues(ids, now, settings.ISSUE_MAX_AGE_DAYS)`; evaluation passes a dict lookup over the dataset. `RecommendationService._score` and its `rank` call are replaced by `rank_pool`; `_persist` is untouched.

- Why a callback rather than loading all issues first: generation keeps loading issues only for gated candidates, in one query, as today.
- Alternative: evaluation re-implements the loop. Rejected: the spec's parity requirement would rest on discipline, and the existing generation tests would not protect evaluation.
- A parity test runs generation on database rows, then `rank_pool` on the loaded features, and compares order and scores.

### D2. Dataset format and location
Data in `apps/backend/evaluation/` (not a Django app, not under `services/`, which holds code): `benchmark-v1.json` and `baselines.json`. JSON rather than YAML: no new dependency, and the export writes the same format.

```json
{
  "format": 1, "name": "benchmark-v1", "description": "...",
  "repositories": { "bench/django-forms-kit": { "description": "...", "languages": [["Python", 120000]],
      "topics": ["django"], "dependencies": [["pypi", "django"]], "has_contributing": true,
      "has_issue_templates": false, "has_good_first_issue_label": true, "has_help_wanted_label": false,
      "snapshot": { "activity_label": "recently_active", "days_since_push": 3, "commits_90d": 40,
                    "prs_merged_90d": 12, "contributors": 25 },
      "issues": [ { "number": 12, "labels": ["good_first_issue", "documentation"],
                    "contribution_type": "documentation", "difficulty": "beginner",
                    "technologies": ["django"], "updated_at": "2026-09-01T00:00:00Z" } ] } },
  "developers": [ { "id": "dev-django", "description": "...", "experience_level": "intermediate",
      "skills": { "python": { "confidence": 0.9, "category": "language", "repo_count": 8 } },
      "interests": { "web": 0.6 },
      "candidates": [ { "repository": "bench/django-forms-kit", "best_search_rank": 3 } ],
      "judgments": { "bench/django-forms-kit": 2 } } ]
}
```

- A shared `repositories` catalog plus per-developer `candidates` (name + search rank, which is per-developer in the real model) avoids repeating repository data across personas, as the real shared `Repository` table does.
- Repository ids are assigned on load (1..n by sorted name) because `RepoData.id` and `IssueFeature.id` must be ints; nothing persists them.
- Issues in the dataset are taken as already eligible (export applies `load_issues`' filter). Their `updated_at` is kept because it breaks ties in issue ranking.
- Skill and interest names are filled from the catalog, so the file holds slugs only; an unknown slug fails validation (catches catalog renames).

### D3. Module layout (`services/evaluation/`)
- `dataset.py`: `load(path) -> Dataset`, validation per the spec (collects all errors, raises `DatasetError` listing them), conversion to `DeveloperFeatures` / `RepoData` / `IssueFeature`.
- `metrics.py`: pure functions `precision_at`, `recall_at`, `reciprocal_rank`, `ndcg_at` over `(ranked names, judgments)`; `DeveloperMetrics` and `mean`.
- `runner.py`: `evaluate(dataset, config: ConfigSpec, *, min_score, top_n) -> Report`; `compare(reports, tolerance) -> list[Verdict]`. `ConfigSpec` is `(label, weights, params)`, built from a stored row or a file after `config.validate(..., stored=True)`.
- `export.py`: `export_developer(user, developer_id, now) -> dict` using `load_developer`, `load_candidates`, `load_issues`.

### D4. Metric definitions
As in the spec. Notes that affect implementation:
- Precision@k divides by k, not by the list length (standard; it penalizes a gate that keeps few results, which is the behavior to measure).
- NDCG@10 ideal ordering uses all the developer's judgments, not only those in the pool's ranked list, so a relevant repository cut by the gate lowers NDCG as well as recall.
- Rounding to 4 places happens at report time only; comparisons and the improvement rule use the rounded dataset-level means, so the printed numbers and the verdict agree.

### D5. Commands
In `recommendations/management/commands/` (the app that owns `ScoringConfig`):

```
evaluate_ranking [--config VERSION]... [--config-file PATH]... [--dataset PATH]
                 [--json OUT] [--require-improvement] [--tolerance 0.01]
                 [--min-score X] [--top-n N]
export_benchmark_developer --user-id ID --as DEV_ID [--out PATH]
```

- Configurations are evaluated in the order given; the first is the baseline. With none given, the active configuration alone is evaluated.
- `--min-score` / `--top-n` default to the settings, so a plain run shows what this installation's users get. The baseline test pins them (D6) so a local `.env` cannot change CI's numbers.
- Output: one dataset-level table (configurations as rows, metrics as columns, deltas in parentheses), then per developer a row per configuration plus its top 10 as `rank. full_name [judgment or ?]`.
- Export takes a user id, not a username, so the command line does not carry the GitHub login either; `--as` is required.
- Errors use `CommandError` (non-zero exit, message on stderr).

### D6. Regression baseline
`baselines.json`: `{ "dataset": "benchmark-v1", "min_score": 0.10, "top_n": 50, "configs": { "v1-deterministic": { "precision@5": ..., ... }, "v2-deterministic": {...} } }`. The test loads the stored rows (seeded by migration), evaluates with the pinned settings and compares rounded values exactly. A helper flag `evaluate_ranking --write-baseline` rewrites the file from the current code, so updating it is one deliberate command whose diff shows in review.

### D7. Seed dataset authoring
Six personas: Django backend (intermediate), React/TypeScript frontend (intermediate), Rust systems (experienced), data engineer with Python/Airflow/SQL (intermediate), Go infrastructure (experienced) and a beginner with JavaScript and HTML/CSS. About 36 fictional repositories under the `bench/` owner, spread so that every persona's pool (8–12 candidates) mixes clear matches, partial overlaps (same language, other domain), activity/openness traps (very active but off-topic) and repositories that only the gate should drop. Judgments are written from the persona description before running any configuration, and the file records that order in its `description`. Fictional names avoid presenting made-up numbers as facts about real projects.

## Risks / Trade-offs

- [Synthetic personas reward what their author believes] → Judgments are written before any run; real exports (D5) are the path to a sturdier dataset, and the format version allows `benchmark-v2`.
- [A small dataset makes small differences noise] → The tolerance and the "strictly higher NDCG" rule refuse ties; the report shows per-developer numbers so one persona carrying a delta is visible.
- [The baseline test fails on every intended ranking change] → That is the point; `--write-baseline` keeps the update to one command and the diff documents the effect.
- [Catalog changes (new skill aliases) break the dataset] → Validation names the unknown slug; fixing the file is part of the catalog change.
- [Exports could leak a user's identity through repository names they own] → Own repositories are excluded from pools by discovery, so they never appear; the person exporting still reviews the file before committing it.

## Migration Plan

No schema or data migration. Refactoring generation onto `rank_pool` is covered by the existing generation tests plus the parity test. Rollback is reverting the change.
