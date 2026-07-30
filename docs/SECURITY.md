# Security model

AuthZDiff is designed for explicit authorized-use workflows, not discovery, crawling, public
target enumeration, or automatic exploitation.

Authentication uses Argon2id password hashes and 256-bit opaque session tokens. Only a token hash
is stored. Cookies are HTTP-only, `SameSite=Strict`, path `/`, and Secure in production. Mutations
require a session-bound synchronizer token in `X-CSRF-Token`; JSON content type and same-origin
browser behavior provide additional protection. Login failures are generic and rate limited.

Analysts see only projects they created. Every child resource resolves through the project
authorization service and cross-owner access returns a 404-style problem. Administrators have
documented workspace-wide oversight. Frontend guards are convenience only; backend checks are
authoritative.

Target execution requires all of the following:

- active, unexpired authorization;
- allowed method and normalized path prefix;
- enough reserved request budget;
- exact scheme, host, port, and allowlist;
- private-lab acknowledgement for private or loopback addresses;
- validation of every A and AAAA answer immediately before connection;
- connection to a validated IP while preserving approved Host and TLS SNI;
- independent validation of every redirect.

Environment proxies and `.netrc` are disabled. TLS cannot be disabled. HTTP is accepted only for
the explicit local synthetic target in non-production mode.

Profiles are encrypted with AES-256-GCM. Associated data contains project, target, profile, and
field identity. Key identifiers support controlled rotation, and fingerprints use a derived HMAC
key. The UI is write-only, but the backend can decrypt profiles for authorized replay; write-only
does not mean irrecoverable.

Responses, logs, problems, audit summaries, evidence, and reports pass through bounded
normalization/redaction. Raw binary bodies are not stored. HTML is escaped and never executed.
CSV cells beginning with formula markers are neutralized. See `THREAT_MODEL.md` if present and
the focused documents in this directory.
