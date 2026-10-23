## ADDED Requirements

### Requirement: Activating a configuration
An operator SHALL activate a stored scoring configuration through a management command that
takes its version, and the admin activation action SHALL apply the same rule. Activation SHALL
first validate the configuration as stored configurations are validated; an unknown version or
invalid configuration SHALL be refused with an error and change nothing. Unless forced, it
SHALL evaluate the configuration against the active one on the selection benchmark with the
same defaults as the evaluation command, and SHALL refuse it when it is not an improvement
under the improvement rule, naming each failed metric and changing nothing. Forcing SHALL
require a non-empty reason and SHALL only be possible from the command, not from the admin
action. A successful activation SHALL deactivate the previous configuration and activate the
new one in one step, so that exactly one configuration is active at every moment, and SHALL
record an audit event with the new and previous versions, whether it was forced, the reason
and any failed metrics. Activating the configuration that is already active SHALL change
nothing, record nothing and report that it is already active. The acceptance holdout check
(see "Replacing the active configuration") SHALL remain the operator's step before activation;
the command SHALL NOT read a holdout.

#### Scenario: Activation refused by the benchmark
- **WHEN** `v2-deterministic` is active and an operator activates `v1-deterministic` without forcing
- **THEN** the command fails naming the metrics where `v1-deterministic` is not an improvement, and `v2-deterministic` stays the only active configuration

#### Scenario: Forced rollback with a reason
- **WHEN** an operator forces the activation of `v1-deterministic` with the reason "rollback after incident"
- **THEN** `v1-deterministic` is the only active configuration, and an audit event records `v1-deterministic`, `v2-deterministic` as the previous version, that it was forced, the reason and the failed metrics

#### Scenario: Forced without a reason
- **WHEN** an operator forces an activation and gives no reason
- **THEN** the command fails before evaluating, and nothing changes

#### Scenario: Improvement activated
- **WHEN** an operator activates a stored configuration that is an improvement over the active one on the selection benchmark
- **THEN** it becomes the only active configuration and an audit event records it as not forced

#### Scenario: Unknown version
- **WHEN** an operator activates `v9-missing`
- **THEN** the command fails with an error naming the version, and nothing changes

#### Scenario: Already active
- **WHEN** an operator activates the configuration that is already active
- **THEN** the command reports that it is already active, and no audit event is recorded

#### Scenario: Admin action refused
- **WHEN** an administrator uses the admin activation action on a configuration that is not an improvement over the active one
- **THEN** the admin shows the failed metrics, points to the command for a forced activation, and the active configuration is unchanged
