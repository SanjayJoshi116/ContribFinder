## ADDED Requirements

### Requirement: Docker development mode stays local and current
`docker compose up` SHALL publish the backend and the frontend only on the host's loopback
interface. The Redis container SHALL NOT be published on the host, so it never takes the port of
the WSL Redis that `npm start` uses, and the Postgres container SHALL stay on host port 5433. The
settings module SHALL come from `.env`, not from the shell that runs compose. Frontend edits on a
Windows host SHALL reach Vite in the container (polling when the compose file asks for it). The
README SHALL say how to rebuild so the frontend container uses newly added dependencies. The
Postgres credentials SHALL be defined once in the compose file.

`.env.example` SHALL list every setting the backend reads from the environment (except settings
read only by the test configuration), each with its default or as required. A setting the
shipped settings modules ignore SHALL NOT be listed. `DJANGO_DEBUG` SHALL apply to the
development settings (default on) and SHALL be ignored by production. The root `package.json`
SHALL offer a formatting command that writes besides the one that checks, and SHALL state the
minimum Node version its runners need.

#### Scenario: Backend not reachable from the network
- **WHEN** `docker compose up` runs on a laptop on a shared network
- **THEN** port 8000 and 5173 answer on `127.0.0.1` only

#### Scenario: Docker and the local stack on one machine
- **WHEN** the WSL Redis from `npm start` is running and the user runs `docker compose up`
- **THEN** compose starts without a port conflict, and `npm start` keeps using the WSL Redis

#### Scenario: Settings module exported in the shell
- **WHEN** the shell has `DJANGO_SETTINGS_MODULE=config.settings.production` exported and the user runs `docker compose up`
- **THEN** the containers use the settings module from `.env`

#### Scenario: Debug off in development
- **WHEN** `.env` sets `DJANGO_DEBUG=false` with the development settings
- **THEN** Django runs without debug pages

#### Scenario: Template covers the settings
- **WHEN** a setting read by `config/settings/base.py` or `production.py` is not in `.env.example`
- **THEN** a test fails naming it
