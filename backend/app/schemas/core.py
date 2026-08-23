from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.parsers.request_import import RequestImportError, canonicalize_path


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[object]


class CsrfResponse(BaseModel):
    csrf_token: str


class SetupStatus(BaseModel):
    setup_required: bool
    authorized_use_version: str = "1.0"


class SetupRequest(BaseModel):
    setup_token: str = Field(min_length=16, max_length=256)
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=128)
    authorization_acknowledgement: Literal[
        "I confirm that I own this target or have explicit authorization to test it."
    ]


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    initial_password: str = Field(min_length=12, max_length=128)
    role: Literal["administrator", "analyst"] = "analyst"


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    role: Literal["administrator", "analyst"] | None = None
    is_active: bool | None = None


class UserRead(ORMModel):
    id: str
    email: EmailStr
    display_name: str
    role: str
    is_active: bool
    must_change_password: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None


class LoginResponse(BaseModel):
    user: UserRead
    csrf_token: str


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=10_000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=10_000)
    status: Literal["active", "archived"] | None = None


class DeleteConfirmation(BaseModel):
    confirmation: str = Field(min_length=1, max_length=200)


class ProjectRead(ORMModel):
    id: str
    name: str
    description: str
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class TargetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    base_url: str = Field(min_length=8, max_length=2048)
    follow_redirects: bool = False
    maximum_redirects: int = Field(default=3, ge=0, le=10)
    timeout_seconds: int = Field(default=10, ge=1, le=60)
    per_run_timeout_seconds: int = Field(default=60, ge=5, le=600)
    request_budget: int = Field(default=25, ge=1, le=500)
    maximum_response_bytes: int = Field(default=2 * 1024 * 1024, ge=1024, le=10 * 1024 * 1024)
    concurrency_limit: int = Field(default=2, ge=1, le=5)
    allowed_path_prefixes: list[str] = Field(default_factory=lambda: ["/"], max_length=50)
    allowed_methods: list[str] = Field(default_factory=lambda: ["GET", "HEAD"], max_length=10)
    tls_policy: Literal["strict", "custom_ca"] = "strict"
    state_changes_enabled: bool = False
    local_test_target: bool = False
    authorization_expires_at: datetime | None = None

    @field_validator("allowed_path_prefixes")
    @classmethod
    def validate_path_prefixes(cls, values: list[str]) -> list[str]:
        if not values:
            raise ValueError("At least one allowed path prefix is required.")
        normalized: set[str] = set()
        for value in values:
            if "?" in value or "#" in value:
                raise ValueError("Allowed path prefixes must be absolute URL paths.")
            try:
                normalized.add(canonicalize_path(value))
            except RequestImportError as exc:
                raise ValueError(exc.detail) from exc
        return sorted(normalized)

    @field_validator("allowed_methods")
    @classmethod
    def validate_methods(cls, values: list[str]) -> list[str]:
        supported = {"GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"}
        normalized = {value.upper() for value in values}
        if not normalized or not normalized <= supported:
            raise ValueError("One or more target methods are unsupported.")
        return sorted(normalized)


class TargetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    follow_redirects: bool | None = None
    maximum_redirects: int | None = Field(default=None, ge=0, le=10)
    timeout_seconds: int | None = Field(default=None, ge=1, le=60)
    per_run_timeout_seconds: int | None = Field(default=None, ge=5, le=600)
    request_budget: int | None = Field(default=None, ge=1, le=500)
    maximum_response_bytes: int | None = Field(default=None, ge=1024, le=10 * 1024 * 1024)
    concurrency_limit: int | None = Field(default=None, ge=1, le=5)
    allowed_path_prefixes: list[str] | None = Field(default=None, max_length=50)
    allowed_methods: list[str] | None = Field(default=None, max_length=10)
    tls_policy: Literal["strict", "custom_ca"] | None = None
    state_changes_enabled: bool | None = None
    authorization_expires_at: datetime | None = None
    is_active: bool | None = None


class AuthorizationConfirmation(BaseModel):
    acknowledgement: Literal[
        "I confirm that I own this target or have explicit authorization to test it."
    ]


class LabConfirmation(BaseModel):
    acknowledgement: Literal[
        "I confirm this private or loopback destination is an authorized local laboratory."
    ]
    allow_private_networks: bool


class AllowlistEntryCreate(BaseModel):
    entry_type: Literal["hostname", "ip", "cidr"]
    value: str = Field(min_length=1, max_length=253)
    allowed_port: int = Field(ge=1, le=65535)
    notes: str = Field(default="", max_length=500)


class AllowlistEntryRead(ORMModel):
    id: str
    entry_type: str
    value: str
    allowed_port: int
    notes: str
    created_at: datetime


class TargetRead(ORMModel):
    id: str
    project_id: str
    name: str
    base_url: str
    scheme: str
    hostname: str
    port: int
    authorization_confirmed: bool
    lab_network_confirmed: bool
    allow_private_networks: bool
    follow_redirects: bool
    maximum_redirects: int
    timeout_seconds: int
    per_run_timeout_seconds: int
    request_budget: int
    request_count_used: int
    maximum_response_bytes: int
    last_execution_at: datetime | None
    concurrency_limit: int
    allowed_path_prefixes: list[str]
    allowed_methods: list[str]
    tls_policy: str
    state_changes_enabled: bool
    local_test_target: bool
    authorization_expires_at: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TargetValidation(BaseModel):
    valid: bool
    normalized_url: str
    resolved_addresses: list[str]


class HeaderPair(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    value: str = Field(max_length=8192)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.replace("-", "").isalnum():
            raise ValueError("Header names may contain only letters, numbers, and hyphens.")
        return value


class TestSessionCreate(BaseModel):
    target_id: str
    name: str = Field(min_length=1, max_length=160)
    role_label: str = Field(min_length=1, max_length=80)
    is_anonymous: bool = False
    description: str = Field(default="", max_length=10_000)
    cookie_header: str | None = Field(default=None, max_length=32_768)
    authorization_header: str | None = Field(default=None, max_length=32_768)
    custom_headers: list[HeaderPair] = Field(default_factory=list, max_length=50)
    expires_at: datetime | None = None

    @field_validator("cookie_header", "authorization_header")
    @classmethod
    def reject_header_injection(cls, value: str | None) -> str | None:
        if value is not None and ("\r" in value or "\n" in value):
            raise ValueError("Header values cannot contain line breaks.")
        return value


class TestSessionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    role_label: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=10_000)
    expires_at: datetime | None = None
    is_active: bool | None = None


class TestSessionSecretReplace(BaseModel):
    cookie_header: str | None = Field(default=None, max_length=32_768)
    authorization_header: str | None = Field(default=None, max_length=32_768)
    custom_headers: list[HeaderPair] = Field(default_factory=list, max_length=50)

    @field_validator("cookie_header", "authorization_header")
    @classmethod
    def reject_header_injection(cls, value: str | None) -> str | None:
        if value is not None and ("\r" in value or "\n" in value):
            raise ValueError("Header values cannot contain line breaks.")
        return value


class TestSessionRead(ORMModel):
    id: str
    project_id: str
    target_id: str
    name: str
    role_label: str
    description: str
    secret_fingerprint: str
    is_anonymous: bool
    credential_version: int
    expires_at: datetime | None
    last_used_at: datetime | None
    is_active: bool
    created_by: str
    created_at: datetime
    updated_at: datetime


class SettingsRead(BaseModel):
    authorized_use_version: str
    setup_completed: bool
    global_state_changes_enabled: bool


class SettingsUpdate(BaseModel):
    global_state_changes_enabled: bool


class AuditEventRead(ORMModel):
    id: str
    user_id: str | None
    action: str
    entity_type: str
    entity_id: str | None
    project_id: str | None
    outcome: str
    summary: str
    safe_metadata: dict[str, object]
    source_ip: str | None
    request_id: str | None
    correlation_id: str | None
    created_at: datetime
