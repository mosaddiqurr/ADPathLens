# Replay engine

`POST /test-cases/{id}/run` validates authorization, policy, state-change controls, budget, and
database concurrency leases, then returns a queued job. In external mode an independent worker
atomically changes exactly one `queued` job to `claimed` using a conditional database update.

The job records worker identity, claim time, heartbeat, correlation ID, attempt count, progress,
cancellation request, and safe failure category. Execution becomes `running`, performs the higher
profile request first and the lower profile second, then compares only when both bounded
observations exist. Transport failure on the first request stops the run; an HTTP 4xx/5xx response
is valid evidence.

Immediately before each attempt and redirect, the worker refreshes policy, checks activation,
expiry, budget consistency, method, path, DNS results, allowlist, and destination network. GET,
HEAD, and OPTIONS may receive one retry for a transient network error. State-changing methods
never retry automatically.

Cancellation changes the job to `cancelling`. In-process tasks are interrupted directly. External
workers observe the database flag at deterministic checkpoints; an in-flight socket operation
finishes or times out before final cancellation. No cancelled or partial job is marked completed.

Worker startup marks stale claimed/running/cancelling jobs interrupted after the configured
heartbeat window and releases their leases. It never silently reruns interrupted state-changing
work.
