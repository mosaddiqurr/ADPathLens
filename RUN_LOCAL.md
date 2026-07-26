# Run ADPathLens locally

## Prerequisites

- Python 3.12
- Node.js 22 and npm
- PostgreSQL 16 for the recommended shared deployment, or SQLite for local evaluation

Copy `.env.example` to `.env`, replace `APP_SECRET_KEY` with at least 32 random characters, and
keep `.env` out of source control. `python scripts/generate-secret.py` prints a suitable value.

## Backend

```powershell
cd backend
python -m pip install -e ".[dev]"
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Health: <http://127.0.0.1:8000/api/v1/health>

## Frontend

```powershell
cd frontend
npm ci
npm run dev
```

Open <http://localhost:5173>. Vite proxies `/api` to the backend, keeping browser traffic
same-origin.

For release acceptance, Playwright uses backend `8011` and frontend `5174`; it owns and tears down
only those processes. Do not point E2E at a populated database.

## Docker Compose

When Docker is installed:

```powershell
docker compose up --build
```

Open <http://localhost:8080>. PostgreSQL data and generated reports use named volumes. The current
Windows validation host did not have Docker, so this command is documented but not runtime-claimed.
