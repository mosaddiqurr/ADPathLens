# Deployment

AuthZDiff is stateless: inputs and reports are processed in memory. Deployments need no database,
upload storage, report directory, accounts, worker, or migration. HAR URLs are never contacted.

## Same-origin containers

Run `docker compose up --build` locally and open http://localhost:8080. The frontend proxies
`/api/` to the internal backend; only the frontend port is exposed. For a public deployment,
place it behind HTTPS, configure the exact public host in `ALLOWED_HOSTS` and the exact frontend
origin in `ALLOWED_FRONTEND_ORIGINS`, and supply access controls and request/rate limits upstream.
The Compose defaults bind to loopback. Container startup must be validated on a running Docker
engine before choosing this route; configuration validation alone does not verify image startup.

## Separate frontend and backend

1. Install `backend/requirements.lock` with Python 3.12 or later. In `backend`, run
   `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log --limit-concurrency 16`.
2. Set backend `ALLOWED_HOSTS=api.example.com` and
   `ALLOWED_FRONTEND_ORIGINS=https://authzdiff.example.com` using your actual domains.
   Hosts contain no scheme or port; origins contain the scheme and optional port, with no path
   or trailing slash. Wildcards are rejected. TLS belongs at the hosting ingress.
3. Before `npm run build` in `frontend`, set `VITE_API_URL=https://api.example.com`.
   This public build-time value is the backend origin, without `/api/v1`. Rebuild when it changes.
   Leave it empty for same-origin API routing. Never put credentials in frontend environment values.
4. Serve `frontend/dist` with a production static host and rewrite non-asset routes to `index.html`
   so `/compare` and `/about` work on direct visits. Serve the favicon and assets from the root.
5. If adding CSP, allow the exact backend origin in `connect-src`. The supplied nginx CSP targets
   same-origin proxy hosting; a separate static host needs its own equivalent security headers.
6. Check `/api/v1/health` and `/api/v1/ready`, then upload Before/After, compare, inspect evidence,
   and download PDF, JSON, and CSV from the deployed frontend.

## Request bounds and privacy

The default API request limit is 12 MiB (`MAX_BODY_BYTES=12582912`), with a 24 MiB configuration
ceiling. Each input is limited to 5 MiB, 2,000 snapshot records or 500 HAR entries.
JSON escaping can enlarge the envelope; the total request limit still applies. Set ingress body
limits consistently. Each process allows two simultaneous computations; add upstream connection,
rate, and memory limits for public hosting. The provided command uses one worker.

Disable request/response body logging and proxy buffering to disk. Do not attach upload/report
volumes. Use no-store responses and avoid shared caching of `/api/`. No authentication is built in;
the operator supplies access controls where required. Uploaded business data may remain after
best-effort credential redaction, so users must review exports before sharing.

For reproducible checks, see [testing](TESTING.md). No deployment or publication is performed by
the local validation commands.
