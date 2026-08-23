# AuthZDiff

AuthZDiff is a black-box HTTP authorization differential testing application. It sends the same
bounded request with a higher-privileged and a lower-privileged controlled profile, normalizes the
two responses, and records differences that may indicate an authorization weakness. Results are
review candidates, not proof of exploitability.

AuthZDiff does not import or semantically evaluate IAM/RBAC policies, group graphs, inherited
permissions, or allow/deny rule sets.

> Use AuthZDiff only on systems you own or have explicit written permission to assess. The bundled
> demo target is intentionally vulnerable, contains fictional data, and must never be exposed
> publicly.

## Workflow and capabilities

1. Create a project and an inactive target.
2. Record the authorized origin, methods, path prefixes, request budget, redirects, TLS policy, and
   exact host/IP/CIDR allowlist.
3. Confirm authorization and, for loopback/private targets, the controlled-lab acknowledgement.
4. Store two encrypted request profiles. Credential values are write-only in the UI/API.
5. Create a request manually or from raw HTTP/cURL. HAR is **preview only** and is never executed or
   imported automatically.
6. Save and run a two-profile comparison through the database-backed worker.
7. Review normalized observations, genuine redirect/header/JSON/text differences, candidate
   findings, recurrence history, and sanitized evidence.
8. Export project findings as JSON, CSV, HTML, or PDF.

Configured project redaction keys and built-in sensitive fields are redacted during normalization,
before observations or finding evidence are persisted. Test-case ignored JSON paths, unordered JSON
paths, ignored safe headers, and literal ignored text patterns affect comparison only.

## Components

- FastAPI API with Argon2id passwords, opaque cookie sessions, session-bound CSRF, workspace roles,
  and server-side project isolation.
- Database-backed replay queue with atomic claims, heartbeats, cancellation, concurrency leases,
  and stale-job recovery.
- Pinned-IP HTTP transport with exact origin, DNS, network, canonical path, redirect, size, timeout,
  and request-budget enforcement immediately before transmission.
- AES-256-GCM write-only profiles with contextual associated data and HMAC fingerprints.
- Deterministic `authzdiff-rules/1.1` response comparison and recurring findings.
- React/TypeScript SPA, including mandatory temporary-password replacement.
- Synthetic FastAPI demo target and JSON/CSV/HTML/PDF report generation.

SQLite is the executed local/test database. PostgreSQL and Docker Compose configurations are
included but have not yet been runtime-validated for this release candidate.

## Local installation and startup

Requirements: Python 3.12+, Node.js 22+, and PowerShell on Windows.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements-dev.lock
Set-Location frontend
npm ci
Set-Location ..
$env:AUTHZDIFF_ADMIN_PASSWORD = "choose-a-local-password-with-12+-characters"
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\runtime.ps1 start
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\runtime.ps1 seed
```

Open `http://localhost:4174`. The launcher owns only the processes it starts. Commands are `start`,
`status`, `health`, `stop`, `restart`, `migrate`, `seed`, and `reset`. Local secrets, databases,
logs, reports, and PID data are stored outside tracked source or under ignored runtime paths.

Administrators can provision users through the API. A provisioned user signs in with the temporary
password and is held on the required-password-change screen until the current password is validated
and a policy-compliant replacement succeeds.

## Validation

```powershell
Set-Location backend
..\.venv\Scripts\python -m pip check
..\.venv\Scripts\python -m ruff format --check --no-cache app tests alembic
..\.venv\Scripts\python -m ruff check --no-cache app tests alembic
..\.venv\Scripts\python -m mypy --no-incremental app
..\.venv\Scripts\python -m pytest -p no:cacheprovider
..\.venv\Scripts\python -m pip_audit -r requirements.lock
..\.venv\Scripts\python -m bandit -q -r app

Set-Location ..\frontend
npm ci
npm run lint
npx tsc --noEmit
npm test
npm run build
npm audit --omit=dev
npm audit
npm run e2e
```

Statement and branch coverage thresholds are not currently configured. Playwright runs desktop and
mobile journeys plus axe scans; automated keyboard-only navigation coverage is not currently
provided.

## Data retention and limitations

Project deletion is a soft deletion. Deleted projects disappear from normal workflows, but child
records, observations, evidence, and generated report files are retained until an operator removes
the local database/report storage under an approved retention procedure. AuthZDiff does not claim
cryptographic deletion or automatic purge.

See [docs/SECURITY.md](docs/SECURITY.md), [docs/TARGET-POLICY.md](docs/TARGET-POLICY.md),
[docs/COMPARISON-LOGIC.md](docs/COMPARISON-LOGIC.md),
[docs/KNOWN-LIMITATIONS.md](docs/KNOWN-LIMITATIONS.md), and
[docs/TESTING.md](docs/TESTING.md).
