# Testing

Run the commands in README.md.

Backend tests cover explicit grants/losses, recognized escalation, public/sensitive/wildcard risk,
removed-deny uncertainty, custom-role review, no-change and JSON/CSV interoperability, safe parsing,
bounds, offline path validation, malformed HAR, corroborated HAR transitions, missing evidence,
request-origin restrictions, report-evidence equality, injection safety, and streamed body limits.
Property tests exercise arbitrary JSON without parser exceptions.
The established response rules retain tests for denial, anonymous/tenant/object-scope candidates,
truncation, genuine header/redirect/JSON differences, ignores, and unordered arrays.

Frontend tests check account-free entry, progressive evidence, risk filters, safe API errors,
response validation, and omission of cookies/cache.
Playwright runs the upload -> compare -> evidence -> export journey on desktop and mobile.
It also tests no-change, example loading, state reset/reload, malformed/unsupported/incompatible inputs,
safe server errors, HAR transitions, keyboard entry, no horizontal overflow, and axe WCAG scans.

npm run build produces the production frontend. Browser tests auto-start the built preview when
no local frontend is running; build first. CI uses Chromium, Windows defaults to installed Edge.
Desktop runs without CI regenerate docs/screenshots/{home,compare,results,evidence}.png using fictional inputs.
Publication regressions cover encoded-path, form, content-type, and tenant-header changes without
inventing access transitions, credential rotation, short secrets and key variants, redacted
filenames, 2,000-record exports, exact CORS preflights, and invalid deployment origin rejection.
Browser checks include CSV pairs/exports, credential evidence redaction, centering at six widths,
and accessible results at 320 pixels.

Separate-host production verification (PowerShell, after the ordinary checks):

```powershell
Push-Location frontend
$env:VITE_API_URL = "http://127.0.0.1:8021"
npm run build -- --outDir ../var/verification/split-dist
$env:E2E_BACKEND_PORT = "8021"
$env:E2E_FRONTEND_PORT = "4175"
$env:E2E_PREVIEW_DIR = "../var/verification/split-dist"
npx playwright test --project desktop --grep "home opens directly|CSV pair"
Remove-Item Env:VITE_API_URL, Env:E2E_BACKEND_PORT, Env:E2E_FRONTEND_PORT, Env:E2E_PREVIEW_DIR
Pop-Location
```

This checks real cross-origin browser requests, exact CORS, validation, comparison, evidence,
and PDF/JSON/CSV downloads using a separate production bundle. It also runs in CI.
Both backend lock files include resolved transitive dependencies; a clean environment can run
the full suite without any legacy packages.

Static checks: Ruff format/lint, mypy, ESLint, TypeScript, Bandit, pip-audit, npm audit.
Publication checks: scripts/verify-publication.py reviews current publishable files and reachable
historical paths/blobs for private artifacts and recognizable credentials; detection is best effort.
Docker and other operating systems are configuration targets, not claimed executed runtime validations.
