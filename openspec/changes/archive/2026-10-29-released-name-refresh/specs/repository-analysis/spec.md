## MODIFIED Requirements

### Requirement: Background refresh
A periodic background task SHALL refresh, in batches of a configured size (default 50), the repositories that are in at least one developer's pool and are STALE, DISCOVERED and not analyzed within the configured grace period (default 10 minutes), or FAILED and due for retry. A refresh SHALL fetch only the data types that are stale when it runs, also when it was queued for particular data types, and SHALL use conditional requests. Repositories in no pool SHALL NOT be refreshed. Refreshing SHALL NOT block any HTTP request.

A repository queued for a refresh SHALL NOT be queued again while that refresh can still run: until the configured stale-job time plus the maximum retry delay has passed since it was queued, or until an analysis completes or fails it. Overlapping background runs SHALL NOT queue the same repository twice. The recovery of an analysis abandoned by a dead worker SHALL NOT wait for this. A refresh that finds nothing stale on a repository that is not STALE (another analysis refreshed it after it was queued) SHALL change nothing, not even the time of the last transition.

A repository that gives up its name and is in at least one developer's pool SHALL have its refresh queued once the change that released the name is committed, without waiting for the periodic task, and SHALL count as queued from then on. This SHALL NOT apply to a repository that another analysis holds, that is FAILED, or whose queued refresh can still run; those keep the paths above. It SHALL NOT apply when the application's client credentials are not configured or when background tasks run inline: the periodic task stays the fallback, and storing a repository SHALL NOT run another repository's analysis. A recorded refresh failure SHALL NOT hold this refresh back.

A refresh that ends without being retried and without marking the repository FAILED (for example a rate-limit wait beyond the maximum, transient failures that used up the attempts, or rejected client credentials) SHALL record its error code and time on the repository, SHALL keep the repository's state and its stored data, and SHALL NOT be queued again by the background task until a configured delay (default 60 minutes) has passed. The failure SHALL NOT be recorded on a repository that another analysis holds, or that another analysis completed or failed after this refresh started. The delay SHALL NOT hold back a FAILED repository's retry or the recovery of an analysis abandoned by a dead worker. A later completed analysis SHALL clear the recorded error.

#### Scenario: Only stale parts fetched
- **WHEN** a STALE repository has only stale metadata and activity signals
- **THEN** the refresh fetches metadata and activity data, does not fetch the README, community files or manifests, and the repository ends RECOMMENDABLE or INDEXED

#### Scenario: Queued part no longer stale
- **WHEN** an issues refresh was queued, and another analysis fetched the repository's issues before it runs
- **THEN** the refresh does not fetch the issues again

#### Scenario: Queued part refreshed meanwhile
- **WHEN** an issues refresh was queued for a STALE repository, and a discovery run's analysis refreshed it to RECOMMENDABLE before the refresh runs
- **THEN** the refresh fetches nothing and leaves the repository's state and transition time unchanged

#### Scenario: Queued refresh not queued twice
- **WHEN** a STALE repository was queued 15 minutes ago and its refresh is waiting for a retry
- **THEN** the next background run does not queue it again

#### Scenario: Lost refresh queued again
- **WHEN** a STALE repository was queued and its refresh never ran, and the stale-job time plus the maximum retry delay has passed
- **THEN** the next background run queues it again

#### Scenario: Orphan repository not refreshed
- **WHEN** a STALE repository is in no developer's pool
- **THEN** the background task does not refresh it

#### Scenario: Released name refreshed right away
- **WHEN** a discovery search stores `org/tool` with GitHub ID 2 while the pooled RECOMMENDABLE repository with GitHub ID 1 holds that name
- **THEN** after the search's transaction commits, a refresh of the repository with GitHub ID 1 is queued and stamped as queued, the next periodic run does not queue it again, and its analysis looks it up by GitHub ID

#### Scenario: Released name rolled back
- **WHEN** the transaction that released a name rolls back
- **THEN** no refresh is queued for the holder

#### Scenario: Released name of a repository in no pool
- **WHEN** a repository in no developer's pool gives up its name
- **THEN** no refresh is queued for it

#### Scenario: Released name while analyzed
- **WHEN** a repository gives up its name while another analysis holds it
- **THEN** no refresh is queued for it, and it is not stamped as queued

#### Scenario: Released name without a worker
- **WHEN** a pooled repository gives up its name while background tasks run inline
- **THEN** no refresh runs, it is not stamped as queued, and the periodic task refreshes it later

#### Scenario: Refresh fails without a retry
- **WHEN** a STALE repository's refresh keeps getting 503 until its attempts are used up
- **THEN** the repository is still STALE and eligible as before, its recorded error is `github_unavailable`, and the background task does not queue it again within the configured delay

#### Scenario: Rejected client credentials
- **WHEN** GitHub rejects the application's client credentials during a refresh
- **THEN** the repository keeps its state, its recorded error is `github_auth_invalid`, and the background task does not queue it again within the configured delay

#### Scenario: Completed by another run meanwhile
- **WHEN** a refresh fails after another analysis completed the same repository
- **THEN** the repository keeps the other analysis's result with no recorded error

#### Scenario: Refresh retried after the delay
- **WHEN** the configured delay has passed since a recorded refresh failure, and the next refresh completes
- **THEN** the background task queues the repository, and after the analysis it has no recorded error
