## Why

Nothing checks the Python, frontend or runner dependencies for known vulnerabilities: CI lints,
type-checks and tests, but a dependency with a published advisory passes every job, and an
advisory published after a commit is never seen at all (`ideas.md` §5). The app holds encrypted
GitHub tokens and session cookies, so a vulnerable Django, DRF, cryptography or bundled frontend
package matters. The audit tools are free, need no account and run in seconds.

## What Changes

- New CI job `dependency-audit`:
  - backend: `pip-audit` against the locked dependencies exported from `apps/backend/uv.lock`
    (hashes, no resolution), failing on any known vulnerability;
  - frontend and runners: `npm audit --audit-level=high` against `apps/frontend/package-lock.json`
    and the root `package-lock.json`, failing on high or critical advisories.
- The workflow also runs on a weekly schedule (and on demand), so an advisory published after
  the last commit still turns CI red.
- An advisory that cannot be fixed yet is accepted explicitly: Python by `--ignore-vuln <id>`
  with a dated reason next to it, npm by an `overrides` pin or a raised threshold note, never by
  silently dropping the job.
- README gains the local commands, and the change records the first audit's findings
  (fixed by upgrading, or accepted with a reason).
- Not in scope: Dependabot or CodeQL (they open pull requests or need repository settings; a
  later change if wanted), and the other §5 items (GitHub budget model, accessibility,
  observability).

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `developer-tooling`: new requirement that CI audits every locked dependency set for known
  vulnerabilities, on every checked commit and on a weekly schedule, with accepted advisories
  recorded explicitly.

## Impact

- `.github/workflows/ci.yml`: new job and `schedule` / `workflow_dispatch` triggers (the existing
  concurrency group already keys pushes by commit; scheduled runs key the same way).
- `apps/backend/uv.lock`, `apps/frontend/package-lock.json`, `package-lock.json`: only if the
  first audit finds something that an upgrade fixes.
- `README.md` (local audit commands), `CLAUDE.md` §6/§7, `ideas.md` §5, `features.txt`,
  `CHANGELOG.md`.
- No application code, API, migration or ranking change.
