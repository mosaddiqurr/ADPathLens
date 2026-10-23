# Running ADPathLens locally

Install and start using the commands in [README.md](README.md#run-locally). Use the project's Python virtual environment for the launcher and all backend commands.

The launcher prefers backend `http://127.0.0.1:8011` and frontend `http://127.0.0.1:4173`. If either port is occupied, it selects a nearby free loopback port, updates the proxy/origin configuration, and prints the actual URLs. It validates readiness and records actual ports and process ownership under `.runtime/`. Duplicate starts are rejected until the existing owned instance is stopped. Use `scripts/adpathlens.py status`, `health`, `stop`, or `restart` with the same Python executable; these commands read the recorded ports.

## Portfolio mode

`LOCAL_MODE=true` enables automatic loopback analyst sessions. The launcher uses this default when `.env` and the process environment do not specify it. A process environment variable takes precedence over `.env`. The new `.env.example` points to `sqlite+aiosqlite:///./adpathlens-local.db`, separate from older account databases.

Open Home → Load demo → Run analysis → Results. No seed password is needed. An optional `scripts/adpathlens.py seed` command loads the same fictional demo. `demo-reset` intentionally deletes the datasets in that demo collection and reloads it; avoid using it when you want to retain prior demo results.

If local mode finds an existing account database, it refuses automatic setup. Select a new local database or set `LOCAL_MODE=false` and sign in. Existing databases are never silently reset or migrated into anonymous access.

## Manual services

From `backend/`, with the virtual environment activated:

```powershell
$env:LOCAL_MODE = 'true'
$env:DATABASE_URL = 'sqlite+aiosqlite:///./adpathlens-local.db'
$env:ALLOWED_FRONTEND_ORIGINS = 'http://127.0.0.1:4173'
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8011 --no-proxy-headers
```

From `frontend/` in a second terminal:

```powershell
$env:VITE_API_PROXY_TARGET = 'http://127.0.0.1:8011'
npm run dev -- --host 127.0.0.1 --port 4173 --strictPort
```

Keep both services bound to loopback. The backend stores imported snapshots in the configured database and generated report files under `REPORT_STORAGE_PATH` (default `backend/reports`). Source uploads are parsed and discarded.

Manual commands use explicit ports. If you choose alternatives, keep the Uvicorn port, frontend proxy target, Vite port, and backend allowed frontend origin in agreement. The launcher handles these choices automatically.

## Shared deployments

Set `LOCAL_MODE=false`. Account setup, login, sessions, CSRF, roles, and data ownership remain available. Use persistent SQLite and report storage for a single Python backend instance. Production checks and deployment requirements are described in [docs/SECURITY.md](docs/SECURITY.md) and [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Troubleshooting

Logs are under `.runtime/`. If startup fails, inspect backend/frontend logs and run `health`. Use the URL from `start` or `status` rather than assuming a preferred port. The launcher searches up to 100 ports near each preferred port and does not kill unrelated processes. A frontend API failure usually means the backend is unavailable or the proxy target is wrong. Browser tests use ports 8011 and 5174; stop an owned instance using those ports before starting them. Do not terminate an unrelated service to free a test port.
