# Security model

AuthZDiff is for explicit authorized testing, not public discovery, crawling, enumeration, or
automatic exploitation.

Authentication uses Argon2id hashes and 256-bit opaque session tokens; only token hashes are stored.
Cookies are HTTP-only, `SameSite=Strict`, path `/`, and Secure in production. Every mutation requires
a session-bound synchronizer token in `X-CSRF-Token`. Login failures are generic and rate limited.
Provisioned users are restricted to logout and password replacement until their temporary password
is validated and a new 12–128 character password succeeds. Password change rotates the session,
invalidates other sessions, and clears `must_change_password` only after commit.

Analysts can access only projects they created. Child resources resolve through project ownership,
and cross-owner identifiers receive the same 404-style response as unknown identifiers.
Administrators have audited workspace-wide oversight but do not bypass target policy.

Outbound execution requires active authorization, method/path policy, reserved budget, an exact
origin and allowlist, private-lab acknowledgement where applicable, validation of every DNS answer,
and connection to a validated IP while preserving Host and TLS SNI. The fully rendered path and
every redirect are canonically normalized and revalidated immediately before transmission.
Environment proxies and `.netrc` are disabled; TLS cannot be disabled.

Profiles use AES-256-GCM with project/target/profile/field associated data. Key identifiers support
rotation and fingerprints use a derived HMAC key. Credentials are write-only to users but decryptable
by the authorized replay worker.

JSON sensitive fields (`password`, `secret`, `token`, `national_id`, `private_key`, and related
built-ins) plus configured project redaction keys are replaced during normalization, before
observations or finding evidence are persisted. Safe headers and bounded text receive token
redaction. Raw binary bodies are hash-only. Reports are generated only from sanitized finding data.
HTML/PDF escape text, and CSV formula prefixes are neutralized.

The local database and report directory still contain security evidence and must be access-controlled.
Soft project deletion does not purge that retained data; see `KNOWN-LIMITATIONS.md`.
