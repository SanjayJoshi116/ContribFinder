# api-platform Specification

## Purpose

Defines the shared API behaviour every ContribFinder capability relies on: a versioned base path, a machine-readable schema, health reporting, a single error format, and baseline protection (authentication, CSRF, throttling, security headers).

## Requirements

### Requirement: Versioned API base path
All application API endpoints SHALL be served under `/api/v1/`.

#### Scenario: Endpoint outside the base path
- **WHEN** a client requests an application endpoint without the `/api/v1/` prefix
- **THEN** the system responds with HTTP 404

### Requirement: OpenAPI schema
The system SHALL publish an OpenAPI 3 schema describing every `/api/v1/` endpoint, including request and response bodies and error responses. Frontend API types SHALL be generated from this schema.

#### Scenario: Schema is available
- **WHEN** a client requests `GET /api/v1/schema/`
- **THEN** the system returns a valid OpenAPI 3 document that includes the authentication and health endpoints

#### Scenario: Schema drift is detected
- **WHEN** the committed schema differs from the one generated from the backend code during CI
- **THEN** the CI run fails

### Requirement: Health check
The system SHALL expose an unauthenticated health endpoint that reports whether the database and cache/queue are reachable, without revealing configuration or secrets. The health endpoint SHALL NOT be rate limited and SHALL NOT be redirected to HTTPS, so infrastructure probes can call it at any rate over plain HTTP.

#### Scenario: All dependencies healthy
- **WHEN** a client requests `GET /api/v1/health/` and the database and Redis are reachable
- **THEN** the system responds with HTTP 200 and a body showing each dependency as `ok`

#### Scenario: A dependency is down
- **WHEN** Redis or the database cannot be reached
- **THEN** the system responds with HTTP 503 and marks the failing dependency as `unavailable`, with no connection strings or credentials

#### Scenario: Redis not configured in local development
- **WHEN** no Redis URL is configured (local development without Redis) and the database is reachable
- **THEN** the system responds with HTTP 200 and reports Redis as `not_configured`

#### Scenario: Production requires Redis
- **WHEN** the application starts with production settings and no Redis URL
- **THEN** startup fails with a configuration error

#### Scenario: Frequent probes are not throttled
- **WHEN** one client address requests `GET /api/v1/health/` more often than the anonymous rate limit allows
- **THEN** every request gets the health response (200 or 503), never HTTP 429

#### Scenario: Plain-HTTP probe in production
- **WHEN** production settings enforce HTTPS and a probe requests `GET /api/v1/health/` over plain HTTP
- **THEN** the system answers the health check directly instead of redirecting to HTTPS

### Requirement: Consistent error format
Every error response from `/api/v1/` SHALL use one JSON envelope with a stable machine-readable `code`, a human-readable `message`, and optional `details` (for example field-level validation errors). This SHALL also hold for errors raised by the web framework before a view runs, such as a disallowed host or an oversized request body.

#### Scenario: Validation error
- **WHEN** a request fails input validation
- **THEN** the system responds with HTTP 400 and a body of the form `{"error": {"code": "validation_error", "message": ..., "details": {...}}}`

#### Scenario: Unauthenticated request
- **WHEN** an unauthenticated client calls an endpoint that requires authentication
- **THEN** the system responds with HTTP 401 and `error.code` equal to `not_authenticated`

#### Scenario: Unexpected server error
- **WHEN** an unhandled exception occurs
- **THEN** the system responds with HTTP 500 and `error.code` equal to `server_error`, with no stack trace or internal detail in the body

#### Scenario: Framework-level bad request
- **WHEN** a request is rejected before reaching a view (for example an unexpected `Host` header or a body larger than the configured limit) and debug mode is off
- **THEN** the system responds with HTTP 400, a JSON body with `error.code` equal to `bad_request`, and no internal detail

#### Scenario: Framework-level permission denied
- **WHEN** a permission error is raised outside the API layer and debug mode is off
- **THEN** the system responds with HTTP 403, a JSON body with `error.code` equal to `permission_denied`

### Requirement: Authenticated by default
API endpoints SHALL require an authenticated session unless explicitly marked public. The only public endpoints in this change are health, schema, and GitHub sign-in start/callback.

#### Scenario: Protected endpoint without session
- **WHEN** a request without a session hits any endpoint not marked public
- **THEN** the system responds with HTTP 401

### Requirement: CSRF protection for state-changing requests
State-changing requests (POST, PUT, PATCH, DELETE) made with a session cookie SHALL require a valid CSRF token. The system SHALL provide a way for the frontend to get one.

#### Scenario: Missing CSRF token
- **WHEN** a signed-in client sends a POST without a valid CSRF token
- **THEN** the system rejects the request with HTTP 403 and `error.code` equal to `csrf_failed`

#### Scenario: Obtaining a CSRF token
- **WHEN** the frontend requests `GET /api/v1/auth/csrf/`
- **THEN** the system sets the CSRF cookie so later state-changing requests can include the token

### Requirement: Request throttling
The system SHALL limit request rates per user (authenticated) and per client address (anonymous), with stricter limits on sign-in endpoints. Limits SHALL be configurable. The client address SHALL be the address of the connecting peer unless the deployment declares how many trusted proxies sit in front of the application; only then SHALL the system take the client address from the forwarded-for header, counting from the right by that number of proxies. Values a client puts in forwarded headers SHALL NOT let it choose its own throttle identity.

#### Scenario: Throttle exceeded
- **WHEN** a client exceeds the configured rate for an endpoint
- **THEN** the system responds with HTTP 429, `error.code` equal to `throttled`, and a `Retry-After` header

#### Scenario: Spoofed forwarded header without a trusted proxy
- **WHEN** no trusted proxies are configured and an anonymous client sends each request with a different `X-Forwarded-For` value
- **THEN** all its requests count against one limit for its connecting address, and requests over the limit get HTTP 429

#### Scenario: Behind a trusted proxy
- **WHEN** one trusted proxy is configured and the proxy appends the real client address to `X-Forwarded-For`
- **THEN** the system throttles by that appended address, and a value the client prepended to the header has no effect

### Requirement: Cross-origin and security headers
The system SHALL only accept credentialed cross-origin requests from configured frontend origins. It SHALL send security headers that prevent MIME sniffing and framing and set a strict referrer policy. In production it SHALL enforce HTTPS with HSTS. The HSTS `includeSubDomains` and `preload` directives SHALL be sent only when the deployment enables them. The system SHALL treat a request as HTTPS based on a forwarded-protocol header only when trusted proxies are configured.

#### Scenario: Unknown origin
- **WHEN** a credentialed cross-origin request comes from an origin not in the allowed list
- **THEN** the response carries no CORS headers that permit it

#### Scenario: Security headers present
- **WHEN** any API response is returned
- **THEN** it includes `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` and `Referrer-Policy: same-origin`

#### Scenario: HSTS defaults in production
- **WHEN** production settings are used and the HSTS subdomain and preload options are not enabled
- **THEN** HTTPS responses carry `Strict-Transport-Security` with the configured `max-age` and without `includeSubDomains` or `preload`

#### Scenario: Forwarded protocol from an untrusted client
- **WHEN** no trusted proxies are configured and a client sends `X-Forwarded-Proto: https` over plain HTTP
- **THEN** the request is not treated as secure

### Requirement: Configuration validated at startup
Every process that serves requests or runs background jobs with production settings SHALL validate the application configuration before it starts work, and SHALL refuse to start when validation reports an error (for example missing token encryption keys or invalid evidence weights). Every serving entry point SHALL default to the same settings module, so the web tier and the workers never run under different settings by accident.

#### Scenario: Invalid configuration blocks the web server
- **WHEN** the production web server starts with an invalid required setting (for example empty token encryption keys)
- **THEN** it exits with an error naming the failed check, before accepting any request

#### Scenario: Invalid configuration blocks the worker
- **WHEN** a background worker or the scheduler starts with production settings and an invalid required setting
- **THEN** it exits with an error naming the failed check, before running any job

#### Scenario: Settings module not set
- **WHEN** the web server, worker or scheduler starts without an explicit settings module
- **THEN** all of them use the production settings
