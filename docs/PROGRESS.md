# ADPathLens implementation progress

Updated: 2026-07-26

## Release-candidate implementation

The FastAPI/React monorepo now includes authentication, opaque sessions, CSRF, roles, workspace
membership, project isolation, atomic imports and provenance, persisted snapshot graphs, bounded
paths, deterministic Draft findings, notes/history, remediation simulation and outcomes, immutable
derived snapshots, persisted comparisons, four sanitized report formats, ownership-safe downloads,
audit/administration, and a resettable fictional NORTHBRIDGE demo.

The responsive frontend uses real APIs for dashboard, workspaces/projects, import validation,
Cytoscape and list exploration, paths, findings, remediation, comparisons, reports, demo, audit,
users, settings, and risk rules.

## Final validation evidence

| Gate | Result |
|---|---|
| Ruff / formatting | Passed; 66 files formatted |
| Strict MyPy | Passed; 54 source files |
| Backend tests | Passed; 14 tests, 66.93% coverage |
| Bandit | Passed; no findings reported |
| SQLite Alembic cycle/check | Passed from an empty database |
| Frontend tests | Passed; 3 files, 4 tests |
| Frontend coverage | 46.13% statements, 50.47% lines |
| ESLint / TypeScript / Vite | Passed; 1,678 modules built |
| Playwright | Passed; desktop and Chromium mobile, 2/2 in 30.4 seconds |
| Accessibility | Zero serious/critical axe violations in tested workflows |
| Restart persistence | Passed; 35 nodes, 56 relationships persisted |
| Process cleanup | Passed; no listeners on 8011 or 5174 |
| Performance | Passed deterministic budgets through 10,000 nodes |
| Clean staged-source install | Passed backend/frontend install, migration, tests, build, restart |
| npm dependency audit | 340 packages, zero vulnerabilities during clean `npm ci` |
| Python dependency audit | Not run; external inventory disclosure was policy-blocked |
| Docker/PostgreSQL runtime | Not run; Docker and `psql` unavailable |

Release commit, annotated tag, source archive, and checksum are the only remaining local packaging
operations. No remote push will be performed.
