# Replay engine

`POST /test-cases/{id}/run` validates authorization, target state, method/state-change controls,
budget, and database concurrency leases, then returns a queued job. In external mode an independent
worker conditionally claims exactly one queued job.

The worker records identity, claim time, heartbeat, correlation ID, attempt count, progress,
cancellation request, and safe failure category. It executes the higher-profile request first and
the lower-profile request second. An HTTP 4xx/5xx is valid response evidence; transport failure stops
the run.

Immediately before each attempt, including a retry, the worker refreshes target state and validates
the exact destination and the fully rendered path. Path validation repeatedly decodes bounded
percent encoding, rejects malformed/ambiguous encoding and traversal, and applies canonical allowed
prefixes. Every redirect receives the same origin, network, method, path, and DNS checks before the
next transmission. Structured query parameters are encoded separately.

Response normalization performs size/binary handling, safe-header selection, token scrubbing, JSON
field redaction, configured project-key redaction, shape extraction, and bounded excerpt generation.
Only that normalized result is persisted. Comparison then applies configured ignored/unordered
fields and stores genuine redirect, header, structure, JSON-value, and text differences.

GET, HEAD, and OPTIONS may receive one transient network retry. State-changing methods never retry.
External cancellation is observed at database checkpoints; an in-flight socket operation finishes or
times out. Worker recovery marks stale jobs interrupted and releases leases without silently
replaying state-changing work.
