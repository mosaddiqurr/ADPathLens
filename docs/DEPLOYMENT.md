# Deployment

PostgreSQL is required for production. Supply all settings from a protected environment or secret
manager. Production validation rejects placeholder or short secrets, insecure session cookies,
HTTP application/frontend origins, wildcard origins, demo/fixture/E2E modes, and in-process replay.

Compose builds four application roles plus PostgreSQL:

- `backend`: migrates then starts one FastAPI worker;
- `worker`: starts `python -m app.worker`;
- `frontend`: builds the SPA and serves it through Nginx;
- `demo-target`: internal network only, for local demonstration and never production;
- `db`: persistent PostgreSQL volume.

Application images run as non-root. Application services drop Linux capabilities and use
`no-new-privileges`. The demo target has no published port. Nginx publishes
`127.0.0.1:8080` by default and adds CSP, frame, referrer, permissions, and content-type headers.
Report and database volumes are persistent.

```text
docker compose build
docker compose up -d db
docker compose run --rm backend alembic upgrade head
docker compose up -d backend worker frontend
docker compose down
```

Do not include `demo-target` in production deployment automation. This repository's Compose file
is a local controlled-lab topology. Docker runtime status is reported in `RELEASE_STATUS.md` and
must not be inferred from static configuration.
