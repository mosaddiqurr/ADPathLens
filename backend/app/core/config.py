from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    session_expiry_minutes: int = Field(default=480, ge=15, le=10080)
    password_hash_memory_cost_kib: int = Field(default=65_536, ge=8_192)
    allowed_frontend_origins: str = "http://localhost:5173,http://localhost:8080"
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
        if self.app_env.lower() == "production":
            if "development-only" in self.app_secret_key.lower():
                raise RuntimeError("Production requires a non-development APP_SECRET_KEY")
            if not self.session_cookie_secure:
                raise RuntimeError("Production requires SESSION_COOKIE_SECURE=true")
            if self.password_hash_memory_cost_kib < 65_536:
                raise RuntimeError("Production requires PASSWORD_HASH_MEMORY_COST_KIB>=65536")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production()
    return settings
