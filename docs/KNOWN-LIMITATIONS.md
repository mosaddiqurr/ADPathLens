# Known limitations

- AuthZDiff is single-workspace and single-node. It has no multi-tenant organization model.
- The database queue survives API restarts, but it is not a distributed task platform. PostgreSQL
  plus controlled worker count is required for meaningful concurrency.
- External cancellation is cooperative at database checkpoints. An in-flight request completes or
  reaches its configured timeout before cancellation finalizes.
- State-changing target requests cannot be rolled back by AuthZDiff. They require multiple
  confirmations and never retry automatically.
- Authentication automation, browser login scripting, discovery, crawling, enumeration, and
  wildcard targets are out of scope.
- The deterministic engine identifies differences and candidates; it does not prove business
  impact, exploitability, or affected population.
- Response evidence is intentionally bounded and sanitized. Truncation can make a comparison
  inconclusive.
- HTML response comparison extracts safe structure/text; it does not execute client-side scripts.
- Local report storage is node-local. External object storage and retention automation are not in
  v1.
- SQLite is for local development and tests; production uses PostgreSQL.
- `npm audit --omit=dev` reports
  [GHSA-qwww-vcr4-c8h2](https://github.com/advisories/GHSA-qwww-vcr4-c8h2) against
  React Router 7.18.2. The advisory affects React Server Components action handling. AuthZDiff is
  a client-only SPA: it has no RSC runtime or server actions, and all FastAPI mutations require the
  session-bound synchronizer CSRF token. As of 2026-07-30 the latest published
  `react-router-dom` is 7.18.2, so no patched DOM package can be installed. This scoped upstream
  residual must be rechecked on every dependency update.

Unavailable external tools or sandbox restrictions are release-environment constraints and are
listed separately in `RELEASE_STATUS.md`.
