import asyncio
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_REPORT_DIR = Path(f"C:/tmp/adpathlens-test-reports-{os.getpid()}")

os.environ["APP_ENV"] = "development"
os.environ["APP_SECRET_KEY"] = "test-secret-key-that-is-longer-than-thirty-two-characters"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REPORT_STORAGE_PATH"] = str(TEST_REPORT_DIR)

from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402


async def reset_database() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)


@pytest.fixture
def client() -> Iterator[TestClient]:
    asyncio.run(reset_database())
    with TestClient(app) as test_client:
        yield test_client
    for report_file in TEST_REPORT_DIR.glob("*"):
        if report_file.is_file():
            report_file.unlink()
