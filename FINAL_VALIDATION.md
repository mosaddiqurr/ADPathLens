# Final validation evidence

Validation date: 2026-07-30. Commands below were executed against the release candidate; a result is
not inferred from configuration.

| Gate | Result | Executed evidence |
|---|---|---|
| Backend format/lint/type/tests | Pass | Ruff format and lint passed; mypy reported no issues in 53 files; pytest 9.0.3: 41 passed |
| Migration empty/existing/drift | Pass | Blank SQLite upgraded through `0010_expectation_types`; `alembic current` reported head and `alembic check` found no operations. A representative 0008-to-head upgrade also passed during final-phase validation |
| Demo target | Pass | Ruff format/lint passed; pytest: 8 passed |
| Frontend lint/type/tests/build | Pass | ESLint, `tsc --noEmit`, 5 Vitest tests, and Vite 7.3.6 production build passed |
| Live integration | Pass | Real loopback SPA/API/external worker/demo created a target, four profiles, imported requests, replayed high/low sessions, persisted observations, classified a vertical candidate, created stable evidence, and generated reports |
| Playwright desktop/mobile | Pass | Final one-worker matrix: desktop 22.5 s, mobile 4.7 s; 2 passed in 31.6 s |
| Accessibility | Pass | Axe ran without disabled rules on dashboard, comparison, and audit in the desktop journey; keyboard/focus and mobile overflow assertions passed |
| Performance/reliability | Pass | Deterministic local workload completed within bounds; measurements below |
| Python dependency audits | Pass | Backend production, backend development, and demo locks: no known vulnerabilities |
| npm dependency audit | Scoped residual | Two high entries represent one RSC-only React Router advisory; no patched `react-router-dom` release exists. See `docs/KNOWN-LIMITATIONS.md` |
| Runtime restart/teardown | Pass | Owned launcher start, duplicate-start rejection, restart persistence, post-restart replay, health, owned stop, and free-port checks passed |
| Clean install | Pass | Exact final 150-file candidate set copied without generated state; fresh venv and `npm ci`; all language gates, migration, build, four-process cold health, and live `1.0.0-rc1` version check passed |
| Docker runtime/images | Not executed | Docker is unavailable in this Windows validation environment. Compose YAML parsed and Dockerfiles/topology were inspected; no runtime pass is claimed |
| Semgrep/Trivy | Not executed | Executables are unavailable in this environment; no scan pass is claimed |

## Browser acceptance

The desktop journey exercised setup/login, project policy, a loopback lab target, encrypted profile
creation and masking, safe and rejected cURL imports, durable worker replay, cancellation,
classification, finding evidence/lifecycle, JSON/CSV/HTML/PDF generation and authenticated download,
audit, logout, rejected login, and relogin. Report downloads were checked for status, media type,
safe attachment filename, and non-empty bytes. The PDF request used Playwright's shared
browser-context HTTP client because a host-installed download-manager extension intercepts PDF
browser fetches; the same authenticated cookie jar and real API route were used.

The mobile journey used a Pixel 7 viewport and verified authentication, core project navigation, and
the absence of horizontal page overflow.

## Performance evidence

The deterministic `scripts/performance-validation.py` workload used 100 requests, 1,000
observations, 500 comparison pairs, and 100 findings:

| Measurement | Result |
|---|---:|
| Schema creation | 384.07 ms |
| Persist 100 requests | 82.02 ms |
| Normalize 1,000 observations | 738.92 ms |
| Persist 1,000 observations | 867.43 ms |
| Compare 500 pairs | 1,865.77 ms |
| Persist 100 findings | 117.57 ms |
| Search/filter | 26.94 ms |
| Render JSON/CSV/HTML/PDF | 1,709.14 ms |
| SQLite file | 1,503,232 bytes |
| Peak traced memory | 11,466,385 bytes |

Report sizes were JSON 40,033 bytes, CSV 16,774 bytes, HTML 22,582 bytes, and PDF 74,217 bytes.
Read-only transient retry and the no-retry rule for state-changing requests were verified with
deterministic injected transports. Cancellation was also exercised against the live `/slow` demo
endpoint.

## Environment-qualified conclusion

Every mandatory gate available in this environment passed. The candidate is qualified for a local
`v1.0.0-rc1` release, subject to the explicitly unexecuted Docker/Semgrep/Trivy checks and the
documented non-applicable React Router RSC advisory. It is not described as production-ready until
container and PostgreSQL validation are executed in an environment that provides them.
