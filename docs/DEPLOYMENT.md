# Direct deployment

Deploy the React/Vite build to a static host and FastAPI to one Python service with a persistent local disk. SQLite stores sessions, projects, snapshots, analyses, and report metadata. Generated reports also need persistent storage. No separate database service is required.

## Frontend

For Netlify: base directory `frontend`, build `npm run build`, publish `dist`. The packaged `public/_redirects` supplies the SPA fallback. For another static host, configure application routes to serve `index.html` while preserving static files.

Set `VITE_API_URL=https://api.your-domain.example` in the build environment. This is the backend origin without `/api/v1`. Rebuild when it changes. All fetch requests and protected report/audit/comparison downloads use this origin. Vite variables are public; never include secrets. Local development leaves it empty and uses Vite's API proxy. See [Vite environment configuration](https://vite.dev/guide/env-and-mode) and [Netlify SPA redirects](https://docs.netlify.com/routing/redirects/rewrites-proxies/).

## Backend

For a Python host such as Render:

- Root directory: `backend`; Python 3.12 or newer.
- Build: `pip install .`.
- Start: `python scripts/start.py`.
- Attach persistent storage at `/data`; use one instance, one Uvicorn worker.
- Configure the environment below. HTTPS terminates at the trusted host ingress, which forwards to the process's `PORT` (default 8000).

| Variable | Production value |
| --- | --- |
| `APP_ENV` | `production` |
| `APP_SECRET_KEY` | Random value of at least 32 characters; use `python ../scripts/generate-secret.py` |
| `DATABASE_URL` | `sqlite+aiosqlite:////data/adpathlens.db` |
| `REPORT_STORAGE_PATH` | `/data/reports` |
| `LOCAL_MODE`, `DEMO_MODE`, `E2E_MODE` | `false` |
| `SESSION_COOKIE_SECURE` | `true` |
| `SESSION_COOKIE_SAMESITE` | `lax` for same-site HTTPS frontend/API |
| `ALLOWED_FRONTEND_ORIGINS` | `https://app.your-domain.example` (exact origins separated by commas) |
| `FRONTEND_PUBLIC_URL` | `https://app.your-domain.example` |
| `BACKEND_PUBLIC_URL` | `https://api.your-domain.example` |

[backend/.env.production.example](../backend/.env.production.example) is a configuration template; replace its secret and domains. Production rejects relative/in-memory database paths and insecure settings. On Windows use an absolute URL such as `sqlite+aiosqlite:///E:/adpathlens-data/adpathlens.db`, plus an absolute report path. The startup script creates parent/report directories, runs Alembic to head, and starts Uvicorn. Existing SQLite migrations and data remain compatible. Provision first-administrator setup on a private service before exposing access.

The authenticated synthetic demo works with all convenience modes disabled. `/api/v1/health` checks liveness and `/api/v1/ready` checks database/schema/report-storage readiness. Persistent storage must be writable by the service account. Ordinary service filesystems may be ephemeral; explicitly attach a persistent disk. See [Render persistent disks](https://render.com/docs/disks).

## Authentication across origins

Use app/API custom subdomains under the same registrable domain, both HTTPS. Separate origins require exact credentialed CORS, but same-site cookies work with `SameSite=Lax`. The browser client includes credentials and sends CSRF tokens on mutations; cookies are host-only, HttpOnly, and Secure. Logout revokes the stored session and deletes the cookie.

Unrelated provider domains are cross-site: `SESSION_COOKIE_SAMESITE=none` with Secure allows cross-site cookies, but browser third-party-cookie restrictions can still prevent login. Prefer same-site custom domains for reliable shared authentication. Wildcard origins cannot be used with credentialed requests. Refer to [MDN cookie attributes](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie) and [credentialed CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS).

## Persistence and acceptance

SQLite uses WAL and a 30-second busy timeout. Keep the database, its WAL/SHM files, and reports on the persistent local disk. Do not use network-mounted SQLite or horizontal replicas. Use SQLite's backup API for a consistent database backup, and preserve reports with it; test restore and choose retention before accepting valuable data. No application DB/report files are tracked.

Run `python backend/scripts/direct_acceptance.py` from the repository root using the backend virtual environment. It provisions disposable production-mode HTTPS services, builds the actual frontend with a separate API origin, performs shared browser authentication/export/reload, checks concurrent writes and integrity, and restarts only the backend. It verifies retained sessions, uploaded/demo snapshots, analyses, and PDF/JSON files, then performs new analysis. OpenSSL and installed Chromium/frontend development dependencies are required. This verifies application behavior using a disposable certificate; the chosen host's public TLS, domain routing, persistent disk, and restore process still need a post-deployment smoke check. See [TESTING.md](TESTING.md).
