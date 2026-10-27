## 1. Backend (D1, D2)

- [x] 1.1 `core/csp.py` `ContentSecurityPolicyMiddleware` (sets the header only when absent; JSON
  media types → API policy, otherwise HTML policy); `MIDDLEWARE` after `SecurityMiddleware`;
  `CONTENT_SECURITY_POLICY_API` and `CONTENT_SECURITY_POLICY_HTML` defaults in `base.py`.
- [x] 1.2 `core/checks.py`: new error id for an empty or non-string policy; covered by
  `run_startup_checks`.
- [x] 1.3 Tests: the `api-platform` scenarios (API JSON incl. a 401 and a 404 error, admin page
  with the HTML policy, a view's own header kept, empty policy refused by the check); the
  existing security-header test still passes.

## 2. Frontend (D3, D4)

- [x] 2.1 `apps/frontend/csp.config.ts` (policy string) and a build-only plugin in
  `vite.config.ts` (`apply: 'build'`, `transformIndexHtml`, meta tag first in `<head>`).
- [x] 2.2 Vitest: the plugin output for a sample `index.html`; the policy holds `script-src
  'self'`, `connect-src 'self'`, `object-src 'none'`, `base-uri 'none'`, the avatar origin; the
  plugin does not apply to `serve`.
- [x] 2.3 After `npm run build`: `dist/index.html` has the meta tag and no `<script>` without
  `src`.

## 3. Verification and housekeeping

- [x] 3.1 Backend `ruff check`, `ruff format --check`, `mypy`, `pytest`; `git diff --exit-code
  apps/backend/evaluation/baselines.json`. Frontend `lint`, `format:check`, `typecheck`, `test`,
  `build`; `npm run e2e` (dev server, unchanged by the policy) and `api:sync` with no schema
  change.
- [x] 3.2 Manual: `npm run build && npm run preview` with the backend running; sign in (or a
  seeded session), open the dashboard and a recommendation; no CSP violation in the console;
  `curl -I` an API endpoint and an admin page shows the two policies.
- [x] 3.3 Docs: README (security headers; serving the build with the same policy as a header plus
  `frame-ancestors 'none'`), `ideas.md` §5 CSP to "Shipped", CLAUDE.md §7 shipped entry (K-1
  carry-over unchanged) and Ideas paragraph, `features.txt`.
- [x] 3.4 Release housekeeping (CLAUDE.md §8): patch 0.12.30; `CHANGELOG.md`, README status line,
  lockfiles, `check:version`.
