# API

The REST API is mounted at `/api/v1`; interactive OpenAPI documentation is available at `/docs`
when enabled by FastAPI. UUIDs identify resources. Errors use RFC Problem Details with stable
application codes and request IDs.

Route groups cover auth, users, workspaces, projects/datasets/snapshots, graph, analyses/paths,
findings/notes, remediation, comparisons, reports/downloads, audit, settings, capabilities, and
risk-rule configuration. State changes require `X-CSRF-Token` for cookie sessions.

Pagination uses `page` and `page_size` where collections may grow. Resource handlers resolve the
owning project before returning data.
