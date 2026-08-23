# Deployment

The executed release workflow is the local Python/Node/SQLite runtime described in `LOCAL-RUN.md`.
PostgreSQL drivers, configuration, migrations, Dockerfiles, and a Compose topology are included, but
Docker and PostgreSQL have not been runtime-validated in the current release environment. Treat the
Compose configuration as a candidate deployment topology until it passes build, migration, runtime,
and acceptance testing on the intended host.

Production configuration rejects placeholder/short secrets, insecure session cookies, HTTP public
origins, wildcard origins, demo/fixture/E2E modes, and in-process replay. Supply settings through a
protected environment or secret manager.

The Compose topology defines PostgreSQL plus backend, external worker, Nginx-served frontend, and an
internal synthetic demo target. Images run as non-root; application services drop Linux capabilities
and enable `no-new-privileges`. Nginx binds loopback by default and adds browser security headers.
The demo target must not be included or exposed in production.

Candidate commands, to be executed only in an equipped validation environment:

```text
docker compose build
docker compose up -d db
docker compose run --rm backend alembic upgrade head
docker compose up -d backend worker frontend
docker compose down
```

Before any production claim, run the full backend/frontend/browser suite against the containerized
PostgreSQL deployment, verify worker concurrency and restart behavior, and confirm clean shutdown,
volume ownership, backup, report retention, TLS termination, and secret injection.

## Publishing branch

The repository currently uses the local `master` branch. During the separately authorized
publishing and history-cleanup phase, rename it to `main` before configuring the GitHub remote. CI
already treats `main` as the publication branch.
