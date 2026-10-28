## Context

CI (`.github/workflows/ci.yml`) has four jobs (backend, frontend, api-contract, e2e) triggered by
pull requests and pushes to `main`; its concurrency group keys pushes by commit (spec
`developer-tooling`, "Every commit on main is checked"). There are three locked dependency sets:
`apps/backend/uv.lock` (Python), `apps/frontend/package-lock.json` (SPA, bundled into the build)
and the root `package-lock.json` (runner scripts, ESLint, Prettier). Runner scripts live in
`scripts/` with Node built-in tests, ESLint and Prettier, and find uv through `scripts/uv.mjs`.
See proposal.md for motivation; the requirement is in the `developer-tooling` delta.

## Goals / Non-Goals

**Goals:**
- One command, `npm run audit:deps`, that CI and a developer run alike.
- Accepted advisories in one reviewed file, for both ecosystems.
- The weekly run costs one short job, not the whole test suite.

**Non-Goals:**
- Automatic upgrade pull requests (Dependabot) and code scanning (CodeQL).
- Auditing the Docker base images or the Python interpreter itself.
- Failing on npm low/moderate advisories (reported only).

## Decisions

### D1. A separate workflow, `audit.yml`

Triggers: `pull_request`, `push` to `main`, weekly `schedule`, `workflow_dispatch`. One job,
`dependency-audit`, with its own concurrency group (`audit-<ref or sha>`, cancelling only on pull
requests, as `ci.yml` does).
*Alternative:* a job in `ci.yml` plus a schedule there. Rejected: the schedule would rerun the
backend, frontend and e2e jobs weekly (or need an `if:` on each), and a scheduled run would share
the per-commit concurrency group with the push run of the same commit.

### D2. A runner script, `scripts/audit.mjs`

It reads `audit-accepted.json`, runs the three audits, applies the accepted list and exits 1 when
anything unaccepted remains, printing one line per finding (ecosystem, package, version,
advisory id, severity, accepted or not). The decision is pure functions, tested with
`node --test` like the other runners:
- `validateAccepted(entries)`: every entry has `ecosystem` (`pypi` | `npm`), `id`, `package`,
  `reason` and `accepted_on` (ISO date); duplicates and unknown fields are errors, so a typo
  never accepts silently.
- `pythonFindings(report, accepted)`: from `pip-audit --format json`; an advisory matches an
  entry by its id or any alias (PYSEC, GHSA, CVE).
- `npmFindings(report, accepted)`: from `npm audit --json` (lockfile v3 report); every advisory
  (`via` entry with a `source`) at its own severity; high and critical fail, low and moderate are
  printed only. An entry matches by GHSA id (taken from the advisory URL).
*Alternative:* inline workflow steps with `pip-audit --ignore-vuln` and `npm audit
--audit-level=high`. Rejected: npm audit has no way to accept one advisory, the accepted list
would live in YAML in two places, and nobody could run the same check locally.
*Alternative:* `audit-ci` (npm package with allowlists). Rejected: a new dependency for a filter
of a few lines, and it does not cover Python.

### D3. Python: audit the export of the lockfile, never resolve

`uv export --frozen --format requirements-txt --no-emit-project` (with hashes) piped to
`uvx pip-audit --requirement - --disable-pip --format json` (or a temp file if stdin is not
supported). `--disable-pip` with hashed, fully pinned requirements audits exactly the locked
versions without installing or resolving. Dev dependencies are included: they run in CI.
`pip-audit` runs through `uvx` with a pinned version, so it is not a project dependency.

### D4. npm: `npm audit --json` per lockfile, no install

`npm audit` reads `package-lock.json` and queries the registry's bulk advisory endpoint; it does
not need `node_modules`. Run in `apps/frontend` and at the root. Dev dependencies are included
(build tools and linters run in CI); the severity threshold, not the dependency type, decides.

### D5. Network failure is a failure

If an audit cannot reach its advisory source, or its output is not the expected JSON, the script
exits 2 with the reason. Spec: no audit may pass silently. Locally a developer behind a blocking
registry setting sees the cause instead of a green result.

## Risks / Trade-offs

- [A new advisory in a transitive dev dependency turns CI red with nothing to upgrade] →
  accept it in `audit-accepted.json` with a reason and date; the weekly run keeps re-checking,
  and the review of that file is the reminder to drop the entry.
- [Advisory databases are flaky] → D5 fails loudly; rerun on demand (`workflow_dispatch`).
- [npm audit's JSON format changes] → the parser validates the shape (D5) and its tests use
  recorded reports.
- [Accepted entries go stale] → `accepted_on` is required and printed with each accepted finding;
  an entry that matches nothing is printed as unused, so it can be removed.

## Migration Plan

1. Land the script, its tests, `audit-accepted.json` (empty list) and the workflow.
2. Run `npm run audit:deps` once; upgrade what an upgrade fixes, accept the rest with reasons.
3. Rollback: delete `audit.yml`; nothing else depends on it.
