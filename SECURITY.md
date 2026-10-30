# Security policy

ContribFinder signs users in with GitHub and stores their GitHub access tokens (encrypted at
rest). Please report security problems privately, not in a public issue.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting: the repository's **Security** tab, then
**Report a vulnerability**. Include what you found, how to reproduce it and what an attacker
could do with it. You will get an answer within 7 days; please give a fix time before
disclosing publicly.

In scope: anything that exposes a GitHub token, a session, another user's data or a secret;
bypasses authentication, authorization, CSRF or the Content Security Policy; or lets one user
affect another. Out of scope: findings that need a compromised server or `.env`, and denial of
service by volume.

## Supported versions

Only the latest release on `main` gets security fixes.

## How secrets are handled

GitHub tokens are encrypted with `TOKEN_ENCRYPTION_KEYS` (MultiFernet), never returned to the
browser, logged or put in URLs, and revoked and deleted on disconnect. The OAuth app asks for no
scopes (public data only). See the README "Secrets" section and `CLAUDE.md` §3.
