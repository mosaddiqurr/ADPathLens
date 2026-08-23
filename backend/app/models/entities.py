from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('administrator','analyst')", name="valid_role"),)

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthSession(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "auth_sessions"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LoginRateLimitBucket(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "login_rate_limit_buckets"

    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class AppSetting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "app_settings"

    singleton_key: Mapped[str] = mapped_column(String(32), unique=True, default="global")
    authorized_use_version: Mapped[str] = mapped_column(String(32), default="1.0", nullable=False)
    setup_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    global_state_changes_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("status IN ('active','archived')", name="valid_status"),
        Index("ix_projects_status_updated", "status", "updated_at"),
    )

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectPolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_policies"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    redaction_keys: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    ignored_headers: Mapped[list[str]] = mapped_column(
        JSON,
        default=lambda: ["date", "server-timing", "x-request-id", "traceparent"],
        nullable=False,
    )
    ignored_text_patterns: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class Target(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "targets"
    __table_args__ = (
        CheckConstraint("scheme IN ('http','https')", name="valid_scheme"),
        CheckConstraint("port BETWEEN 1 AND 65535", name="valid_port"),
        CheckConstraint("maximum_redirects BETWEEN 0 AND 10", name="redirect_limit"),
        CheckConstraint("timeout_seconds BETWEEN 1 AND 60", name="timeout_limit"),
        Index("ix_targets_project_active", "project_id", "is_active"),
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    scheme: Mapped[str] = mapped_column(String(8), nullable=False)
    hostname: Mapped[str] = mapped_column(String(253), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    authorization_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    authorization_confirmed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    authorization_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lab_network_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    lab_network_confirmed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    lab_network_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    allow_private_networks: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    follow_redirects: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    maximum_redirects: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    per_run_timeout_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    request_budget: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    request_count_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    maximum_response_bytes: Mapped[int] = mapped_column(
        Integer, default=2 * 1024 * 1024, nullable=False
    )
    last_execution_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    concurrency_limit: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    allowed_path_prefixes: Mapped[list[str]] = mapped_column(
        JSON, default=lambda: ["/"], nullable=False
    )
    allowed_methods: Mapped[list[str]] = mapped_column(
        JSON, default=lambda: ["GET", "HEAD"], nullable=False
    )
    tls_policy: Mapped[str] = mapped_column(String(24), default="strict", nullable=False)
    state_changes_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    local_test_target: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    authorization_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)


class TargetAllowlistEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "target_allowlist_entries"
    __table_args__ = (
        CheckConstraint("entry_type IN ('hostname','ip','cidr')", name="valid_entry_type"),
        CheckConstraint("allowed_port BETWEEN 1 AND 65535", name="valid_port"),
        UniqueConstraint(
            "target_id", "entry_type", "value", "allowed_port", name="entry_per_target"
        ),
    )

    target_id: Mapped[str] = mapped_column(
        ForeignKey("targets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    entry_type: Mapped[str] = mapped_column(String(16), nullable=False)
    value: Mapped[str] = mapped_column(String(253), nullable=False)
    allowed_port: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)


class TestSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "test_sessions"
    __table_args__ = (Index("ix_test_sessions_project_target", "project_id", "target_id"),)

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[str] = mapped_column(
        ForeignKey("targets.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    role_label: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    encrypted_cookie_data: Mapped[bytes | None] = mapped_column(LargeBinary)
    encrypted_authorization_header: Mapped[bytes | None] = mapped_column(LargeBinary)
    encrypted_custom_headers: Mapped[bytes | None] = mapped_column(LargeBinary)
    secret_fingerprint: Mapped[str] = mapped_column(String(24), nullable=False)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    credential_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)


class ImportedRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "imported_requests"
    __table_args__ = (
        CheckConstraint("scheme IN ('http','https')", name="valid_scheme"),
        CheckConstraint("port BETWEEN 1 AND 65535", name="valid_port"),
        Index("ix_imported_requests_project_target", "project_id", "target_id"),
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    collection_id: Mapped[str | None] = mapped_column(
        ForeignKey("request_collections.id", ondelete="CASCADE")
    )
    target_id: Mapped[str] = mapped_column(
        ForeignKey("targets.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    import_type: Mapped[str] = mapped_column(String(24), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    scheme: Mapped[str] = mapped_column(String(8), nullable=False)
    hostname: Mapped[str] = mapped_column(String(253), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    path: Mapped[str] = mapped_column(String(4096), nullable=False)
    query_parameters: Mapped[list[list[str]]] = mapped_column(JSON, default=list, nullable=False)
    sanitized_headers: Mapped[list[list[str]]] = mapped_column(JSON, default=list, nullable=False)
    encrypted_secret_headers: Mapped[bytes | None] = mapped_column(LargeBinary)
    content_type: Mapped[str | None] = mapped_column(String(255))
    body_template: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_state_changing: Mapped[bool] = mapped_column(Boolean, nullable=False)
    approved_state_change: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expected_markers: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    sensitivity: Mapped[str] = mapped_column(String(24), default="internal", nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)


class RequestCollection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "request_collections"
    __table_args__ = (Index("ix_request_collections_project_updated", "project_id", "updated_at"),)

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[str] = mapped_column(
        ForeignKey("targets.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)


class TestCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "test_cases"
    __table_args__ = (
        CheckConstraint(
            "expected_behaviour IN "
            "('lower_denied','limited_fields','different_records','ownership_separation',"
            "'authenticated_only','tenant_separation','sensitive_fields_limited',"
            "'method_protection','object_existence_indistinguishable','baseline_consistency',"
            "'custom')",
            name="valid_expectation",
        ),
        Index("ix_test_cases_project_target", "project_id", "target_id"),
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[str] = mapped_column(
        ForeignKey("targets.id", ondelete="CASCADE"), nullable=False
    )
    imported_request_id: Mapped[str] = mapped_column(
        ForeignKey("imported_requests.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    high_privilege_session_id: Mapped[str] = mapped_column(
        ForeignKey("test_sessions.id"), nullable=False
    )
    low_privilege_session_id: Mapped[str] = mapped_column(
        ForeignKey("test_sessions.id"), nullable=False
    )
    expected_behaviour: Mapped[str] = mapped_column(String(40), nullable=False)
    custom_expectation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    approved_state_change: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    state_change_approved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    state_change_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ignored_json_paths: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    unordered_json_paths: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    ignored_headers: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    ignored_text_patterns: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)


class TestCaseVariable(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "test_case_variables"
    __table_args__ = (
        CheckConstraint("scope IN ('shared','high','low')", name="valid_scope"),
        UniqueConstraint("test_case_id", "scope", "name", name="variable_per_scope"),
    )

    test_case_id: Mapped[str] = mapped_column(
        ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False
    )
    scope: Mapped[str] = mapped_column(String(12), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    encrypted_value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ComparisonRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "comparison_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN "
            "('queued','running','cancelling','cancelled','completed','failed','interrupted')",
            name="valid_status",
        ),
        Index("ix_runs_test_case_started", "test_case_id", "started_at"),
    )

    test_case_id: Mapped[str] = mapped_column(
        ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    initiated_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(String(500))
    automated_classification: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[str | None] = mapped_column(String(16))
    explanation: Mapped[str | None] = mapped_column(Text)
    engine_version: Mapped[str] = mapped_column(
        String(40), default="authzdiff-rules/1.1", nullable=False
    )
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    progress_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_total: Mapped[int] = mapped_column(Integer, default=2, nullable=False)


class ExecutionJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "execution_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN "
            "('queued','claimed','running','cancelling','completed','failed','cancelled','interrupted')",
            name="valid_status",
        ),
        Index("ix_execution_jobs_project_status", "project_id", "status"),
        Index("ix_execution_jobs_status_heartbeat", "status", "heartbeat_at"),
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    comparison_run_id: Mapped[str] = mapped_column(
        ForeignKey("comparison_runs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[str | None] = mapped_column(String(120))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    correlation_id: Mapped[str] = mapped_column(
        String(36), default=lambda: str(uuid.uuid4()), nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(String(500))


class ResponseSnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "response_snapshots"
    __table_args__ = (
        CheckConstraint("role_label IN ('high','low')", name="valid_role_label"),
        UniqueConstraint("comparison_run_id", "role_label", name="snapshot_per_role"),
    )

    comparison_run_id: Mapped[str] = mapped_column(
        ForeignKey("comparison_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    session_id: Mapped[str] = mapped_column(ForeignKey("test_sessions.id"), nullable=False)
    role_label: Mapped[str] = mapped_column(String(12), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    reason_phrase: Mapped[str] = mapped_column(String(120), nullable=False)
    response_headers: Mapped[list[list[str]]] = mapped_column(JSON, default=list, nullable=False)
    redirect_chain: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255))
    response_size: Mapped[int] = mapped_column(Integer, nullable=False)
    body_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    sanitized_body: Mapped[str | None] = mapped_column(Text)
    body_truncated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_binary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    elapsed_ms: Mapped[float] = mapped_column(Float, nullable=False)
    final_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Observation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint(
            "comparison_run_id", "request_id", "session_id", name="observation_per_execution"
        ),
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    comparison_run_id: Mapped[str] = mapped_column(
        ForeignKey("comparison_runs.id", ondelete="CASCADE"), nullable=False
    )
    request_id: Mapped[str] = mapped_column(
        ForeignKey("imported_requests.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[str] = mapped_column(ForeignKey("test_sessions.id"), nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer)
    redirect_outcome: Mapped[str] = mapped_column(String(80), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255))
    safe_headers: Mapped[list[list[str]]] = mapped_column(JSON, default=list, nullable=False)
    response_length: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    json_shape: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    top_level_json_keys: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    structural_representation: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSON)
    sanitized_body_hash: Mapped[str | None] = mapped_column(String(64))
    sanitized_excerpt: Mapped[str | None] = mapped_column(Text)
    error_category: Mapped[str | None] = mapped_column(String(80))
    auth_challenge: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    access_denied_marker: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    object_existence_marker: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    success_markers: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    body_truncated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_binary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class DiffResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "diff_results"

    comparison_run_id: Mapped[str] = mapped_column(
        ForeignKey("comparison_runs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    status_code_difference: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    redirect_difference: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    header_difference: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    body_size_difference: Mapped[int] = mapped_column(Integer, nullable=False)
    body_similarity: Mapped[float] = mapped_column(Float, nullable=False)
    json_structural_difference: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    json_value_difference: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    text_difference: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sensitive_field_overlap: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    decision_signals: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ComparisonReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "comparison_reviews"
    __table_args__ = (
        CheckConstraint(
            "disposition IN ('unreviewed','expected','false_positive','needs_review')",
            name="valid_disposition",
        ),
    )

    comparison_run_id: Mapped[str] = mapped_column(
        ForeignKey("comparison_runs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    disposition: Mapped[str] = mapped_column(String(24), default="unreviewed", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))


class Finding(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "findings"
    __table_args__ = (
        Index("ix_findings_project_status_severity", "project_id", "status", "severity"),
        UniqueConstraint("project_id", "fingerprint", name="finding_fingerprint_per_project"),
    )

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    comparison_run_id: Mapped[str] = mapped_column(ForeignKey("comparison_runs.id"))
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(24), nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    target_snapshot: Mapped[str] = mapped_column(String(2048), nullable=False)
    endpoint_snapshot: Mapped[str] = mapped_column(String(4096), nullable=False)
    expected_behaviour: Mapped[str] = mapped_column(Text, nullable=False)
    observed_behaviour: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    impact: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reproduction_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    remediation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reviewer_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    priority: Mapped[str] = mapped_column(String(24), default="normal", nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    redaction_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    limitations: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    confirmed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recurrence_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FindingEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "finding_evidence"

    finding_id: Mapped[str] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), index=True, nullable=False
    )
    snapshot_id: Mapped[str | None] = mapped_column(ForeignKey("response_snapshots.id"))
    observation_id: Mapped[str | None] = mapped_column(ForeignKey("observations.id"))
    comparison_run_id: Mapped[str | None] = mapped_column(ForeignKey("comparison_runs.id"))
    evidence_type: Mapped[str] = mapped_column(String(40), nullable=False)
    sanitized_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    excerpt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    safe_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class FindingNote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "finding_notes"

    finding_id: Mapped[str] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), index=True, nullable=False
    )
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)


class FindingStatusHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "finding_status_history"

    finding_id: Mapped[str] = mapped_column(
        ForeignKey("findings.id", ondelete="CASCADE"), index=True, nullable=False
    )
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    changed_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    note: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConcurrencyLease(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "concurrency_leases"
    __table_args__ = (
        UniqueConstraint("scope_type", "scope_id", "slot", name="lease_slot"),
        Index("ix_concurrency_leases_expires", "expires_at"),
    )

    scope_type: Mapped[str] = mapped_column(String(16), nullable=False)
    scope_id: Mapped[str] = mapped_column(String(36), nullable=False)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
    holder_id: Mapped[str] = mapped_column(String(36), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Report(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "reports"
    __table_args__ = (Index("ix_reports_project_generated", "project_id", "generated_at"),)

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    format: Mapped[str] = mapped_column(String(12), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    generated_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_hash: Mapped[str | None] = mapped_column(String(64))
    storage_path: Mapped[str | None] = mapped_column(String(1024))
    error_message: Mapped[str | None] = mapped_column(String(500))


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_user_action_created", "user_id", "action", "created_at"),
    )

    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(36))
    project_id: Mapped[str | None] = mapped_column(String(36), index=True)
    outcome: Mapped[str] = mapped_column(String(24), default="success", nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    safe_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_ip: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(64))
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
