## Context

v0.2.0 stores, per user:
- `GitHubProfile` (with the raw `profile_readme`);
- owned `Repository` rows linked through `UserRepository(relation=owner)`;
- `RepositoryLanguage` (bytes) and `RepositoryTopic`.

`GitHubSyncService` runs ordered, resumable steps recorded on `SyncJob.steps`. Per-item progress goes in `job.metadata`, errors are typed, and `decide_retry` maps them to Celery retries. `SyncJob` has a partial unique constraint on one active job per (user, job_type). Nothing derives skills or interests yet, and there is no `developers` app. Requirements are in `specs/skill-detection`, `specs/interest-detection`, `specs/developer-profile` and the deltas for `github-data-sync` and `sync-jobs`. Motivation is in `proposal.md`.

Deviation from CLAUDE.md's Phase 3 sketch: `DeveloperProfile` gets **no** `profile_readme_raw` column. Phase 2 already stores the raw README on `GitHubProfile` and says derived data goes to `developers`. Copying it would put raw data in two places.

## Goals / Non-Goals

**Goals:**
- A deterministic, reproducible analysis: the same stored data plus the same configuration give the same profile. It is testable as pure functions with no database or HTTP.
- Evidence stored as relational rows. Phase 5 matching and explanations query them directly (skill ↔ repository ↔ source).
- A skill catalog and dependency-name mapping that Phase 4/5 reuse unchanged on candidate repositories (`RepositoryDependency` is per repository, not per user).

**Non-Goals:**
- LLM or embedding extraction (Phase 6). Interests use synonyms only.
- Manifests below the repository root (monorepo subpackages), lockfiles, and ecosystems beyond the eight listed manifests.
- Code reviews and issue comments as contribution evidence. Private or organization-only activity.
- A UI for editing preferences (project size, difficulty) or correcting skills. The fields exist with defaults.
- Showing experience level or numeric confidence to the user.
- Docker Compose verification. It stays a carry-over task; it can't be done without Docker.

## Decisions

### D1. Data model
**`developers` app:**
- `DeveloperProfile` (1:1 User): `summary`, `experience_level` (beginner|intermediate|experienced|unknown), `experience_signals` (JSON, internal), `preferred_project_size` (any|small|medium|large, default any), `preferred_issue_difficulty` (beginner|intermediate|advanced|unknown, default unknown), `languages` (JSON list `{name, bytes, share, repo_count}`: a small, derived, display-only aggregate, recomputed each analysis), `analysis_config` (JSON snapshot: evidence weights, interest weights, thresholds, `taxonomy_version`), `analyzed_at`.
- `Skill`: `slug` (unique), `name`, `category`. Rows are upserted from the catalog at analysis time, so the catalog in code stays the source of truth and the database gets stable FKs for Phase 5.
- `DeveloperSkill(profile, skill, confidence, first_observed_at, last_observed_at)`, unique (profile, skill).
- `SkillEvidence(developer_skill, source, repository FK null SET_NULL, detail (≤255), observed_at)`, where `source` ∈ readme|language|topic|dependency|commit|pull_request|repeated_contribution.
- `Interest(slug, name)`, `DeveloperInterest(profile, interest, strength)`, and `InterestEvidence(developer_interest, source ∈ readme|repo_description|topic|contribution, repository null, detail, observed_at)`.

**`repositories` app:**
- `RepositoryDependency(repository, ecosystem ∈ pypi|npm|go|cargo|maven|gradle, name, manifest_path)`, unique (repository, ecosystem, name). Names are normalized per ecosystem: PyPI names are lowercased and PEP 503-normalized; npm names are kept as-is, scoped names included.
- `UserRepository.Relation` gains `CONTRIBUTOR`. New nullable columns on `UserRepository`: `merged_pr_count`, `push_count`, `last_contributed_at` (null for owner links).
- The Phase 2 owner relink already filters `relation=OWNER`. `RepositoryListView` must add `user_links__relation=owner` (and `.distinct()`); today it filters by user only.

**Alternative:** a single `DeveloperSkill.evidence` JSON (SRS-1 sketch). Rejected by the CLAUDE.md conflict table ("relational evidence rows").

### D2. Catalog as typed Python data (`services/profiling/taxonomy.py`)
- Frozen dataclasses `SkillDef(slug, name, category, aliases, ambiguous_aliases, linguist_names, topics, dependencies: {ecosystem: [names/prefixes]}, implies_interests)` and `InterestDef(slug, name, synonyms, topics)`. `TAXONOMY_VERSION` is a string bumped on any edit and recorded in `analysis_config`.
- Lookup indexes are built once at import: `alias → slug`, `linguist → slug`, `topic → slug`, `(ecosystem, dep) → slug`, with prefix rules such as `@angular/` and `@aws-sdk/`.
- The first catalog covers about 150 skills: the top ~40 GitHub languages, and the major web, data, ML, test and infrastructure frameworks and libraries for Python, JS/TS, Go, Rust, Java/Kotlin, Ruby, PHP and C#. It also covers the main databases, AWS/GCP/Azure, and Docker, Kubernetes, Terraform, Ansible, GitHub Actions, Git, Linux, Nginx. A module-level test asserts that there are no alias collisions and that every slug is unique.
- **Alternative:** YAML or a database-managed catalog. Rejected for now: no PyYAML dependency, typed, reviewed in PRs, and admin editing isn't needed until feedback exists.

### D3. Two new GitHub sync steps (client and service)
- Step order: `profile → readme → repositories → languages → topics → dependencies → contributions → analysis`. `initial_steps()` includes all eight. The service reads missing keys as `pending`, so older jobs still display.
- **Client additions** (normalized dataclasses, same error mapping and ETag cache):
  - `list_root_contents(full_name) -> list[ContentEntry(name, type, size)]` uses `GET /repos/{r}/contents/`; 404 (empty repository) → `[]`.
  - `get_file(full_name, path) -> str` with the raw Accept header.
  - `search_merged_pull_requests(login) -> (list[PullRequestRef(repo_full_name, merged_at)], truncated)` uses `GET /search/issues?q=type:pr author:{login} is:merged is:public -user:{login}`, paginated and capped at `GITHUB_CONTRIB_MAX_PRS` (default 200).
  - `list_public_events(login)` uses `/users/{login}/events/public` (≤ 3 pages, the GitHub limit) and keeps only `PushEvent` with `repo.name` owner ≠ login.
  - `get_repository(full_name) -> GitHubRepo`.
- **`dependencies` step:** for the first `GITHUB_MANIFEST_MAX_REPOS` (30) owned non-fork repositories by `pushed_at`, it lists the root contents, picks supported manifests of at most `GITHUB_MANIFEST_MAX_BYTES` (512 KiB), fetches them, parses them (D4) and replaces that repository's `RepositoryDependency` rows in a transaction. Per-repository progress goes in `metadata.dependencies_done`, as in the languages step. `GitHubNotFound`/`GitHubForbidden` on one repository skip it. Rate-limit and transient errors propagate to the normal retry policy.
- **`contributions` step:** merged PRs and push events are grouped by repository. The top `GITHUB_CONTRIB_MAX_REPOS` (20), ranked by merged PRs then pushes, are fetched with `get_repository` + `get_languages` and upserted with the existing `_upsert_repository`. Topics come from the repository payload. Contributor links are then relinked: repositories no longer observed are removed, and the counts and `last_contributed_at` are set. Repositories the user owns are excluded. The grouped plan is saved in metadata first, then per-repository progress, so retries resume. If the search returns 422 (a user GitHub won't search), the step is `skipped`.
- **`analysis` step:** calls `ProfileAnalysisService(user).run()` (D6). An exception inside becomes `ProfileAnalysisError`, which `decide_retry` maps to `Fail("analysis_failed")`. Analysis is deterministic, so retrying can't help.
- **Alternative:** a Git tree API call per repository (`/git/trees/{branch}`) instead of contents. It costs the same request, but its response is larger. Contents gives sizes for the size cap directly.

### D4. Manifest parsers (`services/profiling/manifests.py`)
- Pure `parse_manifest(filename, text) -> list[Dependency(ecosystem, name)]`. Parsers:
  - requirements.txt: line-based; strips comments, options (`-r`, `-e`, `--`), markers, extras and version specifiers; skips URLs.
  - pyproject.toml: `tomllib`; reads `[project].dependencies`, `optional-dependencies`, `[dependency-groups]` and `[tool.poetry.*dependencies]`, without `python`.
  - package.json: `json`; reads dependencies, devDependencies and peerDependencies.
  - go.mod: `require` single lines and blocks (module paths).
  - Cargo.toml: `tomllib`; reads dependencies, dev-dependencies, build-dependencies and `workspace.dependencies`.
  - pom.xml: regex over `<dependency>` blocks, emitting `groupId:artifactId`. There is no XML parser, so no entity expansion is possible.
  - build.gradle(.kts): regex for `"group:artifact:version"` coordinates in dependency configurations.
- Any parse error → `[]` plus a debug log with the filename only. Fixture tests cover each format, including malformed input.

### D5. Collectors, confidence, interests, experience, summary (`services/profiling/`)
All are pure functions over an immutable `ProfileInput` snapshot (README text; owned non-fork repositories with languages, topics, description, dependencies and `pushed_at`; contributed repositories with counts; account creation date). They don't touch the database.
- **`readme.py`**
  - Converts Markdown to line segments. Recognized sections are headings that match `/skill|tech|stack|tool|language|framework|technolog/i`, up to the next heading of the same or a higher level.
  - Badge and icon sources: shields.io `logo=` query values and `<img alt>` / `![alt]` text; `skillicons.dev/icons?i=a,b` lists; devicon URLs (`devicons/.../<name>-original.svg`).
  - Unambiguous aliases match anywhere, on word boundaries. Ambiguous aliases match only in sections, badges or icons (see spec).
  - Produces one `readme` evidence per skill, `observed_at` = profile `synced_at`.
- **`collectors.py`**
  - `language_skills`: primary language or share ≥ `LANGUAGE_MIN_SHARE` (0.10). Detail: e.g. `"Python · 72% of bytes"`.
  - `topic_skills`, `dependency_skills`. Detail: `"pyproject.toml: djangorestframework"`.
  - `contribution_skills`: `pull_request` evidence per merged PR repository (detail: `"3 merged pull requests"`); `commit` per pushed repository; `repeated_contribution` when merged PRs ≥ `REPEATED_CONTRIBUTION_MIN_PRS` (3).
  - Evidence `observed_at` is the repository's `pushed_at` or `last_contributed_at`.
- **`confidence.py`**
  - `compute_confidence(evidence, weights, decay)`: group by source and order each group newest first. The k-th item (0-based) of a source gets effective weight `w_source · decay^k`. Then `confidence = min(1 − Π(1 − w_eff), CONFIDENCE_CAP)`, with decay = `EVIDENCE_REPEAT_DECAY` (0.5) and the cap at 0.99.
  - This is a noisy-OR: monotonic, with diminishing returns inside a source, and one README mention gives exactly `w_readme`. Different sources compound, so sustained multi-source use beats any single source. The cap keeps confidence below 1 even with `repeated_contribution = 1.0`.
  - **Alternative:** a weighted sum clipped to 1. Rejected: it saturates quickly and a single strong source hides the rest.
- **`interests.py`**
  - Synonym phrases compile to word-boundary regexes. A skill's `implies_interests` (e.g. PyTorch → AI) doesn't create evidence by itself in this phase. It is kept in the catalog for Phase 5.
  - Strength is computed with the same function using `INTEREST_EVIDENCE_WEIGHTS` (readme 0.30, repo_description 0.40, topic 0.50, contribution 0.60).
  - Inclusion: strength ≥ `INTEREST_MIN_STRENGTH` (0.35), or ≥ 2 distinct repositories.
- **`experience.py`**
  - Each signal with data scores 0 (beginner), 1 (intermediate) or 2 (experienced) against thresholds in `EXPERIENCE_THRESHOLDS`: account age in years (1/4), active owned repositories pushed within 2 years (3/10), merged external PRs (1/15), distinct contributed repositories (1/4), skills with confidence ≥ 0.5 (3/8).
  - With fewer than 2 signals that have data → `unknown`. Otherwise the mean score rounds to a level (< 0.67 beginner, < 1.34 intermediate, else experienced). A single signal can never decide the level.
  - The inputs and per-signal scores are stored in `experience_signals` for auditing.
- **`summary.py`**: fixed sentence templates, filled from the top 2 language skills by confidence (markup such as HTML/CSS excluded), the top 3 framework/library skills by confidence and the top 2 interests. Only skills with evidence beyond a README mention qualify. (Ranking languages by bytes was tried first: notebooks and markup dominated, e.g. "Works mostly in Jupyter Notebook and HTML".) Missing parts are left out. With no skills, the sentence reads "Not enough public activity was found to describe your technical profile yet."
- **`languages.py`**: aggregates bytes over owned non-fork repositories into `{name, bytes, share (2 dp), repo_count}`.

### D6. `ProfileAnalysisService` and the standalone job
- `services/profiling/analysis.py`: builds `ProfileInput` with a few prefetching queries, runs D5, then **replaces** the user's derived data in one `transaction.atomic()`: upsert the profile; delete, then bulk-create `DeveloperSkill`, `SkillEvidence`, `DeveloperInterest` and `InterestEvidence`; upsert `Skill`/`Interest` from the catalog. Preferences that aren't at their defaults are left untouched. Because everything happens in one transaction, a failure rolls back and leaves the previous profile intact.
- `SyncJob.JobType.PROFILE_ANALYSIS` with a single step `analysis`. Task `developers.tasks.extract_developer_skills(job_id)` claims the job the same way as the sync task (the shared `claim_job` helper moves to `services/jobs.py`) and runs the service. `analysis_failed` is terminal.
- Management command `reanalyze_profiles [--user <id>]` creates a job per user with a completed sync and enqueues it. The one-active constraint per (user, type) prevents duplicates.
- **Alternative:** run analysis only as its own job enqueued after sync. Rejected: onboarding would need to poll two jobs. A sync step keeps the per-step ticks in one place.

### D7. Configuration and startup check
Settings, all overridable through env as JSON (`env.json`) or scalars:
- `EVIDENCE_WEIGHTS`, `EVIDENCE_REPEAT_DECAY=0.5`, `CONFIDENCE_CAP=0.99`, `LANGUAGE_MIN_SHARE=0.10`, `REPEATED_CONTRIBUTION_MIN_PRS=3`;
- `INTEREST_EVIDENCE_WEIGHTS`, `INTEREST_MIN_STRENGTH=0.35`, `EXPERIENCE_THRESHOLDS`;
- `GITHUB_MANIFEST_MAX_REPOS=30`, `GITHUB_MANIFEST_MAX_BYTES=524288`, `GITHUB_CONTRIB_MAX_PRS=200`, `GITHUB_CONTRIB_MAX_REPOS=20`.

A Django system check in `core/checks.py` (`Error`, deploy and runtime) validates: every evidence source present, weights in [0,1], decay in (0,1), cap in (0,1). Invalid config blocks startup, as the spec requires.

### D8. API (`developers/api.py`, under `/api/v1/profile`)
- `GET /profile` → `DeveloperProfileSerializer`: `summary, languages, preferred_project_size, preferred_issue_difficulty, analyzed_at, skill_count, interest_count`. There is no experience field. Without a profile: 404 `not_analyzed` (a new `NotAnalyzed(APIException)`).
- `GET /profile/skills` → paginated `DeveloperSkill` list ordered by (−confidence, name), `?category=` through django-filter. Each item: `skill {slug, name, category}, confidence, evidence_summary {by_source, repository_count, last_observed_at}, evidence [{source, repository {full_name, html_url} | null, detail, observed_at}]`, loaded with `prefetch_related`, so the query count is constant. `confidence` is in the API because Phase 5 and the bar width use it. The UI never prints it.
- `GET /profile/interests` → paginated, ordered by −strength, with evidence.
- The new routes are added to `github/urls.py`'s `profile/` include. The root `profile` path is `""` in that include.
- `npm run api:sync` regenerates the types.

### D9. Frontend
- Hooks: `useDeveloperProfile()`, `useSkills(category?)` and `useInterests()` (TanStack Query). They are invalidated when `useSyncStatus` sees a transition to COMPLETED.
- `/app` becomes the profile page, with sections Summary · Skills · Interests · Languages · Repositories.
  - `SkillGroup` per category. A `SkillBar` has width = confidence and a text label built by `evidenceLabel(summary)`, e.g. "8 repositories · dependencies · README". A pure function, unit-tested.
  - `SkillEvidenceList` expands inline, with repository links (`target=_blank rel=noopener`).
  - `InterestList` chips show their evidence in an expandable list.
  - The languages chart is a Recharts horizontal bar chart of `profile.languages` (top 8 + "Other"). It replaces the Phase 2 client-side aggregation.
- 404 `not_analyzed` renders a "Your profile is being prepared" state, with the repositories still shown.
- Onboarding: `STEP_ORDER`/`STEP_LABELS` gain dependencies ("Dependencies"), contributions ("Contributions") and analysis ("Building profile"). `messages.ts` maps `analysis_failed`.
- New dependency: `recharts` (CLAUDE.md stack).

## Risks / Trade-offs

- [README false positives from common words] → Ambiguous aliases are restricted to sections, badges and icons. Evidence is visible, so a mistake can be understood, and a README-only skill stays at 0.20.
- [Search API: 30 req/min limit, `is:merged` needs indexing] → 1–2 search requests per sync. A 403/429 goes through the existing rate-limit retry. A 422 skips the step.
- [Events API covers only ~90 days / 300 events] → Commit evidence is "recent pushes" by design. Merged PRs (not time-limited) carry the stronger contribution signal.
- [More requests per sync (~+150 worst case)] → Caps (30 manifest repositories, 20 contributed repositories) and ETags. The total stays below 5% of the hourly budget.
- [Dependency names differ from skills (e.g. `psycopg2-binary`)] → Per-ecosystem normalization and prefix rules in the catalog. Tests pin common names.
- [Catalog drift: new frameworks aren't detected] → `TAXONOMY_VERSION` plus `reanalyze_profiles`. Unknown terms are ignored rather than guessed.
- [Replace-all analysis changes `DeveloperSkill` ids on every run] → Nothing references `DeveloperSkill` by id yet. Phase 5 references `Skill` (stable slug).
- [Large analysis transaction] → The volume is bounded (≤ 150 repositories and a few hundred evidence rows) and uses bulk inserts.
- [Old `SyncJob` rows lack the new steps] → The service treats missing keys as pending, and the UI defaults to pending (it already does `?? 'pending'`).

## Migration Plan

Additive migrations:
- the new `developers` tables;
- `RepositoryDependency`;
- nullable columns on `UserRepository` plus the new choice value (no data change).

Existing users get a profile on their next sync (Refresh or sign-in), or an operator runs `reanalyze_profiles` to analyze without new GitHub data; dependencies and contributions then stay empty until the next sync. Rollback: revert the code and migrations. No existing table loses data.

## Open Questions

- The exact first-release catalog contents (which ~150 skills and interests). This can grow later without spec changes, because `TAXONOMY_VERSION` and re-analysis cover it.
