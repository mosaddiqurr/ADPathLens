"""Migrate persistent SQLite storage, then start one direct Python service."""

import os
import subprocess
import sys
from pathlib import Path

import uvicorn
from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402


def main() -> None:
    os.chdir(Path(__file__).resolve().parents[1])
    settings = get_settings()
    database = make_url(settings.database_url).database
    if database and database != ":memory:":
        Path(database).parent.mkdir(parents=True, exist_ok=True)
    settings.report_storage_path.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), workers=1)


if __name__ == "__main__":
    main()
