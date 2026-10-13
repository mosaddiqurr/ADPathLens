#!/usr/bin/env bash
# Linux convenience launcher. For macOS use the README's two-terminal commands.
set -euo pipefail
TASK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TASK_COMMAND="${1:-status}"
TASK_RUNTIME="$TASK_ROOT/var/runtime"
TASK_RECORDS="$TASK_RUNTIME/linux-processes"
TASK_PYTHON="$TASK_ROOT/.venv/bin/python"
TASK_BACKEND_PORT="${AUTHZDIFF_BACKEND_PORT:-8020}"
TASK_FRONTEND_PORT="${AUTHZDIFF_FRONTEND_PORT:-4174}"
mkdir -p "$TASK_RUNTIME"
task_start_token() { awk '{print $22}' "/proc/$1/stat" 2>/dev/null || true; }
task_owned() { [[ -n "$2" && "$(task_start_token "$1")" == "$2" ]]; }
task_stop() {
  if [[ -f "$TASK_RECORDS" ]]; then
    while read -r task_name task_pid task_token; do
      if task_owned "$task_pid" "$task_token"; then kill "$task_pid"; fi
    done < "$TASK_RECORDS"
    rm -f -- "$TASK_RECORDS"
  fi
}
task_ready() {
  "$TASK_PYTHON" - "$1" <<'PY'
import sys
import time
import urllib.error
import urllib.request
for attempt in range(60):
    try:
        with urllib.request.urlopen(sys.argv[1], timeout=1) as response:
            if response.status == 200:
                raise SystemExit(0)
    except (OSError, urllib.error.URLError):
        time.sleep(0.25)
raise SystemExit("Service failed to start")
PY
}
task_start() {
  [[ -x "$TASK_PYTHON" && -f "$TASK_ROOT/frontend/node_modules/vite/bin/vite.js" ]] || { echo "Install backend/frontend dependencies first." >&2; exit 1; }
  if [[ -f "$TASK_RECORDS" ]]; then
    while read -r task_name task_pid task_token; do
      if task_owned "$task_pid" "$task_token"; then echo "AuthZDiff is already running." >&2; exit 1; fi
    done < "$TASK_RECORDS"
  fi
  "$TASK_PYTHON" - "$TASK_BACKEND_PORT" "$TASK_FRONTEND_PORT" <<'PY'
import socket
import sys
for value in sys.argv[1:]:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", int(value)))
PY
  : > "$TASK_RECORDS"
  export ALLOWED_HOSTS=localhost,127.0.0.1
  export ALLOWED_FRONTEND_ORIGINS="http://localhost:$TASK_FRONTEND_PORT,http://127.0.0.1:$TASK_FRONTEND_PORT"
  export VITE_API_PROXY_TARGET="http://127.0.0.1:$TASK_BACKEND_PORT"
  (cd "$TASK_ROOT/backend"; exec "$TASK_PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port "$TASK_BACKEND_PORT" --no-access-log) > "$TASK_RUNTIME/backend.stdout.log" 2>&1 &
  task_pid=$!
  echo "backend $task_pid $(task_start_token "$task_pid")" >> "$TASK_RECORDS"
  (cd "$TASK_ROOT/frontend"; exec node node_modules/vite/bin/vite.js --host 127.0.0.1 --port "$TASK_FRONTEND_PORT" --strictPort) > "$TASK_RUNTIME/frontend.stdout.log" 2>&1 &
  task_pid=$!
  echo "frontend $task_pid $(task_start_token "$task_pid")" >> "$TASK_RECORDS"
  if ! task_ready "http://127.0.0.1:$TASK_BACKEND_PORT/api/v1/ready" || ! task_ready "http://127.0.0.1:$TASK_FRONTEND_PORT/"; then task_stop; exit 1; fi
  echo "AuthZDiff is ready: http://localhost:$TASK_FRONTEND_PORT"
}
case "$TASK_COMMAND" in
  start) task_start ;;
  stop) task_stop ;;
  restart) task_stop; task_start ;;
  health) task_ready "http://127.0.0.1:$TASK_BACKEND_PORT/api/v1/ready"; task_ready "http://127.0.0.1:$TASK_FRONTEND_PORT/"; echo "Healthy." ;;
  status)
    if [[ -f "$TASK_RECORDS" ]]; then
      while read -r task_name task_pid task_token; do
        if task_owned "$task_pid" "$task_token"; then echo "$task_name: running ($task_pid)"; else echo "$task_name: stopped"; fi
      done < "$TASK_RECORDS"
    else echo "AuthZDiff is stopped."; fi ;;
  *) echo "Use start|stop|restart|status|health." >&2; exit 2 ;;
esac
