"""Start an isolated persistent backend for Playwright acceptance tests."""

import os
import tempfile
from pathlib import Path

test_runtime = tempfile.TemporaryDirectory(prefix="adpathlens-playwright-")
database_path = Path(test_runtime.name) / "test.db"
report_path = Path(test_runtime.name) / "reports"
frontend_port = int(os.environ.get("ADPATHLENS_E2E_FRONTEND_PORT", "5174"))
backend_port = int(os.environ.get("ADPATHLENS_E2E_BACKEND_PORT", "8011"))

os.environ["APP_ENV"] = "development"
os.environ["LOCAL_MODE"] = "false" if os.environ.get("ADPATHLENS_SHARED_E2E") == "1" else "true"
os.environ["DEMO_MODE"] = "false"
os.environ["ALLOWED_FRONTEND_ORIGINS"] = f"http://127.0.0.1:{frontend_port}"
os.environ["APP_SECRET_KEY"] = "playwright-secret-key-with-more-than-thirty-two-characters"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{database_path.as_posix()}"
os.environ["REPORT_STORAGE_PATH"] = str(report_path)
os.environ["SESSION_COOKIE_SECURE"] = "false"
os.environ["PASSWORD_HASH_MEMORY_COST_KIB"] = "8192"

if __name__ == "__main__":
    import uvicorn

    with test_runtime:
        uvicorn.run("app.main:app", host="127.0.0.1", port=backend_port, log_level="warning", proxy_headers=False)
