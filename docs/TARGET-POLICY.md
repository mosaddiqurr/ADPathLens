# Target policy

A target stores a normalized origin, exact port, allowed methods, allowed path prefixes, lifetime
request budget, used request count, per-response byte limit, redirect and timeout limits, TLS
policy, authorization expiry, local-fixture flag, and activation state.

Targets begin inactive. Activation requires authorization acknowledgement and at least one exact
allowlist entry. Private/loopback use additionally requires administrator-approved private policy
and the explicit lab acknowledgement. Wildcards are not supported.

Creating a run atomically reserves two request slots. A budget cannot be overcommitted by
concurrent submissions. Lowering a budget below the reserved count causes execution to fail
closed. The UI shows used and total slots. Increasing the configured budget is the explicit
renewal mechanism; history remains visible in the used count and audit events.

Paths are relative request paths. Absolute URLs, fragments, userinfo, malformed percentages,
backslashes, dot traversal, encoded traversal, and policy-prefix escapes are rejected. Imported
Host and forwarding headers are not honored. Redirects never weaken method, host, address, path,
or network checks.

`POST /targets/{id}/validate` resolves and validates policy only. It never issues an application
HTTP request.
