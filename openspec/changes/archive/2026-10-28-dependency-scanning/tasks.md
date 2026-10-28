## 1. Accepted advisories

- [x] 1.1 `audit-accepted.json` at the repository root: an empty JSON list, with the entry shape
  (`ecosystem`, `id`, `package`, `reason`, `accepted_on`) documented in the README.
- [x] 1.2 `validateAccepted(entries)` in `scripts/audit.mjs`: required fields, `ecosystem` in
  {`pypi`, `npm`}, ISO `accepted_on`, no unknown fields, no duplicate (ecosystem, id); returns
  the errors.

## 2. Audit script (`scripts/audit.mjs`, a CLI guarded by `isMain`)

- [x] 2.1 `pythonFindings(report, accepted)`: parse `pip-audit --format json`; one finding per
  (package, advisory) with id, aliases, fixed versions; accepted when an entry's id equals the
  id or an alias; throws on an unexpected shape.
- [x] 2.2 `npmFindings(report, accepted)`: parse `npm audit --json` (lockfile v3); one finding
  per advisory (`via` entries with a `source`), GHSA id from its URL, its own severity; fails
  only for high and critical; accepted by GHSA id; throws on an unexpected shape.
- [x] 2.3 `unusedAccepted(accepted, findings)`: entries that matched nothing.
- [x] 2.4 Runner: Python via `scripts/uv.mjs` (`uv export --frozen --format requirements-txt
  --no-emit-project` with hashes, then `uvx pip-audit==<pinned> --disable-pip --format json`),
  npm audit in `apps/frontend` and the root; prints one line per finding and each unused
  entry; exit 0 clean, 1 unaccepted findings, 2 audit could not run or invalid accepted file.
- [x] 2.5 Root `package.json` script `audit:deps`.

## 3. Tests (`scripts/audit.test.mjs`, `node --test`)

- [x] 3.1 Recorded pip-audit and npm audit reports (clean, vulnerable, accepted by alias, low
  severity only, malformed) as fixtures in the test file.
- [x] 3.2 Each spec scenario that the script decides: vulnerable Python package fails, low/
  moderate npm advisory reports without failing, accepted advisory passes and stays listed,
  unused entry reported, invalid accepted file refused, malformed report → error.
- [x] 3.3 `npm run test:scripts`, `lint:scripts`, `format:scripts` pass.

## 4. CI

- [x] 4.1 `.github/workflows/audit.yml`: `pull_request`, `push` to `main`, weekly `schedule`,
  `workflow_dispatch`; one `dependency-audit` job (setup-uv, setup-node, `npm run audit:deps`;
  no installs, the audit reads only the lockfiles), `timeout-minutes`, `permissions: contents: read`, own concurrency group
  cancelling only on pull requests.

## 5. First audit

- [x] 5.1 Run `npm run audit:deps`; upgrade what an upgrade fixes (lockfiles refreshed, tests
  pass), accept the rest in `audit-accepted.json` with reasons. Record the result in the
  release notes.

## 6. Docs and release

- [x] 6.1 README: "Dependency audit" (command, what fails, how to accept an advisory);
  CLAUDE.md §4 layout (`audit.mjs`, `audit-accepted.json`, `audit.yml`), §6 command, §7 entry;
  `ideas.md` §5 moved to Shipped; `features.txt`.
- [x] 6.2 Release housekeeping (CLAUDE.md §8): patch 0.12.34, `CHANGELOG.md`, lockfiles,
  `check:version`; archive the change.
