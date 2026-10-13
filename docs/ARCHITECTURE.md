# Architecture

AuthZDiff has one current-comparison workflow.

- React/TypeScript owns only the current Before/After inputs, validation summaries, and result.
- FastAPI accepts bounded JSON requests at /api/v1/inspect, /compare, and /reports/{pdf|json|csv}.
- app/parsers/states.py recognizes explicit access snapshots and HAR captures.
- app/comparison/states.py produces the common change/risk model.
- app/comparison/engine.py and normalization.py preserve the established response reasoning and redaction.
- app/reporting/generator.py produces memory-only exports from the same deterministic result.

No DB, ORM, migration, queue, worker, account, organization, project, or history remains in
the active source. Captured requests are never executed. No uploaded data is sent to external services.

Inputs are re-sent to this instance's backend for validation, comparison, and export.
The browser keeps its state in React memory, without localStorage, IndexedDB, cookies, or server identifiers.
Clearing or reloading discards the current UI state. HTTP responses use Cache-Control: no-store.
This is memory-only processing, not a claim of cryptographic erasure from process memory or OS swap.

Bounded request bodies are checked before JSON parsing. Two computations can run per process;
excess computations fail safely with 429. The local launcher starts only API and frontend.
Docker exposes the frontend on loopback and keeps the API on its internal network.
