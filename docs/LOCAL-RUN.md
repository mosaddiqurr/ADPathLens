# Local run

Python 3.12+ and Node.js 22.13+ (22.x) or 24+ are required.

Windows: create .venv, install backend/requirements-dev.lock, run npm ci inside frontend,
then powershell -NoProfile -ExecutionPolicy Bypass -File scripts/runtime.ps1 start.
Open http://localhost:4174. Commands: start, stop, restart, status, health.
The launcher starts API and Vite only and stops only processes matching its recorded PID/start time.
Operational logs/PID records live in ignored var/runtime. They contain no uploaded datasets.
There is no password, setup token, seeding, encryption key, or database migration.

Linux/macOS can use the two-terminal commands in the README.
The runtime.sh convenience launcher targets Linux and checks /proc ownership; it is not a macOS launcher.

Build frontend with npm run build; npm run preview serves the build on 4174 with the same local API proxy.
Vite development/preview is for local use, not a hardened public web server.

Optional .env settings: ALLOWED_HOSTS, ALLOWED_FRONTEND_ORIGINS, MAX_BODY_BYTES.
Ports are 8020 (API) and 4174 (frontend). Keep explicit origin/host values; wildcards are rejected.
For separate hosting, build with frontend VITE_API_URL set to your backend origin.
See [deployment](DEPLOYMENT.md) for exact CORS, static routing, HTTPS, health, and capacity settings.

docker compose up --build provides a frontend on http://localhost:8080 and an internal-only API.
There is no DB, worker, demo target, report volume, or upload volume.
The supplied container configuration has not been runtime-validated by the Windows release checks.
For any exposed deployment, operators must supply HTTPS/access restrictions and capacity limits.

Generated dependencies, caches, runtime files, and reports are ignored and never needed in a
source publication. Install dependencies using the lock files after a clean checkout.
