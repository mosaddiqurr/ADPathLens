"""Cross-platform, ownership-aware local runtime controller for ADPathLens."""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / ".runtime"
STATE_PATH = RUNTIME_DIR / "processes.json"
BACKEND_PORT = 8011
FRONTEND_PORT = 4173


def _pid_exists(pid: int) -> bool:
    if os.name == "nt":
        # Windows console signals do not reliably probe hidden process groups.
        return bool(_command_line(pid))
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def _command_line(pid: int) -> str:
    if os.name == "nt":
        command = [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            (f'(Get-CimInstance Win32_Process -Filter "ProcessId={pid}").CommandLine'),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
        return completed.stdout.strip()
    path = Path(f"/proc/{pid}/cmdline")
    return path.read_bytes().replace(b"\0", b" ").decode("utf-8", "replace") if path.exists() else ""


def _owned_process(pid: int, marker: str) -> bool:
    command_line = _command_line(pid).casefold()
    return marker.casefold() in command_line and "adpathlens" in command_line


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.settimeout(0.25)
        return client.connect_ex(("127.0.0.1", port)) == 0


def _choose_port(preferred: int, excluded: set[int] | None = None) -> int:
    for candidate in range(preferred, min(preferred + 100, 65_536)):
        if candidate in (excluded or set()) or _port_open(candidate):
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", candidate))
            except OSError:
                continue
        return candidate
    raise RuntimeError(f"No free loopback port found near {preferred}.")


def _runtime_ports() -> tuple[int, int]:
    state = _load_state()
    return (
        int(state.get("backend", {}).get("port", BACKEND_PORT)),
        int(state.get("frontend", {}).get("port", FRONTEND_PORT)),
    )


def _runtime_urls() -> tuple[str, str]:
    backend_port, frontend_port = _runtime_ports()
    return f"http://127.0.0.1:{backend_port}", f"http://127.0.0.1:{frontend_port}"


def _load_state() -> dict[str, Any]:
    if not STATE_PATH.is_file():
        return {}
    try:
        value = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state: dict[str, Any]) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _wait_for(url: str, timeout: float = 45.0) -> None:
    deadline = time.monotonic() + timeout
    last_error = "not reachable"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
                last_error = f"HTTP {response.status}"
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = str(exc)
        time.sleep(0.25)
    raise RuntimeError(f"Readiness timed out for {url}: {last_error}")


def _remove_stale_state() -> None:
    state = _load_state()
    if not state:
        return
    live_owned = False
    for name, marker in (("backend", "uvicorn"), ("frontend", "vite")):
        record = state.get(name)
        if not isinstance(record, dict):
            continue
        pid = int(record.get("pid", 0))
        if pid and _pid_exists(pid) and _owned_process(pid, marker):
            live_owned = True
    if not live_owned:
        STATE_PATH.unlink(missing_ok=True)


def start() -> None:
    _remove_stale_state()
    state = _load_state()
    if state:
        raise RuntimeError("ADPathLens is already running; use status or stop first.")
    backend_port = _choose_port(BACKEND_PORT)
    frontend_port = _choose_port(FRONTEND_PORT, {backend_port})
    backend_url = f"http://127.0.0.1:{backend_port}"
    frontend_url = f"http://127.0.0.1:{frontend_port}"

    from dotenv import dotenv_values

    file_values = {key: value for key, value in dotenv_values(ROOT / ".env").items() if value is not None}
    runtime_environment = {**file_values, **os.environ}
    runtime_environment.setdefault("LOCAL_MODE", "true")
    configured_origins = runtime_environment.get("ALLOWED_FRONTEND_ORIGINS", "")
    runtime_environment["ALLOWED_FRONTEND_ORIGINS"] = ",".join(
        dict.fromkeys([origin.strip() for origin in configured_origins.split(",") if origin.strip()] + [frontend_url])
    )
    if runtime_environment["LOCAL_MODE"].lower() == "true":
        runtime_environment.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./adpathlens-local.db")

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    backend_log = (RUNTIME_DIR / "backend.log").open("ab")
    frontend_log = (RUNTIME_DIR / "frontend.log").open("ab")
    creation_flags = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW) if os.name == "nt" else 0
    npm = "npm.cmd" if os.name == "nt" else "npm"
    backend: subprocess.Popen[bytes] | None = None
    frontend: subprocess.Popen[bytes] | None = None
    try:
        migration = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT / "backend",
            env=runtime_environment,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if migration.returncode:
            raise RuntimeError(f"Migration failed: {migration.stderr.strip()}")
        backend = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--no-proxy-headers",
                "--port",
                str(backend_port),
                "--app-dir",
                str(ROOT / "backend"),
            ],
            cwd=ROOT / "backend",
            env=runtime_environment,
            stdout=backend_log,
            stderr=subprocess.STDOUT,
            creationflags=creation_flags,
            start_new_session=os.name != "nt",
        )
        frontend = subprocess.Popen(
            [
                npm,
                "run",
                "dev",
                "--",
                "--host",
                "127.0.0.1",
                "--port",
                str(frontend_port),
                "--strictPort",
                "--config",
                str(ROOT / "frontend" / "vite.config.ts"),
            ],
            cwd=ROOT / "frontend",
            env={**os.environ, "VITE_API_PROXY_TARGET": backend_url},
            stdout=frontend_log,
            stderr=subprocess.STDOUT,
            creationflags=creation_flags,
            start_new_session=os.name != "nt",
        )
        _save_state(
            {
                "backend": {
                    "pid": backend.pid,
                    "marker": "uvicorn",
                    "port": backend_port,
                },
                "frontend": {
                    "pid": frontend.pid,
                    "marker": "vite",
                    "port": frontend_port,
                },
                "started_at": time.time(),
            }
        )
        _wait_for(f"{backend_url}/api/v1/ready")
        _wait_for(frontend_url)
    except Exception:
        try:
            if STATE_PATH.exists():
                stop()
            else:
                for process in (frontend, backend):
                    if process and process.poll() is None:
                        process.terminate()
        finally:
            raise
    finally:
        backend_log.close()
        frontend_log.close()
    print(f"ADPathLens is ready at {frontend_url} (API {backend_url})")


def stop() -> None:
    state = _load_state()
    if not state:
        print("ADPathLens is not running.")
        return
    failures: list[str] = []
    owned_ports = [int(record["port"]) for record in state.values() if isinstance(record, dict) and "port" in record]
    for name, marker in (("frontend", "vite"), ("backend", "uvicorn")):
        record = state.get(name)
        if not isinstance(record, dict):
            continue
        pid = int(record.get("pid", 0))
        if not pid or not _pid_exists(pid):
            continue
        if not _owned_process(pid, marker):
            failures.append(f"Refused to stop unverified PID {pid} recorded for {name}")
            continue
        if os.name == "nt":
            subprocess.run(
                ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                timeout=15,
                check=False,
            )
        else:
            os.killpg(pid, signal.SIGTERM)
    if failures:
        raise RuntimeError("; ".join(failures))
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and any(_port_open(port) for port in owned_ports):
        time.sleep(0.2)
    occupied = [port for port in owned_ports if _port_open(port)]
    if occupied:
        raise RuntimeError(f"ADPathLens port(s) did not close: {occupied}")
    STATE_PATH.unlink(missing_ok=True)
    print("ADPathLens stopped; owned ports are closed.")


def status() -> None:
    _remove_stale_state()
    state = _load_state()
    backend_port, frontend_port = _runtime_ports()
    result = {
        "running": bool(state),
        "backend": {
            "port": backend_port,
            "url": f"http://127.0.0.1:{backend_port}",
            "listening": _port_open(backend_port),
            "pid": state.get("backend", {}).get("pid") if state else None,
        },
        "frontend": {
            "port": frontend_port,
            "url": f"http://127.0.0.1:{frontend_port}",
            "listening": _port_open(frontend_port),
            "pid": state.get("frontend", {}).get("pid") if state else None,
        },
    }
    print(json.dumps(result, indent=2))


def health() -> None:
    backend_url, frontend_url = _runtime_urls()
    with urllib.request.urlopen(f"{backend_url}/api/v1/ready", timeout=5) as response:
        payload = json.load(response)
    with urllib.request.urlopen(frontend_url, timeout=5) as response:
        frontend_status = response.status
    print(json.dumps({"backend": payload, "frontend_http_status": frontend_status}, indent=2))


def _api_request(
    opener: urllib.request.OpenerDirector,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    csrf: str | None = None,
) -> Any:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if csrf:
        headers["X-CSRF-Token"] = csrf
    backend_url, _ = _runtime_urls()
    request = urllib.request.Request(f"{backend_url}/api/v1{path}", data=data, headers=headers, method=method)
    with opener.open(request, timeout=30) as response:
        body = response.read()
        return json.loads(body) if body else None


def seed_demo(reset: bool) -> None:
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    local = _api_request(opener, "/auth/local-status")
    if local.get("available"):
        backend_url, _ = _runtime_urls()
        request = urllib.request.Request(
            f"{backend_url}/api/v1/auth/local-session",
            data=b"",
            method="POST",
            headers={"X-ADPathLens-Local": "1"},
        )
        with opener.open(request, timeout=10):
            pass
        _seed_authenticated_demo(opener, reset)
        return
    password = os.environ.get("ADPATHLENS_SEED_PASSWORD", "")
    if len(password) < 12:
        raise RuntimeError("Set ADPATHLENS_SEED_PASSWORD (12+ characters) before seed or demo-reset.")
    email = os.environ.get("ADPATHLENS_SEED_EMAIL", "admin@northbridge.local")
    display_name = os.environ.get("ADPATHLENS_SEED_NAME", "NORTHBRIDGE Administrator")
    setup = _api_request(opener, "/auth/setup-status")
    if setup.get("setup_required"):
        _api_request(
            opener,
            "/auth/setup",
            method="POST",
            payload={
                "email": email,
                "display_name": display_name,
                "password": password,
                "authorization_confirmed": True,
            },
        )
    else:
        _api_request(
            opener,
            "/auth/login",
            method="POST",
            payload={"email": email, "password": password},
        )
    _seed_authenticated_demo(opener, reset)


def _seed_authenticated_demo(opener: urllib.request.OpenerDirector, reset: bool) -> None:
    csrf = _api_request(opener, "/auth/csrf")["csrf_token"]
    projects = _api_request(opener, "/projects")
    project = next((item for item in projects if item["name"] == "NORTHBRIDGE Guided Lab"), None)
    if not project:
        workspaces = _api_request(opener, "/workspaces")
        if not workspaces:
            workspace = _api_request(
                opener,
                "/workspaces",
                method="POST",
                csrf=csrf,
                payload={
                    "name": "NORTHBRIDGE Lab",
                    "description": "Fictional guided demo workspace",
                },
            )
        else:
            workspace = workspaces[0]
        project = _api_request(
            opener,
            "/projects",
            method="POST",
            csrf=csrf,
            payload={
                "workspace_id": workspace["id"],
                "name": "NORTHBRIDGE Guided Lab",
                "description": "Entirely fictional defensive AD graph lab",
            },
        )
    datasets = _api_request(opener, f"/projects/{project['id']}/datasets")
    if reset:
        for dataset in datasets:
            _api_request(opener, f"/datasets/{dataset['id']}", method="DELETE", csrf=csrf)
        datasets = []
    if not datasets:
        _api_request(
            opener,
            f"/projects/{project['id']}/datasets/import-demo",
            method="POST",
            csrf=csrf,
            payload={"demo": "small", "authorization_confirmed": True},
        )
    print(f"Fictional NORTHBRIDGE demo ready in project {project['id']}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("start", "stop", "restart", "status", "health", "seed", "demo-reset"),
    )
    args = parser.parse_args()
    try:
        if args.command == "start":
            start()
        elif args.command == "stop":
            stop()
        elif args.command == "restart":
            stop()
            start()
        elif args.command == "status":
            status()
        elif args.command == "health":
            health()
        elif args.command == "seed":
            seed_demo(False)
        else:
            seed_demo(True)
    except (
        RuntimeError,
        OSError,
        urllib.error.URLError,
        urllib.error.HTTPError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
