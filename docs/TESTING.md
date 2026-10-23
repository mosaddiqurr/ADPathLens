# Testing

Use Python 3.12+ and Node.js 22+; install `backend[dev]`, run `npm ci` in `frontend`, and install Chromium with `npx playwright install chromium`.

## Backend (from backend/)

```powershell
.venv/Scripts/python.exe -m pytest --cov=app --cov-fail-under=65
.venv/Scripts/python.exe -m ruff check app tests scripts alembic/env.py ../scripts/adpathlens.py
.venv/Scripts/python.exe -m ruff format --check app tests scripts alembic/env.py ../scripts/adpathlens.py
.venv/Scripts/python.exe -m mypy app --no-incremental
.venv/Scripts/python.exe -m bandit -r app -q
.venv/Scripts/python.exe -m pip_audit
```

Use `.venv/bin/python` on macOS/Linux. If the Windows default pytest temp directory is inaccessible, choose a disposable workspace path with `--basetemp=../.runtime/pytest-direct`.

The suite covers parser validation, malformed archives/JSON, duplicate relationships, missing objects, cycles, no paths, confidence/relationship/entity filters, bounded 10,000-node analysis, graph views, authentication/CSRF/ownership, reports, and SQLite migrations. Existing migrations are tested against real persistent files, including percent characters in paths.

## Frontend (from frontend/)

```powershell
npm run test:coverage
npm run lint
npm run format:check
npm run typecheck
npm run build
npm audit --audit-level=low
npm run test:e2e
```

Playwright starts isolated direct services and exercises demo/import, analysis, graph pan/zoom/fit, path selection/evidence, remediation, filters, PDF/JSON downloads, refresh/direct routes, backend-unavailable feedback, and invalid imports. Desktop/mobile tests cover 1440, 1366, 768, and 390px, keyboard interaction, overflow, and serious/critical axe accessibility checks.

For the same local journeys against built assets, set `ADPATHLENS_BUILT_E2E=1` after a build. Add `ADPATHLENS_SHARED_E2E=1` for the shared-account built-assets journey.

## Production HTTPS and backend-only restart (from repository root)

```powershell
backend/.venv/Scripts/python.exe backend/scripts/direct_acceptance.py
```

Requires OpenSSL (including the Git for Windows installation), npm, installed backend/frontend development dependencies, and Chromium. The script uses fresh disposable certificates and SQLite/report storage. It enables production validation, full Argon2 memory cost, secure cookies, explicit origins, and disables local/demo/test modes. It checks exact CORS preflights, invalid credentials/sessions, CSRF, logout/revocation, 12 concurrent writes, uploaded and demo data, analyses, and PDF/JSON exports. It stops only its owned backend, reruns migrations, restarts, verifies the original session and persisted records/files, and runs new analysis. It then builds and serves the frontend over HTTPS on a separate origin and runs shared-account browser acceptance. CI runs this command too.

Automated browser acceptance currently uses Chromium. It does not establish a complete screen-reader audit or certify a provider's public ingress, disk lifecycle, or backup/restore procedure. Review exported PDFs visually when report layout changes; perform a provider-specific smoke check after actual deployment.

## Current verification

The publication pass on 2026-10-23 verified 42 backend tests (67.55% coverage), 21 frontend tests (61.49% statement coverage), and six browser checks against production assets. Lint, formatting, strict typing, the production build, Bandit, dependency consistency, and both dependency audits passed. Report and product-workflow tests also passed after updating Pillow and certifi.

The separate-origin production HTTPS acceptance also passed: secure sign-in and report downloads, exact CORS rules, CSRF and logout checks, 12 concurrent writes, persisted demo/uploads/analyses/exports, session survival after a backend restart, a fresh analysis after restart, SQLite integrity, and WAL mode.

Browser checks cover demo/import and error recovery, analysis, graph evidence, remediation, PDF/JSON exports, refresh persistence, mobile navigation, and dark/light accessibility. Axe found no serious or critical violations on the four main screens in either theme. Saved appearance preferences apply before first paint. Animations start without a header control and suspend during scrolling, on hidden documents, or outside the hero viewport. The optional About preference disables decorative motion. Export controls remain separated at 320, 390, 768, 1242, and 1440px, including keyboard use. The home illustration uses generic identities; imported identities retain their source names.

The local production desktop Lighthouse run on 2026-10-22 reported Performance 93, Accessibility 100, Best Practices 96, SEO 92, FCP 0.5s, LCP 1.7s, total blocking time 0ms, and CLS 0. Native wheel-scroll probes with animations enabled had 95th-percentile frame intervals of 16.8ms on Home and 16.7ms on Results at 1242×668, with no intervals over 50ms. With a four-times CPU slowdown, desktop intervals were 50ms at the 95th percentile; at 390×844 they were 33.3ms on Home and 16.7ms on Results. These are local browser lab measurements, not a guarantee for every device or public hosting configuration.
