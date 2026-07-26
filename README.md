# ADPathLens

ADPathLens is a defensive, local-first Active Directory relationship analysis workbench. It
imports authorized JSON/CSV snapshots, preserves their provenance, explores a snapshot-scoped
graph, calculates bounded possible privilege paths, creates human-reviewed findings, simulates
remediation in immutable derived snapshots, compares historical states, and produces sanitized
reports.

ADPathLens does not collect from LDAP, execute changes, prove exploitation, or establish that a
system was compromised. Use only synthetic data or information collected from systems you own or
are explicitly authorized to assess.

## Start locally

Requirements: Python 3.12, Node.js 22, and npm.

```powershell
Copy-Item .env.example .env
python scripts/generate-secret.py
cd backend
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open <http://localhost:5173>. On first launch, create the initial administrator, confirm
authorized use, then use Guided demo or create a workspace and project. SQLite is the lightweight
local default; PostgreSQL 16 is the recommended shared deployment database.

See [RUN_LOCAL.md](RUN_LOCAL.md) for environment settings and
[docs/DEMO_GUIDE.md](docs/DEMO_GUIDE.md) for the fictional NORTHBRIDGE journey.

## What is included

- Argon2id authentication, opaque server sessions, CSRF, role checks, workspace membership, and
  server-side object ownership enforcement.
- Atomic JSON, CSV pair, and constrained ZIP imports with validation digests, warning
  acknowledgement, provenance, archive defenses, and no retained source uploads.
- Snapshot-scoped NetworkX `MultiDiGraph` analysis with bounded deterministic algorithms and
  edge-level evidence.
- Deterministic versioned risk rules whose output begins as Draft and requires analyst review.
- Findings, notes, status history, remediation proposals, previews, derived snapshots, retests,
  persisted comparisons, audit records, and administrative rule/settings controls.
- Escaped HTML, structured PDF, versioned JSON, and formula-safe findings CSV reports.
- Responsive React UI, Cytoscape graph view, accessible list alternatives, and desktop/mobile
  Playwright acceptance coverage.

## Validation snapshot

The 2026-07-26 release validation passed 14 backend tests at 66.93% coverage, 4 frontend unit tests,
strict MyPy, Ruff, formatting, Bandit, ESLint, TypeScript, the production build, and 2 real
Playwright journeys. Automated accessibility scans reported zero serious or critical violations.
The backend restart proof preserved a 35-node/56-relationship snapshot and closed its owned port.

Docker was not installed, so Docker runtime behavior was not executed. The isolated `npm ci`
audited 340 packages and found zero vulnerabilities. A Python advisory refresh was blocked by the
execution policy. See [FINAL_VALIDATION.md](FINAL_VALIDATION.md) for exact evidence and limitations.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Graph model](docs/GRAPH_MODEL.md)
- [Data format](docs/DATA_FORMAT.md)
- [Risk model](docs/RISK_MODEL.md)
- [Security and threat model](docs/SECURITY.md)
- [Testing](docs/TESTING.md)
- [Reporting](docs/REPORTING.md)
- [Known limitations](docs/KNOWN-LIMITATIONS.md)
- [Release status](RELEASE_STATUS.md)

Licensed under the MIT License.
