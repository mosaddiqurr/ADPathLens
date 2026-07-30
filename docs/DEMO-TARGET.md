# Demo target

The demo target is a separate intentionally vulnerable FastAPI process containing fictional users,
documents, identifiers, and static synthetic bearer tokens:

- administrator: `demo-admin-token`
- User A: `demo-user-a-token`
- User B: `demo-user-b-token`
- anonymous: no credential

Secure and vulnerable endpoint pairs cover authentication, vertical administrator access,
horizontal document ownership, sensitive-field exposure, method protection, and existence
leakage. `/ambiguous` deliberately produces weak evidence. `/slow` provides a deterministic
bounded cancellation fixture.

Local runtime binds it to `127.0.0.1:8021`. Compose exposes it only on the internal network and
does not publish a host port. Import fails when `APP_ENV=production`.

`POST /internal/reset` requires both `DEMO_MODE=true` and an exact reset token. The normal UI calls
the authenticated backend `/api/v1/demo/reset`, which verifies project ownership, requires
non-production demo mode, calls the fixed configured demo URL, and records an audit event.

Reset changes only the demo target's in-memory fictional fixtures. It never touches the main
database or real credentials.
