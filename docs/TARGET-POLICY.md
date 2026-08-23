# Target policy

A target stores one normalized HTTP(S) origin and exact port, allowed methods, canonical allowed path
prefixes, request budget, per-response size limit, redirect/timeout limits, TLS policy, authorization
expiry, private-lab flags, and activation state.

Targets begin inactive. Activation requires an authorization acknowledgement and at least one exact
hostname/IP/CIDR allowlist entry. Private or loopback use additionally requires administrator
confirmation and an address/CIDR rule covering every resolved private address. Wildcard targets are
not supported.

Every run atomically reserves two request slots. Immediately before every transmission—including
retries and redirects—the worker refreshes the target and validates:

- active and unexpired authorization;
- method and state-change approval;
- exact origin, host, port, DNS answers, allowlist, and network class;
- the fully rendered path after variable expansion;
- every percent-decoding layer, up to the bounded decoding limit;
- canonical path-prefix membership.

Paths with dot segments, encoded or multiply encoded traversal, malformed percent escapes,
backslashes, absolute/network paths, fragments, or variable-injected query delimiters are rejected.
Query parameters remain separate structured pairs and are encoded normally. Redirect paths receive
the same canonical validation; redirects cannot escape the configured origin or path scope.

Imported Host, forwarding, proxy, connection, and transfer-control headers are rejected. Environment
proxies and `.netrc` are disabled. `POST /targets/{id}/validate` performs DNS/policy validation only
and never sends an application request.
