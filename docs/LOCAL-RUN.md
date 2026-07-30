# Local run

## Windows

Install locked dependencies, then use the owned-process launcher:

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
Defaults are API `8020`, SPA `4174`, and demo `8021`. The launcher checks ports before starting,
records PID plus process start time, rejects duplicate starts, ignores stale records, writes
separate stdout/stderr logs, polls readiness, and stops only matching owned processes.

Local secrets, SQLite data, reports, logs, and PID records live under
`%LOCALAPPDATA%\AuthZDiff` unless `AUTHZDIFF_RUNTIME_DIR` overrides it. They persist through
restart and are not source artifacts.

## Unix

`scripts/runtime.sh` provides the same command names and stores state beneath
`$XDG_STATE_HOME/authzdiff` or `~/.local/state/authzdiff`. Docker Compose is the preferred
production-like Unix workflow.

## Manual services

Set the variables in `.env.example`, migrate from `backend`, then run:

```text
python -m uvicorn app.main:app --host 127.0.0.1 --port 8020
python -m app.worker
python -m uvicorn app.main:app --host 127.0.0.1 --port 8021   # from demo-target
npm run dev -- --host 127.0.0.1 --port 4174 --strictPort
```

Set `VITE_API_PROXY_TARGET=http://127.0.0.1:8020` for the SPA. Never expose the demo target.
