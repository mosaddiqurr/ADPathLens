# Testing

Backend:

```powershell
cd backend
python -m ruff format --check app tests scripts --no-cache
python -m ruff check app tests scripts --no-cache
python -m mypy app --no-incremental
python -m pytest -q --cov=app --cov-fail-under=65
python -m bandit -r app -q
```

Frontend:

```powershell
cd frontend
npm run lint
npm run test:coverage
npm run build
npm run test:e2e
```

Playwright starts one loopback backend on 8011 and one Vite server on 5174 with a fresh SQLite
database and one worker. Desktop covers the complete Mina Rahman workflow and cross-user IDOR;
mobile covers authentication, responsive navigation, keyboard access, and axe. Both use Chromium.

Performance tests generate 1k/5k/10k graphs at runtime and import the 500-node/1,501-edge medium
fixture. Results in `FINAL_VALIDATION.md` are measurements, not scale guarantees.
