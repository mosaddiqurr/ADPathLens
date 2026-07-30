#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMMAND="${1:-status}"
RUNTIME_DIR="${AUTHZDIFF_RUNTIME_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/authzdiff}"
PID_FILE="$RUNTIME_DIR/processes"
SECRET_FILE="$RUNTIME_DIR/local-secrets.env"
LOG_DIR="$RUNTIME_DIR/logs"
BACKEND_PORT="${AUTHZDIFF_BACKEND_PORT:-8020}"
FRONTEND_PORT="${AUTHZDIFF_FRONTEND_PORT:-4174}"
DEMO_PORT="${AUTHZDIFF_DEMO_PORT:-8021}"
PYTHON="$ROOT/.venv/bin/python"
VITE="$ROOT/frontend/node_modules/vite/bin/vite.js"

mkdir -p "$LOG_DIR"

start_token() {
  awk '{print $22}' "/proc/$1/stat" 2>/dev/null || true
}

is_owned() {
  local pid="$1" expected="$2"
  [[ -n "$expected" && "$(start_token "$pid")" == "$expected" ]]
}

initialize() {
  [[ -x "$PYTHON" ]] || { echo "Missing .venv Python." >&2; exit 1; }
  if [[ ! -f "$SECRET_FILE" ]]; then
    "$PYTHON" - "$SECRET_FILE" "$RUNTIME_DIR" <<'PY'
import base64
import os
import pathlib
import sys

destination = pathlib.Path(sys.argv[1])
runtime = pathlib.Path(sys.argv[2])
def secret():
    return base64.urlsafe_b64encode(os.urandom(32)).decode()
database = (runtime / "authzdiff.sqlite").resolve().as_posix()
destination.write_text(
    "\n".join(
        [
            f"APP_SECRET_KEY={secret()}",
            f"ENCRYPTION_MASTER_KEY={secret()}",
            f"FIRST_ADMIN_SETUP_TOKEN={secret()}",
            f"DEMO_RESET_TOKEN={secret()}",
            f"DATABASE_URL=sqlite+aiosqlite:///{database}",
        ]
    )
    + "\n",
    encoding="utf-8",
)
PY
    chmod 600 "$SECRET_FILE"
  fi
  # shellcheck disable=SC1090
  source "$SECRET_FILE"
  export APP_SECRET_KEY ENCRYPTION_MASTER_KEY FIRST_ADMIN_SETUP_TOKEN DEMO_RESET_TOKEN DATABASE_URL
  export APP_ENV=development DEMO_MODE=true FIXTURE_MODE=true E2E_MODE=false
  export REPLAY_EXECUTION_MODE=external
  export REPORT_STORAGE_PATH="$RUNTIME_DIR/reports"
  export ALLOWED_FRONTEND_ORIGINS="http://localhost:$FRONTEND_PORT,http://127.0.0.1:$FRONTEND_PORT"
  export ALLOWED_HOSTS="localhost,127.0.0.1"
  export APPLICATION_URL="http://localhost:$BACKEND_PORT"
  export FRONTEND_URL="http://localhost:$FRONTEND_PORT"
  export DEMO_TARGET_URL="http://127.0.0.1:$DEMO_PORT"
  export VITE_API_PROXY_TARGET="http://127.0.0.1:$BACKEND_PORT"
}

port_free() {
  "$PYTHON" - "$1" <<'PY'
import socket
import sys
port = int(sys.argv[1])
with socket.socket() as value:
    value.bind(("127.0.0.1", port))
PY
}

wait_ready() {
  local url="$1" name="$2"
  for _ in $(seq 1 120); do
    if "$PYTHON" - "$url" >/dev/null 2>&1 <<'PY'
import sys
import urllib.request
with urllib.request.urlopen(sys.argv[1], timeout=1) as response:
    if not 200 <= response.status < 300:
        raise SystemExit(1)
PY
    then return
    fi
    sleep 0.25
  done
  echo "$name did not become ready." >&2
  exit 1
}

status() {
  if [[ ! -f "$PID_FILE" ]]; then
    echo "AuthZDiff is stopped."
    return
  fi
  while read -r name pid token; do
    if is_owned "$pid" "$token"; then echo "$name PID $pid running"; else echo "$name PID $pid stale"; fi
  done < "$PID_FILE"
}

stop_all() {
  [[ -f "$PID_FILE" ]] || return
  while read -r name pid token; do
    if is_owned "$pid" "$token"; then
      kill "$pid"
      echo "Stopped owned $name PID $pid."
    fi
  done < "$PID_FILE"
  for _ in $(seq 1 40); do
    local live=0
    while read -r _ pid token; do
      if is_owned "$pid" "$token"; then live=1; fi
    done < "$PID_FILE"
    [[ "$live" -eq 0 ]] && break
    sleep 0.1
  done
  rm -f "$PID_FILE"
}

record_pid() {
  local name="$1" pid="$2"
  echo "$name $pid $(start_token "$pid")" >> "$PID_FILE"
}

migrate() {
  initialize
  (cd "$ROOT/backend" && "$PYTHON" -m alembic upgrade head)
}

start_all() {
  initialize
  if [[ -f "$PID_FILE" ]] && grep -q . "$PID_FILE"; then
    while read -r _ pid token; do
      if is_owned "$pid" "$token"; then
        echo "AuthZDiff already has an owned process. Stop it first." >&2
        exit 1
      fi
    done < "$PID_FILE"
    rm -f "$PID_FILE"
  fi
  for port in "$BACKEND_PORT" "$FRONTEND_PORT" "$DEMO_PORT"; do
    port_free "$port" || { echo "Port $port is occupied; no process was stopped." >&2; exit 1; }
  done
  [[ -f "$VITE" ]] || { echo "Frontend dependencies are not installed." >&2; exit 1; }
  migrate
  : > "$PID_FILE"
  (
    cd "$ROOT/demo-target"
    exec "$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port "$DEMO_PORT" \
      >"$LOG_DIR/demo.stdout.log" 2>"$LOG_DIR/demo.stderr.log"
  ) &
  record_pid demo "$!"
  (
    cd "$ROOT/backend"
    exec "$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" \
      >"$LOG_DIR/backend.stdout.log" 2>"$LOG_DIR/backend.stderr.log"
  ) &
  record_pid backend "$!"
  (
    cd "$ROOT/backend"
    exec "$PYTHON" -m app.worker >"$LOG_DIR/worker.stdout.log" 2>"$LOG_DIR/worker.stderr.log"
  ) &
  record_pid worker "$!"
  (
    cd "$ROOT/frontend"
    exec node "$VITE" --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort \
      >"$LOG_DIR/frontend.stdout.log" 2>"$LOG_DIR/frontend.stderr.log"
  ) &
  record_pid frontend "$!"
  wait_ready "http://127.0.0.1:$DEMO_PORT/ready" "Demo target"
  wait_ready "http://127.0.0.1:$BACKEND_PORT/api/v1/ready" "Backend"
  wait_ready "http://127.0.0.1:$FRONTEND_PORT/" "Frontend"
  echo "AuthZDiff is ready at http://localhost:$FRONTEND_PORT"
}

health() {
  initialize
  wait_ready "http://127.0.0.1:$DEMO_PORT/ready" "Demo target"
  wait_ready "http://127.0.0.1:$BACKEND_PORT/api/v1/ready" "Backend"
  wait_ready "http://127.0.0.1:$FRONTEND_PORT/" "Frontend"
  status
}

seed() {
  initialize
  : "${AUTHZDIFF_ADMIN_PASSWORD:?Set AUTHZDIFF_ADMIN_PASSWORD first.}"
  "$PYTHON" "$ROOT/scripts/seed-demo.py" \
    --base-url "http://127.0.0.1:$BACKEND_PORT" \
    --setup-token "$FIRST_ADMIN_SETUP_TOKEN" \
    --email "${AUTHZDIFF_ADMIN_EMAIL:-admin@authzdiff.local}" \
    --password "$AUTHZDIFF_ADMIN_PASSWORD" "$@"
}

case "$COMMAND" in
  start) start_all ;;
  status) status ;;
  stop) stop_all ;;
  restart) stop_all; start_all ;;
  health) health ;;
  migrate) migrate ;;
  seed) seed ;;
  reset) seed --reset-only ;;
  *) echo "Unknown command: $COMMAND" >&2; exit 2 ;;
esac
