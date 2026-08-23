# Testing

Automated tests use SQLite, ASGI transports, fake resolvers, controlled loopback services, and
synthetic data. They do not send requests to public targets.

Backend gates:

```powershell
Set-Location backend
..\.venv\Scripts\python -m pip check
..\.venv\Scripts\python -m ruff format --check --no-cache app tests alembic
..\.venv\Scripts\python -m ruff check --no-cache app tests alembic
..\.venv\Scripts\python -m mypy --no-incremental app
..\.venv\Scripts\python -m pytest -p no:cacheprovider
..\.venv\Scripts\python -m alembic upgrade head
..\.venv\Scripts\python -m alembic check
..\.venv\Scripts\python -m pip_audit -r requirements.lock
..\.venv\Scripts\python -m pip_audit -r requirements-dev.lock
..\.venv\Scripts\python -m bandit -q -r app
```

Frontend gates:

```powershell
Set-Location frontend
npm ci
npm run lint
npx tsc --noEmit
npm test
npm run build
npm audit --omit=dev
npm audit
```

Playwright uses one worker and exercises desktop then Pixel 7 layouts against real loopback API,
worker, SPA, and demo processes. The release journey includes setup, target policy, encrypted
profiles, safe/unsafe cURL handling, comparison, cancellation, findings, all report formats, audit,
logout/relogin, administrator provisioning, mandatory password replacement, old-password rejection,
and axe scans. CI uses bundled Chromium; supported local Windows runs use Edge.

Security regression coverage includes rendered/encoded/multiply encoded traversal, malformed path
escapes, redirect scope escape, pre-persistence redaction, all-format report redaction, malformed HAR,
SQLite foreign-key enforcement, CSRF, SSRF, and cross-owner isolation.

Statement and branch coverage tools/thresholds are not configured. Axe results and responsive tests
are useful automated checks, not a claim of accessibility compliance; keyboard-only navigation is
not currently automated.
