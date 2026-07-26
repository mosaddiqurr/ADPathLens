# Architecture

ADPathLens is a local-first monorepo. A React/TypeScript Vite client calls a FastAPI REST API under
`/api/v1`. Same-origin development and Nginx proxies carry an HTTP-only opaque session cookie and
an `X-CSRF-Token` header for state changes.

FastAPI routers validate Pydantic schemas and call role- and ownership-aware services backed by
async SQLAlchemy 2. Alembic owns the portable SQLite/PostgreSQL schema. Imported files are
normalized in one transaction; only normalized nodes, relationships, provenance, and validation
messages are retained.

Every graph is rebuilt from one persisted snapshot into an isolated NetworkX `MultiDiGraph`.
Cache keys include snapshot identity and revision, with TTL/LRU eviction. Bounded path work runs
with depth, path-count, expansion, deadline, and graph-size budgets.

Findings, notes, history, remediation plans/actions, derived snapshots, comparisons, reports, and
audit events remain relational records. Generated reports use UUID storage names and are downloaded
only after project authorization is resolved.
