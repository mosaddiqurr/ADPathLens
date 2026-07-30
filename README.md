# AuthZDiff

AuthZDiff is a single-workspace authorization-differential testing platform. It replays one
bounded, explicitly authorized request with two controlled identities, normalizes the responses,
and records an explainable comparison for human review. Similar successful responses are review
signals, not automatic proof of exploitation.

> Use AuthZDiff only on systems you own or have explicit written permission to assess. The
> bundled demo target is intentionally vulnerable, contains fictional data only, and must never
> be exposed publicly.

## Components

- FastAPI API with opaque cookie sessions, synchronizer CSRF, role and object authorization.
- Database-backed replay queue with atomic claims, worker identity, heartbeat, cancellation,
  concurrency leases, and stale-job recovery.
- Pinned-IP outbound HTTP transport with exact target policy, allowlist, DNS and redirect checks.
- AES-256-GCM write-only profiles and HMAC fingerprints.
- Deterministic `authzdiff-rules/1.0` comparisons, stable recurring findings, immutable sanitized
  evidence links, audit events, and JSON/CSV/HTML/PDF reports.
- React SPA using only the authenticated API.
- Isolated fictional FastAPI demo target.

PostgreSQL is the supported production database. SQLite is intended for local development,
tests, and low-concurrency demonstrations.

## Local run

Requirements are Python 3.12+, Node.js 22+, and PowerShell on Windows.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements-dev.lock
Set-Location frontend
npm ci
Set-Location ..
$env:AUTHZDIFF_ADMIN_PASSWORD = "choose-a-local-password"
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\runtime.ps1 start
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\runtime.ps1 seed
```

Open `http://localhost:4174`. The isolated ports are backend `8020`, frontend `4174`, and demo
target `8021`. Use `status`, `health`, `stop`, or `restart` with the same launcher. It records
process identity and stops only processes it started.

Copy `.env.example` to `.env` only for manual or Compose workflows and replace every placeholder.
Never commit `.env`.

## Validation

```powershell
Set-Location backend
..\.venv\Scripts\python -m ruff format --check --no-cache app tests alembic
..\.venv\Scripts\python -m ruff check --no-cache app tests alembic
..\.venv\Scripts\python -m mypy app
..\.venv\Scripts\python -m pytest -p no:cacheprovider

Set-Location ..\frontend
npm run lint
npm test
npm run build
npm run e2e
```

See [docs/LOCAL-RUN.md](docs/LOCAL-RUN.md), [docs/SECURITY.md](docs/SECURITY.md),
[docs/TESTING.md](docs/TESTING.md), and [RELEASE_STATUS.md](RELEASE_STATUS.md). Release status
documents executed evidence and distinguishes unavailable tooling from product limitations.
