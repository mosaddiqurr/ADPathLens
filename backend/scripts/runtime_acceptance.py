"""Prove process ownership, migration, restart persistence, and clean teardown."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

HOST = "127.0.0.1"
PORT = 8011
BASE_URL = f"http://{HOST}:{PORT}/api/v1"


def _port_is_free() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        return probe.connect_ex((HOST, PORT)) != 0


def _wait_ready(process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Backend exited early with code {process.returncode}.")
        try:
            response = httpx.get(f"{BASE_URL}/health", timeout=1)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    raise TimeoutError("Backend did not become ready within 30 seconds.")


def _start_backend(environment: dict[str, str]) -> subprocess.Popen[str]:
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            HOST,
            "--port",
            str(PORT),
            "--log-level",
            "warning",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    _wait_ready(process)
    return process


def _stop_backend(process: subprocess.Popen[str]) -> None:
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if _port_is_free():
            return
        time.sleep(0.1)
    raise RuntimeError("ADPathLens acceptance port remained open after owned-process teardown.")


def main() -> None:
    if not _port_is_free():
        raise RuntimeError(f"Acceptance port {PORT} is already occupied; no process was changed.")
    with tempfile.TemporaryDirectory(prefix="adpathlens-runtime-") as temp_directory:
        root = Path(temp_directory)
        database_path = root / "runtime.db"
        environment = os.environ.copy()
        environment.update(
            {
                "APP_ENV": "development",
                "APP_SECRET_KEY": "runtime-acceptance-secret-longer-than-thirty-two-characters",
                "DATABASE_URL": f"sqlite+aiosqlite:///{database_path.as_posix()}",
                "REPORT_STORAGE_PATH": str(root / "reports"),
                "SESSION_COOKIE_SECURE": "false",
                "PASSWORD_HASH_MEMORY_COST_KIB": "8192",
            }
        )
        backend_root = Path(__file__).resolve().parents[1]
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=backend_root,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )

        first = _start_backend(environment)
        try:
            with httpx.Client(base_url=BASE_URL, timeout=20) as client:
                setup = client.post(
                    "/auth/setup",
                    json={
                        "email": "runtime-admin@example.com",
                        "display_name": "Runtime Administrator",
                        "password": "Runtime-Correct-Horse-Battery-123",
                        "authorization_confirmed": True,
                    },
                )
                setup.raise_for_status()
                csrf = setup.json()["csrf_token"]
                workspace_id = client.get("/workspaces").json()[0]["id"]
                project = client.post(
                    "/projects",
                    headers={"X-CSRF-Token": csrf},
                    json={"workspace_id": workspace_id, "name": "Persistent Synthetic Project"},
                )
                project.raise_for_status()
                project_id = project.json()["id"]
                snapshot = client.post(
                    f"/projects/{project_id}/datasets/import-demo",
                    headers={"X-CSRF-Token": csrf},
                    json={"demo": "small", "authorization_confirmed": True},
                )
                snapshot.raise_for_status()
                snapshot_id = snapshot.json()["id"]
        finally:
            _stop_backend(first)

        second = _start_backend(environment)
        try:
            with httpx.Client(base_url=BASE_URL, timeout=20) as client:
                login = client.post(
                    "/auth/login",
                    json={
                        "email": "runtime-admin@example.com",
                        "password": "Runtime-Correct-Horse-Battery-123",
                    },
                )
                login.raise_for_status()
                persisted_project = client.get(f"/projects/{project_id}")
                persisted_snapshot = client.get(f"/snapshots/{snapshot_id}")
                persisted_project.raise_for_status()
                persisted_snapshot.raise_for_status()
                summary = client.get(f"/snapshots/{snapshot_id}/graph/summary")
                summary.raise_for_status()
        finally:
            _stop_backend(second)

        result = {
            "backend_port": PORT,
            "database_bytes": database_path.stat().st_size,
            "project_persisted": persisted_project.json()["id"] == project_id,
            "snapshot_persisted": persisted_snapshot.json()["id"] == snapshot_id,
            "nodes_after_restart": summary.json()["node_count"],
            "relationships_after_restart": summary.json()["relationship_count"],
            "port_free_after_teardown": _port_is_free(),
        }
        print("RUNTIME_ACCEPTANCE=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
