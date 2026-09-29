## Why

Since v0.2.0 ContribFinder holds the user's raw GitHub data (profile, README, repositories, languages, topics), but nothing derives a picture of the developer from it. Matching (Phase 5) needs a structured, evidence-backed profile: which skills the developer has, how strongly the data supports each one, and what they are interested in. Following SRS-2 §6, the profile must show *why* each conclusion was drawn, and an isolated README mention must not count as much as sustained use. This phase builds that profile deterministically (no LLM or embeddings; SRS-2 Phase 3, FR-PROFILE-001 to 005).

## What Changes

- **Skill taxonomy**: a canonical catalog of skills with aliases and categories (language, framework, library, database, cloud, devops, tool), GitHub language-name mappings, topic mappings and dependency-name mappings per ecosystem.
- **More GitHub evidence** collected during sync (two new sync steps):
  - `dependencies`: root-level dependency manifests of the user's recently pushed, non-fork repositories (requirements.txt, pyproject.toml, package.json, go.mod, Cargo.toml, pom.xml, build.gradle / build.gradle.kts). They are parsed into stored dependency names per repository.
  - `contributions`: the user's merged pull requests and recent public pushes to repositories they do not own, plus those repositories' metadata, languages and topics. The repositories are linked to the user as `contributor`.
- **Evidence collectors** (pure functions) for README (tech sections, badges, skill icons), repository languages, repository topics, dependencies, commits, pull requests and repeated contributions. Each piece of evidence is stored as a `SkillEvidence` row with its source, supporting repository, detail and observation date.
- **Configurable confidence**: `EVIDENCE_WEIGHTS` in settings (SRS-1 §15 defaults) and a diminishing-returns `compute_confidence`, so a single README mention stays low. The weights used are recorded on each analyzed profile.
- **Interest detection** from README phrases, repository descriptions, topics and contributed repositories, mapped to an interest taxonomy through synonyms. Interests have evidence too.
- **Developer profile**: `DeveloperProfile` with a summary built from templates (generated only from computed signals), aggregated languages, an internal experience level (`beginner | intermediate | experienced | unknown`, used only for matching, not shown), and default preferences.
- **Profile analysis** runs as the final `analysis` sync step and as a standalone `extract_developer_skills` task/job (for re-analysis when weights or taxonomy change, via a management command). It never calls GitHub. A failed analysis leaves the previous profile in place.
- **API**: `GET /api/v1/profile`, `GET /api/v1/profile/skills` (with evidence, filterable by category), `GET /api/v1/profile/interests`.
- **Frontend**: the signed-in page becomes a profile page: summary, skills grouped by category with bars labeled by evidence (never "expertise %"), expandable evidence per skill, interests, a languages chart (Recharts), repositories and Refresh. Onboarding shows the three new steps.
- `GET /api/v1/profile/repositories` keeps returning only repositories the user owns; contributed repositories are exposed only as evidence.

## Capabilities

### New Capabilities
- `skill-detection`: skill taxonomy, evidence sources and collectors, evidence records per skill, configurable evidence weights and confidence (FR-PROFILE-002, FR-PROFILE-004, FR-PROFILE-005).
- `interest-detection`: interest taxonomy, interest sources, synonym matching and interest evidence (FR-PROFILE-003).
- `developer-profile`: the structured profile (summary, languages, experience level, preferences), when and how analysis runs, the profile/skills/interests API, and the profile page (FR-PROFILE-001).

### Modified Capabilities
- `github-data-sync`: adds ingestion of dependency manifests and of external contributions (merged PRs, public pushes, contributed repositories).
- `sync-jobs`: the step list grows to profile, readme, repositories, languages, topics, dependencies, contributions and analysis. The repository endpoint is limited to owned repositories. Onboarding shows the new steps.

## Impact

- **Backend**:
  - new app `developers`: `DeveloperProfile`, `Skill`, `DeveloperSkill`, `SkillEvidence`, `Interest`, `DeveloperInterest`, `InterestEvidence`;
  - `repositories` gains `RepositoryDependency` and the `contributor` relation;
  - new `services/profiling/` (taxonomy, manifest parsers, collectors, confidence, interests, experience, summary, analysis service);
  - the GitHub client gains contents, search and events methods;
  - sync service steps, a new job type `profile_analysis`, new endpoints, a `reanalyze_profiles` management command and a settings system check for weights. Migrations are additive only.
- **Frontend**: profile page components, hooks and a new dependency `recharts`; regenerated API types.
- **GitHub API usage**: roughly +60–90 requests for manifests (capped by `GITHUB_MANIFEST_MAX_REPOS`, default 30) and +45 for contributions (capped by `GITHUB_CONTRIB_MAX_REPOS`, default 20) per sync, plus 1–2 search requests (30/min search limit). ETags make repeat syncs cheap. That stays well within 5,000 requests per hour.
- **Privacy**: more GitHub-derived data is stored (dependency names, contributed repositories, derived skills and interests). It is public data only, with no new OAuth scopes. Deletion remains FR-DATA-003 (Phase 8a).
- **Carry-over**: Docker Compose verification is still open and stays in this phase's task list (it needs a machine with Docker).
