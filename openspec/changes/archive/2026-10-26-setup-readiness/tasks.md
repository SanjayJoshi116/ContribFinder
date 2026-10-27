## 1. Detection and fetching (D1, D2, D3)

- [x] 1.1 `services/github/client.py`: `list_contents(full_name, path)` (`[]` on 404 or a
  non-list body, `@_parses_response`); `list_root_contents` delegates to it. Fixture tests:
  a listing, 404, a file path (object body).
- [x] 1.2 `services/repositories/setup.py`: `SetupFacts`, marker tables, `detect(root,
  workflows)`, `needs_workflows(root)` (a `.github` dir and no other CI marker). Unit tests per
  fact: each marker, case-insensitive names, file vs dir type, prefixes (`jest.config.ts`),
  workflows with and without `.yml`/`.yaml` files, empty root.
- [x] 1.3 `services/github/storage.read_manifests(client, full_name, entries=None)`: uses the
  given entries instead of listing again. GitHub sync call unchanged; test that a call with
  entries makes no listing request.

## 2. Storage and analysis (D4)

- [x] 2.1 `repositories/models.py`: `has_ci`, `has_tests`, `has_dev_environment`,
  `has_docker_compose` (`BooleanField(null=True, blank=True)`); migration `repositories.0009`
  (`makemigrations --settings config.settings.test`).
- [x] 2.2 `services/repositories/analysis.py`: the `dependencies` part lists the root once,
  reads manifests from it, fetches `.github/workflows` only when `needs_workflows`, and `_store`
  writes the four facts with `dependencies_synced_at`.
- [x] 2.3 Analysis tests (respx fixtures):
  - all four found (spec scenario "Setup facts found");
  - nothing found: no workflows request, analysis succeeds;
  - `.github` without `workflows` (404) or with only `README.md` → CI not found; `.travis.yml`
    → CI found and no workflows request;
  - a refresh of another part only (e.g. `activity`) leaves the facts unchanged; null until the
    dependencies part runs;
  - ranking unaffected: `rank_pool` on two candidates differing only in facts gives the same
    scores and reasons.

## 3. API (D5)

- [x] 3.1 `recommendations/serializers.py`: `SetupSerializer`; `setup` on
  `RecommendationSerializer` (list and detail). No added queries (existing query-count tests
  pass).
- [x] 3.2 API tests: list and detail return `setup` with true/false/null; `npm run api:sync`
  (OpenAPI `1.0.0`, additive).

## 4. Frontend (D6)

- [x] 4.1 `features/recommendations/messages.ts`: `SETUP_TEXT`, `SETUP_LABELS`.
- [x] 4.2 `RecommendationCard.tsx`: setup line from the found facts ("CI · tests"), none when
  nothing is found or all are null.
- [x] 4.3 `RecommendationDetailPage.tsx`: "Setup" group after "Contribution guidelines" with
  Found / Not found / Not available and the root-only note.
- [x] 4.4 Tests (Vitest + Testing Library): card line with two facts, no line for all false and
  all null; detail page wording for found, not found and null.

## 5. Verification and housekeeping

- [x] 5.1 Backend `ruff check`, `ruff format --check`, `mypy`, `pytest`; frontend lint,
  format:check, typecheck, test, build; `npm run e2e` (cards change); root `check:version`;
  `git diff --exit-code apps/backend/evaluation/baselines.json`.
- [x] 5.2 Manual: refresh one repository's dependencies part on the dev database
  (`lifecycle`/backlog or the analysis service) and check its card line and detail page.
- [x] 5.3 Docs: README (setup facts on cards and the detail page), CLAUDE.md §7 shipped entry
  (K-1 carry-over unchanged), `ideas.md` §8 to "Shipped" and the priority table, `features.txt`.
- [x] 5.4 Release housekeeping (CLAUDE.md §8): patch 0.12.24; `CHANGELOG.md`, `features.txt`,
  README status line; lockfiles.
