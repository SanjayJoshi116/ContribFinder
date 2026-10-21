## MODIFIED Requirements

### Requirement: Configuration validated at startup
Every process that serves requests or runs background jobs with production settings SHALL validate the application configuration before it starts work, and SHALL refuse to start when validation reports an error (for example missing token encryption keys or invalid evidence weights). Validation SHALL cover every numeric, interval and structured setting the application reads, including job and sync settings (attempts, cooldown, stale-after and recovery intervals), GitHub request caps and timeouts, OAuth state limits, repository grace and retry windows, analysis concurrency, session lifetime, the Redis socket timeout, and the experience thresholds (known signals, each a pair of non-negative numbers in order), so a value that would loop, never finish or fail every job blocks startup instead. Every serving entry point SHALL default to the same settings module, so the web tier and the workers never run under different settings by accident.

#### Scenario: Invalid configuration blocks the web server
- **WHEN** the production web server starts with an invalid required setting (for example empty token encryption keys)
- **THEN** it exits with an error naming the failed check, before accepting any request

#### Scenario: Invalid configuration blocks the worker
- **WHEN** a background worker or the scheduler starts with production settings and an invalid required setting
- **THEN** it exits with an error naming the failed check, before running any job

#### Scenario: Zero recovery interval
- **WHEN** a process starts with production settings and `JOB_RECOVERY_INTERVAL_SECONDS` set to 0
- **THEN** it exits with an error naming the setting, instead of scheduling recovery in a loop

#### Scenario: Malformed experience thresholds
- **WHEN** a process starts with production settings and an `EXPERIENCE_THRESHOLDS` entry that names an unknown signal, is not a pair of non-negative numbers, or has its intermediate threshold above its experienced one
- **THEN** it exits with an error naming the setting, instead of failing every profile analysis

#### Scenario: Settings module not set
- **WHEN** the web server, worker or scheduler starts without an explicit settings module
- **THEN** all of them use the production settings
