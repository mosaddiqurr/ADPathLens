from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VariableInput(BaseModel):
    scope: Literal["shared", "high", "low"]
    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,79}$")
    value: str = Field(max_length=8192)
    is_secret: bool = False


class TestCaseCreate(BaseModel):
    target_id: str
    imported_request_id: str
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=10_000)
    high_privilege_session_id: str
    low_privilege_session_id: str
    expected_behaviour: Literal[
        "lower_denied",
        "limited_fields",
        "different_records",
        "ownership_separation",
        "authenticated_only",
        "tenant_separation",
        "sensitive_fields_limited",
        "method_protection",
        "object_existence_indistinguishable",
        "baseline_consistency",
        "custom",
    ]
    custom_expectation: str = Field(default="", max_length=2000)
    approved_state_change: bool = False
    variables: list[VariableInput] = Field(default_factory=list, max_length=100)
    ignored_json_paths: list[str] = Field(default_factory=list, max_length=100)
    unordered_json_paths: list[str] = Field(default_factory=list, max_length=100)
    ignored_headers: list[str] = Field(default_factory=list, max_length=50)
    ignored_text_patterns: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def sessions_must_differ(self) -> TestCaseCreate:
        if self.high_privilege_session_id == self.low_privilege_session_id:
            raise ValueError("Comparison sessions must be different.")
        if self.expected_behaviour == "custom" and not self.custom_expectation.strip():
            raise ValueError("A custom expectation is required.")
        return self


class TestCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    target_id: str
    imported_request_id: str
    name: str
    description: str
    high_privilege_session_id: str
    low_privilege_session_id: str
    expected_behaviour: str
    custom_expectation: str
    approved_state_change: bool
    created_at: datetime
    updated_at: datetime


class RunAuthorization(BaseModel):
    authorization_confirmed: bool
    test_data_confirmed: bool = False
    typed_confirmation: str = ""


class RunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    test_case_id: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    initiated_by: str
    error_code: str | None
    error_message: str | None
    automated_classification: str | None
    confidence: str | None
    explanation: str | None
    engine_version: str
    cancellation_requested: bool
    progress_completed: int
    progress_total: int


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    comparison_run_id: str
    status: str
    request_count: int
    completed_count: int
    cancellation_requested: bool
    worker_id: str | None
    claimed_at: datetime | None
    heartbeat_at: datetime | None
    correlation_id: str
    attempt_count: int
    error_code: str | None
    error_message: str | None


class ObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    request_id: str
    session_id: str
    status_code: int | None
    redirect_outcome: str
    content_type: str | None
    safe_headers: list[list[str]]
    response_length: int
    duration_ms: float
    json_shape: dict[str, object] | None
    top_level_json_keys: list[str]
    structural_representation: dict[str, object] | list[object] | None
    sanitized_body_hash: str | None
    sanitized_excerpt: str | None
    error_category: str | None
    auth_challenge: bool
    access_denied_marker: bool
    object_existence_marker: bool
    success_markers: list[str]
    body_truncated: bool
    is_binary: bool


class RunDetail(BaseModel):
    run: RunRead
    job: JobRead | None
    observations: list[ObservationRead]
    difference: dict[str, object] | None
    context: dict[str, object]
