## Why

Review sweep of `apps/backend/services/ranking/` (config, pipeline, score, explain, freshness,
activation). `/code-review` reported 10 findings, all verified against the code (RNK-1…RNK-10 in
`Bug_Backlog.md`); `/security-review` found nothing. Two affect users today: the freshness sweep
waits 6 hours after any recent failure even when a later generation succeeded, and activating a
new configuration never regenerates developers who have no recommendations.

## What Changes

- **RNK-1** Freshness backs off only when the developer's *latest* finished generation failed.
- **RNK-2** Freshness also marks due a developer whose last completed generation ran under a
  configuration that is no longer active (read from the job's `config_version` metadata), so a
  developer with zero recommendations is regenerated on activation.
- **RNK-3** `framework_match` skips technologies whose repository weight is 0, as `skill_match`
  does (latent: every stored configuration weights topics 0.6).
- **RNK-4** Openness evidence names only affordances worth more than 0 points (latent).
- **RNK-5** Activation fails when the configuration being activated is gone at the switch,
  instead of leaving no active configuration and auditing a success.
- **RNK-6** The freshness sweep keeps starting jobs for other developers when queuing one fails.
- **RNK-7** A reason whose contribution rounds to 0 at 4 decimals is not created.
- **RNK-8** Remove the unused `score.weighted_score`; `explain.reasons` takes the contributions
  scoring computed (no `params=None` default that drops relevance scaling).
- **RNK-9** Issues are loaded and matched only when issue fit or difficulty fit is weighted above 0.
- **RNK-10** Folded into RNK-8: `Scored` carries its contributions; reasons reuse them.

No ranking change: stored configurations hit none of RNK-3, RNK-4, RNK-9, and RNK-7 drops only
reasons stored as weight 0.0. `baselines.json` must not move.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `recommendation-engine`: "Relevance signals" (framework weight 0, openness evidence),
  "Recommendation freshness" (latest-failure backoff, config change without recommendations,
  per-developer queuing failure).
- `recommendation-explanations`: "Reasons from scoring evidence" (stored contribution above 0;
  scenarios for weight-0 framework and 0-point openness).
- `recommendation-evaluation`: "Activating a configuration" (configuration gone at the switch).

## Impact

- Code: `services/ranking/freshness.py`, `activation.py`, `explain.py`, `score.py`,
  `pipeline.py`, `service.py`; `services/matching/signals.py`; possibly `services/jobs.py`
  (`on_commit(..., robust=True)` for the generation send).
- Tests: freshness, activation, signals, explanations, pipeline; tests calling
  `weighted_score` or `reasons(signals, weights)` move to the new signatures.
- No API, migration, OpenAPI or frontend change. Patch release 0.12.66.
