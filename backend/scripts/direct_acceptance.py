"""Production-mode HTTPS, separate-origin browser, SQLite, and backend restart acceptance.

Requires OpenSSL and installed frontend development dependencies/Chromium.
All state and certificates are disposable; only owned servers are stopped.
"""

from __future__ import annotations

import functools
import json
import os
import secrets
import shutil
import socket
import sqlite3
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import URL

BACKEND = Path(__file__).resolve().parents[1]
FRONTEND = BACKEND.parent / "frontend"
EMAIL = "deployment@example.com"
PASSWORD = "Shared-Workflow-Regression-2026!"


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class StaticSPA(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        if not Path(self.translate_path(self.path)).is_file():
            self.path = "/index.html"
        super().do_GET()

    def log_message(self, format: str, *args: Any) -> None:
        pass


def stop(process: subprocess.Popen[Any]) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=True, capture_output=True, timeout=20)
        process.wait(timeout=5)
        return
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def request(client: httpx.Client, method: str, path: str, **kwargs: Any) -> httpx.Response:
    response = client.request(method, path, **kwargs)
    if response.is_error:
        raise RuntimeError(f"{method} {path}: {response.status_code} {response.text}")
    response.raise_for_status()
    return response


def main() -> None:
    openssl = shutil.which("openssl")
    if not openssl:
        bundled = Path("C:/Program Files/Git/usr/bin/openssl.exe")
        if bundled.is_file():
            openssl = str(bundled)
    if not openssl:
        raise RuntimeError("OpenSSL is required for disposable HTTPS acceptance certificates.")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        raise RuntimeError("npm is required for frontend acceptance.")
    with tempfile.TemporaryDirectory(prefix="adpathlens-direct-") as directory:
        root = Path(directory)
        certificate, key = root / "certificate.pem", root / "key.pem"
        subprocess.run(
            [
                openssl,
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-keyout",
                str(key),
                "-out",
                str(certificate),
                "-days",
                "1",
                "-subj",
                "/CN=localhost",
                "-addext",
                "subjectAltName=DNS:localhost,IP:127.0.0.1",
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        api_port, ui_port = free_port(), free_port()
        api_origin, ui_origin = f"https://localhost:{api_port}", f"https://localhost:{ui_port}"
        database = root / "persistent.db"
        environment = {
            **os.environ,
            "APP_ENV": "production",
            "APP_SECRET_KEY": secrets.token_urlsafe(48),
            "DATABASE_URL": URL.create("sqlite+aiosqlite", database=database.as_posix()).render_as_string(
                hide_password=False
            ),
            "REPORT_STORAGE_PATH": str(root / "reports"),
            "LOCAL_MODE": "false",
            "DEMO_MODE": "false",
            "E2E_MODE": "false",
            "SESSION_COOKIE_SECURE": "true",
            "SESSION_COOKIE_SAMESITE": "lax",
            "PASSWORD_HASH_MEMORY_COST_KIB": "65536",
            "ALLOWED_FRONTEND_ORIGINS": ui_origin,
            "FRONTEND_PUBLIC_URL": ui_origin,
            "BACKEND_PUBLIC_URL": api_origin,
        }
        tls = ssl.create_default_context(cafile=str(certificate))
        client = httpx.Client(base_url=f"{api_origin}/api/v1", verify=tls, timeout=30, trust_env=False)
        processes: list[subprocess.Popen[Any]] = []
        server: ThreadingHTTPServer | None = None
        log = (root / "backend.log").open("w")

        def start() -> subprocess.Popen[Any]:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(api_port),
                    "--ssl-certfile",
                    str(certificate),
                    "--ssl-keyfile",
                    str(key),
                    "--no-proxy-headers",
                    "--workers",
                    "1",
                ],
                cwd=BACKEND,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            processes.append(process)
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"Backend exited: {(root / 'backend.log').read_text()}")
                try:
                    if client.get("/ready").status_code == 200:
                        return process
                except httpx.HTTPError:
                    pass
                time.sleep(0.2)
            raise RuntimeError("Production backend readiness timed out.")

        def migrate() -> None:
            subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                cwd=BACKEND,
                env=environment,
                check=True,
                capture_output=True,
                timeout=60,
            )

        try:
            migrate()
            first = start()
            setup = request(
                client,
                "POST",
                "/auth/setup",
                json={
                    "email": EMAIL,
                    "display_name": "Deployment analyst",
                    "password": PASSWORD,
                    "authorization_confirmed": True,
                },
            )
            cookie = setup.headers["set-cookie"].lower()
            assert "secure" in cookie and "httponly" in cookie and "samesite=lax" in cookie
            csrf = {"X-CSRF-Token": setup.json()["csrf_token"]}
            workspace = request(client, "GET", "/workspaces").json()[0]["id"]
            project = request(
                client,
                "POST",
                "/projects",
                headers=csrf,
                json={
                    "workspace_id": workspace,
                    "name": "Restart persistence",
                },
            ).json()["id"]
            snapshot = request(
                client,
                "POST",
                f"/projects/{project}/datasets/import-demo",
                headers=csrf,
                json={"demo": "small", "authorization_confirmed": True},
            ).json()["id"]
            upload = (FRONTEND / "public/northbridge-demo.json").read_bytes()
            upload_project = request(
                client,
                "POST",
                "/projects",
                headers=csrf,
                json={
                    "workspace_id": workspace,
                    "name": "Uploaded persistence",
                },
            ).json()["id"]
            validation = request(
                client,
                "POST",
                f"/projects/{upload_project}/datasets/validate-json",
                headers=csrf,
                files={"file": ("directory.json", upload, "application/json")},
            ).json()
            assert validation["valid"]
            imported = request(
                client,
                "POST",
                f"/projects/{upload_project}/datasets/import-json",
                headers=csrf,
                files={"file": ("directory.json", upload, "application/json")},
                data={
                    "validation_digest": validation["digest"],
                    "authorization_confirmed": "true",
                    "name": "Uploaded directory",
                    "acknowledged_warnings": ",".join(
                        message["code"] for message in validation["messages"] if message["level"] == "warning"
                    ),
                },
            ).json()["id"]
            nodes = request(client, "GET", f"/snapshots/{snapshot}/nodes", params={"page_size": 100}).json()["items"]
            target = next(node["id"] for node in nodes if node["display_name"] == "Domain Admins")
            source = next(node["id"] for node in nodes if node["display_name"] == "Mina Rahman")
            payload = {
                "start_node_id": source,
                "target_node_id": target,
                "algorithm": "top_paths",
                "maximum_depth": 12,
                "maximum_paths": 25,
            }
            analysis = request(client, "POST", f"/snapshots/{snapshot}/analyses", headers=csrf, json=payload).json()
            assert analysis["path_count"] > 0
            reports = []
            for format in ("pdf", "json"):
                report = request(
                    client,
                    "POST",
                    f"/projects/{project}/reports",
                    headers=csrf,
                    json={
                        "snapshot_id": snapshot,
                        "analysis_id": analysis["id"],
                        "report_type": "executive",
                        "format": format,
                    },
                ).json()["id"]
                content = request(client, "GET", f"/reports/{report}/download").content
                assert (
                    content.startswith(b"%PDF") if format == "pdf" else json.loads(content)["source"]["important_paths"]
                )
                reports.append((report, content))
            with ThreadPoolExecutor(max_workers=6) as pool:
                results = list(
                    pool.map(
                        lambda index: (
                            request(
                                client,
                                "POST",
                                "/projects",
                                headers=csrf,
                                json={
                                    "workspace_id": workspace,
                                    "name": f"Concurrent project {index}",
                                },
                            ).status_code
                        ),
                        range(12),
                    )
                )
            assert results == [201] * 12
            stop(first)
            migrate()
            start()
            assert request(client, "GET", "/auth/me").json()["email"] == EMAIL
            assert request(client, "GET", f"/analyses/{analysis['id']}").json() == analysis
            for persisted in (snapshot, imported):
                summary = request(client, "GET", f"/snapshots/{persisted}/graph/summary").json()
                assert summary["node_count"] == 35 and summary["relationship_count"] == 56
            for report, content in reports:
                assert request(client, "GET", f"/reports/{report}/download").content == content
            assert (
                request(client, "POST", f"/snapshots/{snapshot}/analyses", headers=csrf, json=payload).json()[
                    "path_count"
                ]
                > 0
            )
            preflight = client.options(
                "/projects",
                headers={
                    "Origin": ui_origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type,x-csrf-token",
                },
            )
            assert preflight.status_code == 200
            assert preflight.headers["access-control-allow-origin"] == ui_origin
            assert preflight.headers["access-control-allow-credentials"] == "true"
            assert (
                "access-control-allow-origin"
                not in client.get("/auth/me", headers={"Origin": "https://untrusted.example"}).headers
            )
            assert client.post("/projects", json={"workspace_id": workspace, "name": "No CSRF"}).status_code == 403
            raw_session = client.cookies.get("adpathlens_session")
            assert request(client, "POST", "/auth/logout", headers=csrf).status_code == 204
            assert client.get("/auth/me").status_code == 401
            assert client.get("/auth/me", headers={"Cookie": f"adpathlens_session={raw_session}"}).status_code == 401
            assert client.post("/auth/login", json={"email": EMAIL, "password": "Invalid-password"}).status_code == 401
            assert (
                request(client, "POST", "/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 200
            )
            with closing(sqlite3.connect(database)) as connection:
                assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
                assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)
                assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0003_completion",)
            browser_env = {
                **os.environ,
                "VITE_API_URL": api_origin,
                "ADPATHLENS_EXTERNAL_E2E": "1",
                "ADPATHLENS_SHARED_E2E": "1",
                "ADPATHLENS_BUILT_E2E": "1",
                "ADPATHLENS_E2E_BASE_URL": ui_origin,
                "ADPATHLENS_E2E_API_URL": api_origin,
            }
            subprocess.run([npm, "run", "build"], cwd=FRONTEND, env=browser_env, check=True, timeout=120)
            server = ThreadingHTTPServer(
                ("127.0.0.1", ui_port), functools.partial(StaticSPA, directory=str(FRONTEND / "dist"))
            )
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certificate, key)
            server.socket = context.wrap_socket(server.socket, server_side=True)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            subprocess.run([npm, "run", "test:e2e"], cwd=FRONTEND, env=browser_env, check=True, timeout=180)
            print(
                "DIRECT_ACCEPTANCE="
                + json.dumps(
                    {
                        "production_https": True,
                        "cross_origin_browser": True,
                        "session_survived_backend_restart": True,
                        "demo_and_upload_persisted": True,
                        "analysis_and_exports_persisted": True,
                        "new_analysis_after_restart": True,
                        "concurrent_writes": 12,
                        "sqlite_integrity": "ok",
                        "journal_mode": "wal",
                    },
                    sort_keys=True,
                )
            )
        finally:
            client.close()
            if server:
                server.shutdown()
                server.server_close()
            for process in processes:
                if process.poll() is None:
                    stop(process)
            log.close()


if __name__ == "__main__":
    main()
