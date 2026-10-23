# Architecture

ADPathLens remains a React/TypeScript + FastAPI monorepo. The primary UI has four routes: Home, Analyze, Results, and About. One product context owns the selected dataset and restores its most recent completed analysis. Results combines prioritization, a selected-path graph, evidence, remediation, and export.

The client sends API requests and authenticated export downloads to the public origin configured by `VITE_API_URL` at build time. Local Vite development uses a proxy at `/api/v1`. FastAPI validates requests and enforces roles, workspace membership, project scope, CSRF, and object ownership. Async SQLAlchemy persists imported snapshots, analyses, findings, sessions, and reports in SQLite; Alembic maintains the existing schema. WAL and a busy timeout support ordinary concurrent requests. Production uses one backend process and a persistent local disk; report files are stored separately on the same disk.

An explicit development-only local mode establishes a normal opaque session for a dedicated analyst on loopback. It uses a separate SQLite database by default and refuses to bootstrap into a database with existing accounts. Shared deployments retain password authentication. See [SECURITY.md](SECURITY.md).

Each persisted snapshot becomes an isolated NetworkX MultiDiGraph, cached by snapshot identity/revision with TTL/LRU limits. Traversal respects relationship filters, confidence, enabled objects, depth, path count, expansion, and time budgets. Reverse searches share one expansion/time budget across all starting objects. Responses retain ordered steps, object types, explanations, source evidence, confidence, and score components. Reached limits produce an explicit partial-results flag.

The selected path is rendered in Cytoscape with a structured layout. Optional nearby relationships have a separate bounded view. Cytoscape loads on demand, keeping the landing page independent of the graph bundle. Text step cards provide the same path relationships and evidence for keyboard and mobile use.

PDF and JSON exports reference the analysis being viewed. PDF presents a bounded narrative; JSON preserves the complete returned records. Report files use UUID storage names, and downloads resolve ownership before accessing storage. Existing findings, simulations, comparisons, audit, and administration APIs remain available for compatibility and security regression coverage, while the primary UI omits their enterprise workflows.

The local controller starts migration-first, verifies readiness, records owned processes, and checks command lines before stopping them. Direct hosting runs `backend/scripts/start.py`, which creates configured storage directories, migrates, and starts one Uvicorn service.
