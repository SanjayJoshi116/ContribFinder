## ADDED Requirements

### Requirement: API availability without the cache
Requests that read or write only PostgreSQL SHALL keep working when the cache (Redis) is unavailable. Sessions SHALL be stored in and read from PostgreSQL, without depending on the cache. When request throttling cannot reach the cache, the request SHALL be allowed, the problem SHALL be logged as a warning without request data, and further throttle checks in the same process SHALL skip the cache for a configured backoff (default 30 seconds), so requests do not each wait for the cache's connection timeout. Throttling SHALL resume on its own once the cache is reachable again.

#### Scenario: Redis down during a dashboard read
- **WHEN** Redis is unreachable and a signed-in user requests `GET /api/v1/recommendations`
- **THEN** the system responds with HTTP 200 and the user's recommendations from PostgreSQL, and the user stays signed in

#### Scenario: Throttle cache error backs off
- **WHEN** Redis is unreachable and one process serves two API requests within the backoff period
- **THEN** both requests are answered, a warning is logged, and only the first request tries the cache for throttling

#### Scenario: Throttling resumes
- **WHEN** Redis becomes reachable again and the backoff period has passed
- **THEN** requests are counted against their throttle limits again, and requests over the limit get HTTP 429

#### Scenario: Existing sessions keep working
- **WHEN** a user signed in before the session storage change and makes a request afterwards
- **THEN** the session is still valid and the request is authenticated
