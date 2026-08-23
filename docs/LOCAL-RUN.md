# Local run

## Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements-dev.lock
Set-Location frontend
npm ci
Set-Location ..
$env:AUTHZDIFF_ADMIN_PASSWORD = "a local password with 12+ characters"
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\runtime.ps1 start
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\runtime.ps1 seed
```

Commands are `start`, `status`, `health`, `stop`, `restart`, `migrate`, `seed`, and `reset`.
Defaults are API `8020`, SPA `4174`, and demo `8021`. The launcher verifies ports, records PID plus
process start time, rejects duplicate starts, ignores stale records, separates logs, polls readiness,
and stops only matching owned processes.

Local secrets, SQLite data, reports, logs, and PID records live beneath `%LOCALAPPDATA%\AuthZDiff`
unless `AUTHZDIFF_RUNTIME_DIR` overrides it. They persist through restart and must never be committed.

## Unix

`scripts/runtime.sh` provides the same commands and stores state beneath
`$XDG_STATE_HOME/authzdiff` or `~/.local/state/authzdiff`. The Python/Node/SQLite runtime is the
validated Unix-compatible path used by CI browser acceptance. Docker Compose remains an unverified
candidate topology; see `DEPLOYMENT.md`.

## Manual services

Set protected values based on `.env.example`, migrate from `backend`, and run:

```text
python -m uvicorn app.main:app --host 127.0.0.1 --port 8020
python -m app.worker
python -m uvicorn app.main:app --host 127.0.0.1 --port 8021   # from demo-target
npm run dev -- --host 127.0.0.1 --port 4174 --strictPort
```

Set `VITE_API_PROXY_TARGET=http://127.0.0.1:8020` for the SPA. Never expose the demo target.
