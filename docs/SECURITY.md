# Security design

- Passwords use Argon2id with bounded input length. Production enforces a strong secret and secure
  environment settings.
- Sessions store only SHA-256 token hashes server-side; cookies are opaque, HttpOnly,
  SameSite=Lax, expiring, revocable, and configurable Secure.
- Cookie-authenticated mutations require CSRF. Login errors are generic and throttled by normalized
  email plus source IP.
- Global role, workspace membership, project scope, and object ownership are enforced by the API.
  Unauthorized object access returns non-disclosing not-found responses.
- Imports enforce body/content/archive limits and are never executed. Source files are not retained.
- Imported text is escaped in HTML, structured directly into PDF, and neutralized in CSV cells.
- CSP, frame denial, MIME sniffing prevention, referrer policy, CORS allow-listing, request IDs,
  structured redacted logs, and safe Problem Details responses are enabled.
- Audit records exclude passwords, cookies, raw uploads, and sensitive metadata.

Security regression coverage includes CSRF, IDOR, cross-workspace isolation, archive traversal,
symlinks, duplicate ZIP entries, nested archives, executable signatures, compression bombs, stored
XSS payloads, report escaping, CSV formulas, cookie attributes, and headers.
