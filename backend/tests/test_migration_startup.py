import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from sqlalchemy import URL


def test_real_migrations_persist_schema_with_percent_in_database_url(tmp_path: Path) -> None:
    database = tmp_path / "directory%20snapshot.db"
    database_url = URL.create("sqlite+aiosqlite", database=database.as_posix()).render_as_string(hide_password=False)
    environment = {**os.environ, "DATABASE_URL": database_url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0003_completion",)
        columns = {row[1] for row in connection.execute("PRAGMA table_info(directory_nodes)")}
        assert {"stable_fingerprint", "first_seen_at", "last_seen_at"} <= columns


def test_repeated_migration_preserves_data(tmp_path: Path) -> None:
    database = tmp_path / "repeat.db"
    database_url = URL.create("sqlite+aiosqlite", database=database.as_posix()).render_as_string(hide_password=False)
    environment = {**os.environ, "DATABASE_URL": database_url}
    for _ in range(2):
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == ("0003_completion",)
