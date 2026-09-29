## 1. Data model

- [x] 1.1 Create the `developers` app with `DeveloperProfile` (summary, experience_level + experience_signals, preferred_project_size default `any`, preferred_issue_difficulty default `unknown`, languages JSON, analysis_config JSON, analyzed_at), `Skill`, `DeveloperSkill`, `SkillEvidence`, `Interest`, `DeveloperInterest`, `InterestEvidence`, with enums, unique constraints and indexes (design D1)
- [x] 1.2 Add `repositories.RepositoryDependency` (unique repository+ecosystem+name). Add the `UserRepository.Relation.CONTRIBUTOR` choice and the nullable `merged_pr_count`, `push_count`, `last_contributed_at` columns
- [x] 1.3 Add `SyncJob.JobType.PROFILE_ANALYSIS`. Generate migrations (`--settings config.settings.test`). Register read-only admin views
- [x] 1.4 Tests: unique constraints (skill per profile, dependency per repository, contributor link); cascade on profile delete; `SET_NULL` on evidence when a repository is deleted

## 2. Configuration

- [x] 2.1 Add settings `EVIDENCE_WEIGHTS` (SRS-1 §15 defaults), `EVIDENCE_REPEAT_DECAY`, `CONFIDENCE_CAP`, `LANGUAGE_MIN_SHARE`, `REPEATED_CONTRIBUTION_MIN_PRS`, `INTEREST_EVIDENCE_WEIGHTS`, `INTEREST_MIN_STRENGTH`, `EXPERIENCE_THRESHOLDS`, `GITHUB_MANIFEST_MAX_REPOS`, `GITHUB_MANIFEST_MAX_BYTES`, `GITHUB_CONTRIB_MAX_PRS`, `GITHUB_CONTRIB_MAX_REPOS`, with env overrides. Document them in `.env.example`
- [x] 2.2 Add a system check in `core/checks.py` that rejects missing evidence sources, weights outside [0,1], and decay or cap outside (0,1). Tests for valid and invalid configs

## 3. Catalog and pure profiling functions (spec: skill-detection, interest-detection)

- [x] 3.1 Implement `services/profiling/taxonomy.py`: `SkillDef`, `InterestDef`, `TAXONOMY_VERSION`, ~150 skills across the 7 categories (aliases, ambiguous aliases, linguist names, topics, per-ecosystem dependency names and prefixes) and the interest catalog (≥ 14 interests with synonyms and topics). Build the lookup indexes
- [x] 3.2 Catalog tests: unique slugs; no alias, topic or dependency collisions between skills; PostgreSQL resolves from "Postgres", `postgresql` and `psycopg`/`psycopg2-binary`; unknown terms resolve to nothing
- [x] 3.3 Implement `services/profiling/manifests.py` parsers (requirements.txt, pyproject.toml, package.json, go.mod, Cargo.toml, pom.xml, build.gradle/.kts) with per-ecosystem name normalization. Fixture tests for each format, including malformed input returning `[]`
- [x] 3.4 Implement the `ProfileInput` snapshot dataclasses and `services/profiling/readme.py` (tech sections, shields.io `logo=`, image alt text, skillicons.dev, devicon URLs; ambiguous aliases only in sections, badges or icons; one evidence per skill). Tests: skills section, badge, skill icons, "go hiking" free text gives no Go, no README gives no evidence
- [x] 3.5 Implement `services/profiling/collectors.py` (language with primary-or-share rule, topic, dependency, pull_request, commit, repeated_contribution; forks excluded; details and observed_at). Tests per source covering the spec scenarios
- [x] 3.6 Implement `services/profiling/confidence.py` `compute_confidence` (per-source decay, noisy-OR, cap). Tests: README-only equals the README weight; monotonic; the 10th item adds less than the 2nd; sustained multi-source beats a README mention; deterministic; a weight change is reflected
- [x] 3.7 Implement `services/profiling/interests.py` (word-boundary synonyms, topic mapping, sources readme/repo_description/topic/contribution, strength, inclusion threshold). Tests: synonyms resolve to one interest, "maintain" gives no AI, a single weak mention is excluded, three repositories are included
- [x] 3.8 Implement `experience.py` (multi-signal scoring, `unknown` with < 2 signals), `summary.py` (templates, sparse-account sentence) and `languages.py` (aggregation with share and repo_count). Tests covering the developer-profile spec scenarios

## 4. GitHub client additions (spec: github-data-sync)

- [x] 4.1 Add `list_root_contents` (404 → `[]`), `get_file` (raw), `search_merged_pull_requests` (paginated, capped, truncation flag), `list_public_events` (PushEvent to non-owned repositories only, ≤ 3 pages) and `get_repository`, with normalized dataclasses `ContentEntry`, `PullRequestRef`, `PushRef`
- [x] 4.2 respx fixture tests: contents listing and empty repository; raw file; search pagination and cap; search 422 → typed error; events filtered to external pushes; rate-limit and transient mapping on the search endpoint; no token in logs

## 5. Sync steps (spec: github-data-sync, sync-jobs)

- [x] 5.1 Extend `STEPS`/`initial_steps()` to eight steps. Treat missing step keys as pending
- [x] 5.2 Implement the `dependencies` step: top `GITHUB_MANIFEST_MAX_REPOS` owned non-fork repositories by `pushed_at`, root listing, size cap, parse and replace `RepositoryDependency` per repository in a transaction, per-repository progress in metadata, 404/403 skip a repository, record the cap in metadata
- [x] 5.3 Implement the `contributions` step: search merged PRs and public pushes, group by repository excluding owned ones, save the plan in metadata, fetch and upsert the top `GITHUB_CONTRIB_MAX_REPOS` (metadata, languages, topics) with per-repository progress, relink `CONTRIBUTOR` links with counts and `last_contributed_at`, remove stale links, 422 → `skipped`, record caps
- [x] 5.4 Implement the `analysis` step calling `ProfileAnalysisService` (section 6). Wrap failures in `ProfileAnalysisError`, and make `decide_retry` map it to `Fail("analysis_failed")`
- [x] 5.5 Restrict `GET /api/v1/profile/repositories` to `relation=owner` (with `.distinct()`)
- [x] 5.6 Tests: full sync with all eight steps done; manifests stored per repository; a repository without manifests or a 403 is skipped; manifest cap metadata; forks not read; contributions stored and linked with counts; own repositories excluded; stale contributor link removed; 422 → skipped and job COMPLETED; retry resumes the dependencies and contributions steps without re-fetching (request counts); analysis failure → FAILED `analysis_failed` with GitHub data kept; the repository list excludes contributor links; old jobs without the new step keys serialize

## 6. Profile analysis service and job (spec: developer-profile)

- [x] 6.1 Implement `services/profiling/analysis.py` `ProfileAnalysisService(user).run()`: build `ProfileInput` with prefetching queries, run collectors, confidence, interests, experience, summary and languages, upsert `Skill`/`Interest` from the catalog, replace the derived rows in one transaction, keep non-default preferences, store `analysis_config` (weights, thresholds, taxonomy version) and `analyzed_at`
- [x] 6.2 Move `claim_job` into `services/jobs.py` (shared). Add task `developers.tasks.extract_developer_skills(job_id)` (job type `profile_analysis`, single step `analysis`, `analysis_failed` terminal) and the management command `reanalyze_profiles [--user]`
- [x] 6.3 Tests: profile created with defaults; re-analysis replaces stale skills and interests; idempotent (two runs give identical rows); failure mid-way leaves the previous profile unchanged; no GitHub requests during analysis (respx asserts none); weight change plus re-analysis changes a README-only confidence; sparse account summary; the command enqueues one job per synced user and none for users without a sync

## 7. Profile API (spec: developer-profile)

- [x] 7.1 Implement `GET /api/v1/profile` (no experience field; 404 `not_analyzed` through a new `NotAnalyzed` exception), `GET /api/v1/profile/skills` (paginated, ordered by confidence, `?category=` filter, evidence summary and evidence with repository name and URL, constant query count) and `GET /api/v1/profile/interests` (paginated, ordered by strength, with evidence)
- [x] 7.2 Tests: response shapes; category filter; `not_analyzed`; user isolation; 401 when signed out; no experience level in any response; query count does not grow with the number of skills
- [x] 7.3 Regenerate the OpenAPI schema and TypeScript types (`npm run api:sync`)

## 8. Frontend (spec: developer-profile, sync-jobs)

- [x] 8.1 Add `recharts`. Add hooks `useDeveloperProfile`, `useSkills`, `useInterests` using generated types, invalidated when a sync completes
- [x] 8.2 Build the profile page on `/app`: summary; skills grouped by category with `SkillBar` (width from confidence, label from a pure `evidenceLabel()`, no percentages); expandable `SkillEvidenceList` with repository links; `InterestList` with evidence; Recharts languages chart (top 8 + Other) replacing the client-side aggregation; repositories, last synced and Refresh kept; a "profile is being prepared" state for `not_analyzed`
- [x] 8.3 Onboarding: add the dependencies, contributions and analysis ("Building profile") steps; map `analysis_failed` to a readable message with retry
- [x] 8.4 Tests (Vitest + RTL): `evidenceLabel` cases; skills grouped by category with no "%" rendered; expanding a skill shows evidence and links; interests render; the not-analyzed state; onboarding shows eight steps and the `analysis_failed` message; the languages chart renders the profile data

## 9. Verification, docs and release

- [x] 9.1 Manual end-to-end with `npm start` (WSL Redis and worker) on a real account: onboarding shows all steps, the profile page shows skills with evidence, interests and languages; `reanalyze_profiles` updates `analyzed_at` without GitHub calls
- [~] 9.2 Carry-over: verify `docker compose up` from a fresh `.env` on a machine with Docker. If still impossible, mark it `[~]` and carry it to Phase 4 — still no Docker on the dev machine (2026-09-29); carried over to Phase 4
- [x] 9.3 Run all checks: ruff, ruff format, mypy, pytest (Postgres), eslint, prettier, tsc, vitest, build, `openspec validate --strict`, `check:version`
- [x] 9.4 Release housekeeping (CLAUDE.md §8): bump to 0.3.0 across `VERSION` and the manifests plus lockfiles; `CHANGELOG.md`; `features.txt`; `README.md`; `CLAUDE.md` (Phase 3 shipped, the `developers` app in the layout, the `profile_readme_raw` deviation, carry-overs into Phase 4)
