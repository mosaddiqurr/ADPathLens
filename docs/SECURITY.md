# Security design

Local mode is a convenience for the portfolio demo, enabled only in development. Both the actual client peer and requested host must be loopback. Supplied origins must be loopback and allowlisted; cross-site requests are rejected. Session creation requires the custom `X-ADPathLens-Local` header. Uvicorn local startup disables forwarded-header trust so a remote peer cannot become loopback through a forged header.

The dedicated local account is an analyst. Bootstrap creates a workspace only in an empty account database; it refuses to adopt an existing shared account database. The local database default is `adpathlens-local.db`. Setting `LOCAL_MODE=false` restores the password-based shared workflow. Production settings reject local mode.

Existing controls remain in the API:

- Argon2id password hashing with bounded input, opaque expiring/revocable HttpOnly SameSite cookies, and server-side token hashes.
- CSRF tokens for authenticated mutations, generic login errors, and per-email/source throttling.
- Role, membership, project, snapshot, finding, report, and other object ownership enforcement with non-disclosing not-found responses.
- Import size/content/archive limits, schema validation, digest binding, explicit authorization, and warning acknowledgement. Uploads are parsed, never executed, and source files are not retained.
- HTML escaping, structured PDF text, CSV formula neutralization, UUID report names, and authorized download paths.
- CSP, frame denial, MIME sniffing prevention, referrer policy, allowlisted CORS, request IDs, safe Problem Details responses, and redacted logging/audit records.
- Production checks for secrets, secure cookies, HTTPS origins/public URLs, absolute persistent SQLite and report storage, and disabled demo/E2E/local modes.
- Ownership-aware local process control.

Tests cover CSRF, IDOR, cross-workspace isolation, local-mode boundaries, archive traversal/symlinks/duplicate entries/nested archives/compression bombs, stored XSS, report escaping, CSV formulas, cookies, and security headers. Bandit and online dependency audits supplement those tests; they do not replace a deployment review.

The tool interprets supplied relationship evidence. It does not collect directory credentials, contact an AD domain, execute attack steps, or change directory permissions. Use only synthetic data or environments you are authorized to assess. Production hosting requires persistent storage, trusted HTTPS ingress, and private first-administrator provisioning. Same-site HTTPS custom domains support secure SameSite=Lax cookies; cross-site SameSite=None is subject to browser third-party-cookie restrictions. See [DEPLOYMENT.md](DEPLOYMENT.md).
