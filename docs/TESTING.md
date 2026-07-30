# Testing

Ordinary automated tests use SQLite, ASGI transports, fake resolvers, and synthetic network
backends. They do not access public websites.

Backend gates:

```powershell
Set-Location backend
..\.venv\Scripts\python -m ruff format --check --no-cache app tests alembic
..\.venv\Scripts\python -m ruff check --no-cache app tests alembic
..\.venv\Scripts\python -m mypy app
..\.venv\Scripts\python -m pytest -p no:cacheprovider
```

Migration gates use a fresh temporary database and a representative earlier revision:

```powershell
$env:DATABASE_URL = "sqlite+aiosqlite:///C:/path/to/temporary.sqlite"
..\.venv\Scripts\python -m alembic upgrade head
..\.venv\Scripts\python -m alembic check
```

Frontend and browser gates:

```powershell
Set-Location frontend
npm run lint
npm test
npm run build
npm run e2e
```

The Playwright matrix uses one worker, desktop Edge/Chromium first, then a Pixel 7 profile. It uses
real loopback backend, worker, frontend, and demo processes. Axe rules are not disabled. Browser
artifacts are retained only on failure and excluded from release packaging.

Run counts and exact results belong in `FINAL_VALIDATION.md`; this document intentionally does not
claim a command passed merely because it is configured.
