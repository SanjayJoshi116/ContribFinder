## Context

Findings: `Bug_Backlog.md` batch 47. `e2e_seed --attempts N` builds `N` copies of each
data-changing user (`<user>`, `<user>-retry1`, …); `playwright.config.ts` passes `RETRIES + 1`;
`fixtures.ts` `sessionId(user, retry)` picks the copy by `testInfo.retry`. `--repeat-each` runs a
test again with the same `retry` 0, and a second `--ui` run reuses servers without a re-seed.

## Goals / Non-Goals

**Goals:** fail loudly and explain, instead of silently reusing changed data; tighten the dev
branch and the Vitest excludes; make the canary robust.

**Non-Goals:** supporting `--repeat-each` or repeated `--ui` runs (would need copies per repeat
and a re-seed per run); E2EC-2 and E2EC-5 (accepted).

## Decisions

**D1. Refuse, not extend (E2EC-1).** `sessionId(user, testInfo)`: for a user mapped to a list,
`testInfo.repeatEachIndex > 0` throws "e2e: --repeat-each is not supported for <user> (it changes
data; each attempt needs a fresh seeded copy). Run npm run e2e again." A missing copy for
`retry` throws "… attempt N, but the seed built M; set RETRIES in playwright.config.ts (CLI
--retries is not supported)." Read-only users (one string) keep working under any flag. A short
comment above `RETRIES` and one README line list the unsupported flags. Alternative: seed
`attempts × repeats` copies through an env var; rejected, it adds config for a debugging flag and
still breaks on a second `--ui` run.

**D2. One serve option (E2EC-3).** `SERVE = --host localhost --port 5174 --strictPort`, used by
both branches.

**D3. Comment (E2EC-4).** "the others only read (opening a detail page records a view)".

**D4. Defaults kept (E2EC-6).** `exclude: [...configDefaults.exclude, 'e2e/**', 'dist-e2e/**']`
(`configDefaults` from `vitest/config`).

**D5. Canary (E2EC-7).** `const taken = policyViolations.take()`; `expect(taken.length)
.toBeGreaterThan(0)`; every entry `toContain` the directive.

## Risks / Trade-offs

- [Someone relied on `--retries` working locally] → It already threw past the seeded copies; the
  message now says how to raise `RETRIES`.
