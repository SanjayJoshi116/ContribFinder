## MODIFIED Requirements

### Requirement: Conditional requests
The system SHALL send conditional requests (ETag) for resources it has fetched before. A `304 Not Modified` response SHALL reuse the previously stored data and SHALL NOT be treated as an error. A `304` SHALL keep the stored response usable for another full cache lifetime, so an unchanged resource keeps getting conditional requests. The stored responses only save requests. When they cannot be read or written (for example the cache server is unreachable), the request SHALL be sent without a condition and its result used. The request and the job SHALL NOT fail because of the cache. After such an error the process SHALL skip the stored responses for a configured backoff, so later requests do not each wait for the cache to time out.

#### Scenario: Unchanged repository list
- **WHEN** a second sync requests the repository list and GitHub answers 304 Not Modified
- **THEN** the previously fetched repository list is reused and the sync completes successfully

#### Scenario: Unchanged resource stays conditional
- **WHEN** a resource answered 304 shortly before its stored response would expire, and it is requested again after that original expiry time but within one cache lifetime of the 304
- **THEN** the request is still sent with the stored ETag, and a further 304 reuses the stored data

#### Scenario: Cache unavailable during a job
- **WHEN** a sync or repository analysis requests GitHub data while the response cache cannot be reached
- **THEN** the request is sent without a condition, its result is stored as usual, and the job continues without failing or retrying because of the cache

#### Scenario: Backoff after a cache error
- **WHEN** a request in a process has just failed to reach the response cache, and the same process sends another request within the configured backoff
- **THEN** that request does not try the cache and is sent without a condition
