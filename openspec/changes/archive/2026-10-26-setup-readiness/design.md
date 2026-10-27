## Context

See proposal.md for why.
- The `dependencies` analysis part (`services/repositories/analysis.py`, `_fetch`) calls
  `services/github/storage.read_manifests`, which lists the root (`GitHubClient.list_root_contents`,
  `/repos/{r}/contents/`, `[]` on 404) and fetches each manifest. The developer's own repositories
  use `read_manifests` too (GitHub sync, dependencies step).
- Part freshness: `staleness.PART_FIELDS["dependencies"] = "dependencies_synced_at"`,
  `REPO_STALE_AFTER["dependencies"]` 168 h. `_store` writes each fetched part's fields in one
  transaction under the repository claim.
- Community facts (`has_contributing`, …) are nullable booleans on `Repository`, shown through
  `OpennessSerializer` (`openness` on list items and the detail) and as "Yes" / "No" / "Not
  available" in the detail page's "Contribution guidelines" group. Cards do not show them.
- Every GitHub call goes through `GitHubClient` (ETag cache, retries); tests use recorded
  fixtures with respx.

## Goals / Non-Goals

**Goals:**
- Four setup facts per repository from at most one extra request.
- Wording that never claims more than the root shows.

**Non-Goals:**
- Scoring, reasons, filters or evaluation fields from the facts (a ranking change, after K-1).
- Reading file contents (which CI jobs run, whether tests pass), searching below the root, or a
  "build status" badge.
- Detecting setup facts for the developer's own repositories.

## Decisions

**D1. One root listing, shared by manifests and setup detection.**
- `read_manifests(client, full_name, entries=None)` takes the root entries when the caller has
  them; without them it lists the root as today (the GitHub sync is unchanged).
- The analysis' `dependencies` part lists the root once, passes the entries to `read_manifests`
  and to setup detection.
- *Alternative:* a separate `setup` part with its own timestamp and age. Rejected: it would list
  the same root again on its own schedule, and the facts change about as often as manifests.

**D2. `.github/workflows` only when the root has a `.github` directory.**
- New `GitHubClient.list_contents(full_name, path)` (`/repos/{r}/contents/{path}`, `[]` on 404 or
  a non-list body, `@_parses_response`); `list_root_contents` becomes `list_contents(name, "")`.
- CI is found when that listing holds a file ending in `.yml` or `.yaml`, or when a root marker of
  another CI service matched (then the workflows listing is skipped: the fact is already found).
- *Alternative:* `/repos/{r}/actions/workflows`. Rejected: same cost, but it also lists disabled
  and GitHub-managed workflows (Dependabot, Pages), and a repository with Actions turned off
  answers 404 like one without workflows.

**D3. Detection is a pure function over entry names.**
- `services/repositories/setup.py`: `SetupFacts(ci, tests, dev_environment, docker_compose)` and
  `detect(root: Sequence[ContentEntry], workflows: Sequence[ContentEntry] | None) -> SetupFacts`.
- Marker tables as module constants, matched on the lowercased name and the entry type (`dir` or
  `file`), like the manifest names in `services/profiling/manifests`:
  - CI files: `.gitlab-ci.yml`, `.travis.yml`, `azure-pipelines.yml`, `jenkinsfile`,
    `.drone.yml`, `appveyor.yml`, `bitbucket-pipelines.yml`, `.cirrus.yml`; CI dirs: `.circleci`,
    `.buildkite`;
  - test dirs: `test`, `tests`, `spec`, `specs`, `__tests__`, `testing`; test files:
    `pytest.ini`, `tox.ini`, `noxfile.py`, `conftest.py`, `phpunit.xml`, `phpunit.xml.dist`,
    `.rspec`, `karma.conf.js`, plus prefixes `jest.config.`, `vitest.config.`,
    `playwright.config.`, `cypress.config.`;
  - dev environment: dir `.devcontainer`, files `.devcontainer.json`, `.gitpod.yml`;
  - Docker Compose files: `docker-compose.yml`, `docker-compose.yaml`, `compose.yml`,
    `compose.yaml`.
- *Alternative:* settings. Rejected: these are facts about file conventions (like manifest
  names), not weights; a change is a code change with a test.

**D4. Storage: four nullable booleans, refreshed with dependencies.**
- `Repository.has_ci`, `has_tests`, `has_dev_environment`, `has_docker_compose`
  (`BooleanField(null=True)`); migration adds them as null, no backfill.
- `_store` sets them in the `dependencies` branch, next to `replace_dependencies`, so they share
  `dependencies_synced_at` and the claim's transaction. Null = never analyzed for setup.
- `services/evaluation/export.py` and the benchmark dataset do not read them (Non-Goals).

**D5. API: `setup` next to `openness`.**
- `SetupSerializer(ModelSerializer[Repository])` with `ci`, `tests`, `dev_environment`,
  `docker_compose` (`BooleanField(source=..., allow_null=True)`), added to
  `RecommendationSerializer` as `setup` (so list items and the detail have it). The
  repository is already loaded with the recommendation; no extra query.

**D6. Interface wording.**
- `features/recommendations/messages.ts`: `SETUP_TEXT` (card words: "CI", "tests", "dev
  container", "Docker Compose") and `SETUP_LABELS` (detail terms: "CI configuration", "Tests",
  "Dev container or Gitpod", "Docker Compose"), in that order.
- Card: the found facts joined with " · " in the footer next to the activity indicator; nothing
  when none is found or all are unknown.
- Detail page: a "Setup" group after "Contribution guidelines" with `foundOrNot(value)`: "Found",
  "Not found", "Not available" (shared `UNAVAILABLE`). The group's note says detection looks at
  the repository root only.

## Risks / Trade-offs

- [False "not found": tests next to the code (Go `_test.go`, Rust `#[cfg(test)]`), CI only in a
  monorepo subfolder] → Wording is "Not found", never "No"; cards only mention what was found.
- [False "found": a `test` folder of fixtures, a stale `.travis.yml`] → The facts are shown as
  observations, never scored; acceptable for a hint.
- [GitHub budget: one more request per analyzed repository with `.github`] → Only on the weekly
  dependencies refresh, behind the ETag cache; none when another CI marker already matched.
- [Existing repositories show nothing until their dependencies refresh (up to 168 h)] → Unknown
  renders as "Not available" and no card line; no forced refresh.

## Migration Plan

- Migration adds four nullable columns (no default needed, safe online). Deploy backend, then
  the regenerated schema with the frontend.
- Rollback: revert the release; reversing the migration drops the columns.
