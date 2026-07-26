"""Start an isolated persistent backend for Playwright acceptance tests."""

import os
import tempfile
from pathlib import Path

database_path = Path(tempfile.gettempdir()) / "adpathlens-playwright.db"
database_path.unlink(missing_ok=True)
report_path = Path(tempfile.gettempdir()) / "adpathlens-playwright-reports"

os.environ["APP_ENV"] = "development"
os.environ["APP_SECRET_KEY"] = "playwright-secret-key-with-more-than-thirty-two-characters"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{database_path.as_posix()}"
os.environ["REPORT_STORAGE_PATH"] = str(report_path)
os.environ["SESSION_COOKIE_SECURE"] = "false"
os.environ["PASSWORD_HASH_MEMORY_COST_KIB"] = "8192"

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8011, log_level="warning")
