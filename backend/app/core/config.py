from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "ADPathLens"
    app_secret_key: str = "development-only-change-this-secret-key"
    database_url: str = "sqlite+aiosqlite:///./adpathlens.db"
    session_cookie_name: str = "adpathlens_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    session_expiry_minutes: int = Field(default=480, ge=15, le=10080)
    password_hash_memory_cost_kib: int = Field(default=65_536, ge=8_192)
    allowed_frontend_origins: str = (
        "http://127.0.0.1:4173,http://localhost:4173,http://127.0.0.1:5173,http://localhost:5173"
    )
    max_upload_bytes: int = Field(default=52_428_800, ge=1024)
    max_archive_entries: int = Field(default=100, ge=2, le=1000)
    max_uncompressed_bytes: int = Field(default=209_715_200, ge=1024)
    max_json_depth: int = Field(default=20, ge=3, le=100)
    max_csv_rows: int = Field(default=125_000, ge=1)
    max_graph_nodes: int = Field(default=25_000, ge=1)
    max_graph_relationships: int = Field(default=100_000, ge=1)
    max_path_depth: int = Field(default=12, ge=1, le=50)
    max_returned_paths: int = Field(default=25, ge=1, le=100)
    graph_cache_ttl_seconds: int = Field(default=300, ge=0)
    report_storage_path: Path = Path("./reports")
    log_level: str = "INFO"
    demo_mode: bool = True
    local_mode: bool = False
    e2e_mode: bool = False
    frontend_public_url: str = "http://localhost:5173"
    backend_public_url: str = "http://localhost:8000"
    max_analysis_expansions: int = Field(default=100_000, ge=100, le=5_000_000)
    analysis_deadline_seconds: float = Field(default=5.0, ge=0.1, le=60.0)

    @field_validator("app_secret_key")
    @classmethod
    def validate_secret(cls, value: str, info: object) -> str:
        if len(value) < 32:
            raise ValueError("APP_SECRET_KEY must contain at least 32 characters")
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.allowed_frontend_origins.split(",") if item.strip()]

    def validate_production(self) -> None:
        database = make_url(self.database_url)
        if database.drivername != "sqlite+aiosqlite":
            raise RuntimeError("DATABASE_URL must use sqlite+aiosqlite")
        if self.session_cookie_samesite == "none" and not self.session_cookie_secure:
            raise RuntimeError("SameSite=None requires SESSION_COOKIE_SECURE=true")
        if self.local_mode and self.app_env.lower() != "development":
            raise RuntimeError("LOCAL_MODE is available only in development")
        if self.app_env.lower() == "production":
            lowered_secret = self.app_secret_key.lower()
            weak_markers = ("development", "replace", "change-this", "example", "password", "secret-key")
            if any(marker in lowered_secret for marker in weak_markers):
                raise RuntimeError("Production requires a non-development APP_SECRET_KEY")
            if not self.session_cookie_secure:
                raise RuntimeError("Production requires SESSION_COOKIE_SECURE=true")
            if self.password_hash_memory_cost_kib < 65_536:
                raise RuntimeError("Production requires PASSWORD_HASH_MEMORY_COST_KIB>=65536")
            if self.demo_mode or self.e2e_mode:
                raise RuntimeError("Production requires DEMO_MODE=false and E2E_MODE=false")
            if not self.cors_origins or "*" in self.cors_origins:
                raise RuntimeError("Production requires an explicit CORS origin allow-list")
            for origin in self.cors_origins:
                parsed = urlparse(origin)
                if parsed.scheme != "https" or not parsed.netloc or parsed.path not in {"", "/"}:
                    raise RuntimeError("Production CORS origins must be HTTPS origins without paths")
            for value in (self.frontend_public_url, self.backend_public_url):
                parsed = urlparse(value)
                if parsed.scheme != "https" or not parsed.netloc:
                    raise RuntimeError("Production public URLs must use HTTPS")
            if not database.database or not Path(database.database).is_absolute():
                raise RuntimeError("Production requires an absolute persistent SQLite database path")
            if not self.report_storage_path.is_absolute():
                raise RuntimeError("Production REPORT_STORAGE_PATH must be absolute")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production()
    return settings
