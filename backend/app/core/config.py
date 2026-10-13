from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    allowed_frontend_origins: str = "http://localhost:4174,http://127.0.0.1:4174"
    allowed_hosts: str = "localhost,127.0.0.1,backend"
    max_body_bytes: int = Field(default=12 * 1024 * 1024, ge=1024, le=24 * 1024 * 1024)

    @field_validator("allowed_frontend_origins", "allowed_hosts")
    @classmethod
    def explicit_lists(cls, value: str) -> str:
        parts = [part.strip() for part in value.split(",") if part.strip()]
        if not parts or any("*" in part for part in parts):
            raise ValueError("Explicit hosts and origins are required.")
        return ",".join(parts)

    @field_validator("allowed_frontend_origins")
    @classmethod
    def exact_origins(cls, value: str) -> str:
        for part in value.split(","):
            origin = urlsplit(part)
            if (
                origin.scheme not in {"http", "https"}
                or not origin.hostname
                or origin.username is not None
                or origin.password is not None
                or origin.path
                or origin.query
                or origin.fragment
                or part != f"{origin.scheme}://{origin.netloc}"
            ):
                raise ValueError("Use exact HTTP(S) origins without paths or credentials.")
            _ = origin.port  # Reject malformed/out-of-range ports at startup.
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [part.strip() for part in self.allowed_frontend_origins.split(",")]

    @property
    def trusted_hosts(self) -> list[str]:
        return [part.strip() for part in self.allowed_hosts.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
