## ADDED Requirements

### Requirement: Dependencies are audited for known vulnerabilities
CI SHALL audit every locked dependency set (the backend's Python lockfile, the frontend's npm
lockfile and the runners' npm lockfile) against public vulnerability advisories. The audit SHALL
use exactly the locked versions, never a fresh resolution. A Python dependency with any known
vulnerability, or an npm dependency with a high or critical advisory, SHALL fail CI. The audit
SHALL run on every commit CI checks and also on a weekly schedule and on demand, so an advisory
published after the last commit is still reported. An advisory that cannot be fixed yet SHALL be
accepted only by an explicit entry in the repository naming the advisory, the reason and the
date; no audit SHALL be skipped or allowed to fail silently.

#### Scenario: Vulnerable locked dependency
- **WHEN** a commit's backend lockfile pins a package version with a published advisory
- **THEN** the CI run for that commit fails and names the package and the advisory

#### Scenario: Advisory published later
- **WHEN** an advisory is published for a locked npm dependency at high severity after the last commit to `main`
- **THEN** the next weekly run fails without any new commit

#### Scenario: Low-severity npm advisory
- **WHEN** an npm dependency has only a low or moderate advisory
- **THEN** the audit reports it and CI does not fail

#### Scenario: Accepted advisory
- **WHEN** an advisory has no fixed version and the repository records it as accepted with a reason and a date
- **THEN** the audit passes and the accepted advisory stays visible in the repository
