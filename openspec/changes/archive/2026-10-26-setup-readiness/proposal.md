## Why

A first contribution often fails before the first line of code: the project is hard to build and
test locally. ContribFinder shows whether a project explains how to contribute (CONTRIBUTING,
templates, labels) but not whether it is easy to set up. `ideas.md` §8 ("Setup readiness", first
in the "can ship now" list): the root listing the analysis already fetches for manifests shows CI
configuration, tests, a dev container and Docker Compose for about one extra request per
repository. Shown as observable facts, they help a developer pick a project they can actually run.
No ranking change: the facts are stored and shown, never scored.

## What Changes

- Repository analysis records four setup facts, each true, false or unknown (not yet analyzed):
  - **CI**: GitHub Actions workflows under `.github/workflows`, or a root CI file of another
    service (GitLab CI, Travis, CircleCI, Azure Pipelines, Jenkins, …);
  - **tests**: a root test directory (`tests`, `test`, `spec`, `__tests__`, …) or test-runner
    configuration (`pytest.ini`, `tox.ini`, `jest.config.*`, `vitest.config.*`, …);
  - **dev environment**: a `.devcontainer` directory, `.devcontainer.json` or `.gitpod.yml`;
  - **Docker Compose**: `docker-compose.yml` / `compose.yml` (`.yaml` too).
- The facts come from the root listing the dependencies part already fetches, plus one listing of
  `.github/workflows` when a `.github` directory exists. They refresh with the dependencies part
  (weekly by default); repositories analyzed before this change show them as unknown until then.
- Detection only looks at the repository root (and `.github/workflows`), so "not found" never
  claims a project has no tests: tests kept next to the code (Go, Rust) are not seen. The
  interface says "Not found", never "No".
- API: recommendation list items and the detail gain `setup` (`ci`, `tests`, `dev_environment`,
  `docker_compose`, each boolean or null). Additive; OpenAPI stays `1.0.0`.
- Interface:
  - cards show a short setup line built from the facts found, for example "CI · tests · dev
    container" (nothing when none was found or the data is unknown);
  - the detail page gains a "Setup" group next to the contribution guidelines with "Found",
    "Not found" or "Not available" per fact.
- No ranking, explanation or evaluation change: no signal, reason or benchmark field reads the
  facts.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repository-analysis`, "Repository data collection": the setup facts, how they are detected
  and that absence is only "not found at the root".
- `recommendations-view`:
  - "Recommendation detail endpoint": the `setup` facts;
  - "Recommendations on the dashboard": the setup line on cards;
  - "Repository detail page": the Setup group.

## Impact

- Backend:
  - `repositories/models.py`: `has_ci`, `has_tests`, `has_dev_environment`,
    `has_docker_compose` (nullable booleans, migration, no backfill);
  - `services/repositories/setup.py` (new, pure): marker tables and `detect(root, workflows)`;
  - `services/github/storage.py`: the root listing is fetched once and shared by manifests and
    setup detection; `services/repositories/analysis.py` fetches `.github/workflows` when needed
    and stores the facts with the dependencies part;
  - `recommendations/serializers.py`: `SetupSerializer` on list items and the detail;
  - tests with recorded fixtures (respx).
- Frontend: `RecommendationCard.tsx` (setup line), `RecommendationDetailPage.tsx` (Setup group),
  labels in `features/recommendations/messages.ts`; regenerated `src/api/openapi.json` and
  `schema.d.ts`; tests.
- GitHub budget: at most one extra request per analyzed repository (only with a `.github`
  directory), covered by the ETag cache on refreshes.
- Release: patch 0.12.24. Docs: README, CLAUDE.md §7, `ideas.md` §8 (shipped), CHANGELOG,
  features.
