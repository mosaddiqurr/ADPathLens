from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "AuthZDiff"
    app_version: str = "1.0.0-rc1"
    app_secret_key: str = "development-only-secret-key-change-me"
    first_admin_setup_token: str = "development-setup-token"
    session_cookie_name: str = "authzdiff_session"
    session_cookie_secure: bool = False
    session_expiry_minutes: int = Field(default=480, ge=15, le=10_080)
    database_url: str = "sqlite+aiosqlite:///./authzdiff.db"
    encryption_master_key: str = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    encryption_old_keys: str = ""
    allowed_frontend_origins: str = "http://localhost:5173,http://localhost:8080"
    allowed_hosts: str = "localhost,127.0.0.1"
    max_har_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    max_request_body_bytes: int = Field(default=1024 * 1024, ge=1024)
    max_response_bytes: int = Field(default=2 * 1024 * 1024, ge=1024)
    max_report_excerpt_bytes: int = Field(default=100 * 1024, ge=1024)
    default_request_timeout_seconds: int = Field(default=10, ge=1, le=60)
    max_redirects: int = Field(default=3, ge=0, le=10)
    max_decompression_ratio: int = Field(default=100, ge=1, le=1000)
    replay_execution_mode: Literal["inprocess", "external"] = "inprocess"
    replay_global_concurrency: int = Field(default=5, ge=1, le=50)
    replay_worker_poll_ms: int = Field(default=250, ge=50, le=10_000)
    replay_worker_heartbeat_seconds: int = Field(default=5, ge=1, le=60)
    replay_stale_after_seconds: int = Field(default=45, ge=10, le=3600)
    global_state_changes_enabled: bool = False
    log_level: str = "INFO"
    demo_mode: bool = False
    fixture_mode: bool = False
    e2e_mode: bool = False
    application_url: str = "http://localhost:8020"
    frontend_url: str = "http://localhost:4174"
    demo_target_url: str = "http://127.0.0.1:8021"
    demo_reset_token: str = "development-demo-reset-token"
    custom_ca_path: str = ""
    report_storage_path: Path = Path("../var/reports")

    @field_validator("allowed_frontend_origins", "allowed_hosts")
    @classmethod
    def reject_empty_lists(cls, value: str) -> str:
        if not [part.strip() for part in value.split(",") if part.strip()]:
            raise ValueError("must contain at least one value")
        return value

    @model_validator(mode="after")
    def production_secrets_must_be_replaced(self) -> Settings:
        if self.app_env == "production":
            forbidden = {
                "development-only-secret-key-change-me",
                "development-setup-token",
                "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
                "development-demo-reset-token",
            }
            values = {
                self.app_secret_key,
                self.first_admin_setup_token,
                self.encryption_master_key,
            }
            if forbidden & values:
                raise ValueError("production secrets must be explicitly configured")
            if not self.session_cookie_secure:
                raise ValueError("SESSION_COOKIE_SECURE must be true in production")
            if len(self.app_secret_key) < 32:
                raise ValueError("APP_SECRET_KEY must be at least 32 characters in production")
            if self.demo_mode or self.fixture_mode or self.e2e_mode:
                raise ValueError("demo, fixture and E2E modes are forbidden in production")
            if self.replay_execution_mode != "external":
                raise ValueError("REPLAY_EXECUTION_MODE must be external in production")
            origins = [*self.cors_origins, self.application_url, self.frontend_url]
            if any("*" in origin for origin in origins):
                raise ValueError("wildcard origins are forbidden in production")
            if any(urlsplit(origin).scheme != "https" for origin in origins):
                raise ValueError("public application origins must use HTTPS in production")
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [part.strip() for part in self.allowed_frontend_origins.split(",") if part.strip()]

    @property
    def trusted_hosts(self) -> list[str]:
        return [part.strip() for part in self.allowed_hosts.split(",") if part.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
