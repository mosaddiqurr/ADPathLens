from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def uuid_string() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class Role(StrEnum):
    ADMINISTRATOR = "administrator"
    ANALYST = "analyst"
    VIEWER = "viewer"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(256))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(32), default=Role.VIEWER.value, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String(128))
    created_ip: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    user: Mapped[User] = relationship()


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    name: Mapped[str] = mapped_column(String(256), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class WorkspaceMembership(Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_workspace_membership"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(32), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(256), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(32), index=True)
    source_filename: Mapped[str | None] = mapped_column(String(256))
    authorization_confirmed: Mapped[bool] = mapped_column(Boolean)
    authorization_confirmed_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    authorization_confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    import_status: Mapped[str] = mapped_column(String(32), default="complete", index=True)
    validation_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    node_count: Mapped[int] = mapped_column(Integer, default=0)
    relationship_count: Mapped[int] = mapped_column(Integer, default=0)
    data_hash: Mapped[str] = mapped_column(String(64), index=True)
    schema_version: Mapped[str] = mapped_column(String(16), default="1.0")
    progress_percent: Mapped[int] = mapped_column(Integer, default=100)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class ImportedFile(Base):
    __tablename__ = "imported_files"
    __table_args__ = (UniqueConstraint("dataset_id", "content_hash", "logical_name", name="uq_import_file"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    logical_name: Mapped[str] = mapped_column(String(256))
    original_name: Mapped[str] = mapped_column(String(256))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    media_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ImportIssue(Base):
    __tablename__ = "import_issues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    level: Mapped[str] = mapped_column(String(32), index=True)
    code: Mapped[str] = mapped_column(String(128), index=True)
    message: Mapped[str] = mapped_column(String(1000))
    location: Mapped[str | None] = mapped_column(String(512))
    acknowledged_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class GraphSnapshot(Base):
    __tablename__ = "graph_snapshots"
    __table_args__ = (UniqueConstraint("project_id", "version", name="uq_snapshot_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    dataset_id: Mapped[str | None] = mapped_column(ForeignKey("datasets.id", ondelete="SET NULL"), index=True)
    parent_snapshot_id: Mapped[str | None] = mapped_column(ForeignKey("graph_snapshots.id", ondelete="SET NULL"))
    remediation_plan_id: Mapped[str | None] = mapped_column(String(36))
    name: Mapped[str] = mapped_column(String(256))
    snapshot_type: Mapped[str] = mapped_column(String(32), default="imported")
    description: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class DirectoryNode(Base):
    __tablename__ = "directory_nodes"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "external_id", name="uq_node_external_snapshot"),
        Index("ix_node_snapshot_type_name", "snapshot_id", "node_type", "name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("graph_snapshots.id", ondelete="CASCADE"), index=True)
    source_file_id: Mapped[str | None] = mapped_column(ForeignKey("imported_files.id", ondelete="SET NULL"), index=True)
    external_id: Mapped[str] = mapped_column(String(256), index=True)
    node_type: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(256), index=True)
    display_name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    domain_name: Mapped[str | None] = mapped_column(String(256), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    high_value: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    privileged: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    risk_level: Mapped[str] = mapped_column(String(32), default="informational")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DirectoryRelationship(Base):
    __tablename__ = "directory_relationships"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "external_id", name="uq_rel_external_snapshot"),
        Index("ix_rel_snapshot_type", "snapshot_id", "relationship_type"),
        Index("ix_rel_snapshot_endpoints", "snapshot_id", "source_node_id", "target_node_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("graph_snapshots.id", ondelete="CASCADE"), index=True)
    source_file_id: Mapped[str | None] = mapped_column(ForeignKey("imported_files.id", ondelete="SET NULL"), index=True)
    external_id: Mapped[str] = mapped_column(String(256), index=True)
    source_node_id: Mapped[str] = mapped_column(ForeignKey("directory_nodes.id", ondelete="CASCADE"), index=True)
    target_node_id: Mapped[str] = mapped_column(ForeignKey("directory_nodes.id", ondelete="CASCADE"), index=True)
    relationship_type: Mapped[str] = mapped_column(String(64), index=True)
    direction: Mapped[str] = mapped_column(String(32), default="forward")
    inherited: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    risk_weight: Mapped[float] = mapped_column(Float, default=5.0)
    confidence: Mapped[str] = mapped_column(String(32), default="high")
    description: Mapped[str] = mapped_column(Text, default="")
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(128), index=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), index=True)
    summary: Mapped[str] = mapped_column(String(1000))
    source_ip: Mapped[str | None] = mapped_column(String(64))
    context_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class PathAnalysis(Base):
    __tablename__ = "path_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("graph_snapshots.id", ondelete="CASCADE"), index=True)
    start_node_id: Mapped[str] = mapped_column(ForeignKey("directory_nodes.id"), index=True)
    target_node_id: Mapped[str | None] = mapped_column(ForeignKey("directory_nodes.id"))
    algorithm: Mapped[str] = mapped_column(String(32), index=True)
    maximum_depth: Mapped[int] = mapped_column(Integer, default=12)
    path_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="running", index=True)
    request_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    catalog_version: Mapped[str] = mapped_column(String(16), default="1.0")
    initiated_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    failure_code: Mapped[str | None] = mapped_column(String(64))


class PrivilegePath(Base):
    __tablename__ = "privilege_paths"
    __table_args__ = (UniqueConstraint("path_analysis_id", "path_signature", name="uq_analysis_path_signature"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    path_analysis_id: Mapped[str] = mapped_column(ForeignKey("path_analyses.id", ondelete="CASCADE"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    path_signature: Mapped[str] = mapped_column(String(64))
    total_weight: Mapped[float] = mapped_column(Float)
    hop_count: Mapped[int] = mapped_column(Integer)
    risk_score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[str] = mapped_column(String(32))
    explanation: Mapped[str] = mapped_column(Text)
    limitations: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PrivilegePathStep(Base):
    __tablename__ = "privilege_path_steps"
    __table_args__ = (UniqueConstraint("privilege_path_id", "position", name="uq_path_step_position"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    privilege_path_id: Mapped[str] = mapped_column(ForeignKey("privilege_paths.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    source_node_id: Mapped[str] = mapped_column(ForeignKey("directory_nodes.id"))
    relationship_id: Mapped[str] = mapped_column(ForeignKey("directory_relationships.id"))
    target_node_id: Mapped[str] = mapped_column(ForeignKey("directory_nodes.id"))
    step_explanation: Mapped[str] = mapped_column(Text)
    remediation_summary: Mapped[str] = mapped_column(Text)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RiskFinding(Base):
    __tablename__ = "risk_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("graph_snapshots.id", ondelete="CASCADE"), index=True)
    node_id: Mapped[str | None] = mapped_column(ForeignKey("directory_nodes.id"))
    relationship_id: Mapped[str | None] = mapped_column(ForeignKey("directory_relationships.id"))
    privilege_path_id: Mapped[str | None] = mapped_column(ForeignKey("privilege_paths.id"))
    rule_id: Mapped[str | None] = mapped_column(String(64), index=True)
    rule_version: Mapped[str] = mapped_column(String(16), default="1.0")
    title: Mapped[str] = mapped_column(String(256), index=True)
    category: Mapped[str] = mapped_column(String(128), index=True)
    severity: Mapped[str] = mapped_column(String(32), index=True)
    confidence: Mapped[str] = mapped_column(String(32), index=True)
    internal_score: Mapped[float] = mapped_column(Float)
    priority: Mapped[str] = mapped_column(String(32), default="medium", index=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    description: Mapped[str] = mapped_column(Text)
    technical_explanation: Mapped[str] = mapped_column(Text, default="")
    impact: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    contributing_signals: Mapped[list[str]] = mapped_column(JSON, default=list)
    reducing_signals: Mapped[list[str]] = mapped_column(JSON, default=list)
    remediation: Mapped[str] = mapped_column(Text)
    validation_steps: Mapped[list[str]] = mapped_column(JSON, default=list)
    limitations: Mapped[str] = mapped_column(Text, default="")
    reviewer_notes: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    record_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class FindingStatusHistory(Base):
    __tablename__ = "finding_status_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    finding_id: Mapped[str] = mapped_column(ForeignKey("risk_findings.id", ondelete="CASCADE"), index=True)
    previous_status: Mapped[str | None] = mapped_column(String(32))
    new_status: Mapped[str] = mapped_column(String(32), index=True)
    note: Mapped[str] = mapped_column(Text, default="")
    changed_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FindingNode(Base):
    __tablename__ = "finding_nodes"
    finding_id: Mapped[str] = mapped_column(ForeignKey("risk_findings.id", ondelete="CASCADE"), primary_key=True)
    node_id: Mapped[str] = mapped_column(ForeignKey("directory_nodes.id", ondelete="CASCADE"), primary_key=True)


class FindingRelationship(Base):
    __tablename__ = "finding_relationships"
    finding_id: Mapped[str] = mapped_column(ForeignKey("risk_findings.id", ondelete="CASCADE"), primary_key=True)
    relationship_id: Mapped[str] = mapped_column(
        ForeignKey("directory_relationships.id", ondelete="CASCADE"), primary_key=True
    )


class FindingPath(Base):
    __tablename__ = "finding_paths"
    finding_id: Mapped[str] = mapped_column(ForeignKey("risk_findings.id", ondelete="CASCADE"), primary_key=True)
    path_id: Mapped[str] = mapped_column(ForeignKey("privilege_paths.id", ondelete="CASCADE"), primary_key=True)


class RemediationPlan(Base):
    __tablename__ = "remediation_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    source_snapshot_id: Mapped[str] = mapped_column(ForeignKey("graph_snapshots.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class RemediationAction(Base):
    __tablename__ = "remediation_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    remediation_plan_id: Mapped[str] = mapped_column(ForeignKey("remediation_plans.id", ondelete="CASCADE"), index=True)
    finding_id: Mapped[str | None] = mapped_column(ForeignKey("risk_findings.id"))
    action_type: Mapped[str] = mapped_column(String(64), index=True)
    target_node_id: Mapped[str | None] = mapped_column(ForeignKey("directory_nodes.id"))
    target_relationship_id: Mapped[str | None] = mapped_column(ForeignKey("directory_relationships.id"))
    description: Mapped[str] = mapped_column(Text)
    proposed_change: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    before_value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    priority: Mapped[str] = mapped_column(String(32), default="medium")
    status: Mapped[str] = mapped_column(String(32), default="proposed")
    validation_notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class SnapshotComparison(Base):
    __tablename__ = "snapshot_comparisons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    before_snapshot_id: Mapped[str] = mapped_column(ForeignKey("graph_snapshots.id"))
    after_snapshot_id: Mapped[str] = mapped_column(ForeignKey("graph_snapshots.id"))
    nodes_added: Mapped[int] = mapped_column(Integer, default=0)
    nodes_removed: Mapped[int] = mapped_column(Integer, default=0)
    nodes_changed: Mapped[int] = mapped_column(Integer, default=0)
    relationships_added: Mapped[int] = mapped_column(Integer, default=0)
    relationships_removed: Mapped[int] = mapped_column(Integer, default=0)
    relationships_changed: Mapped[int] = mapped_column(Integer, default=0)
    paths_added: Mapped[int] = mapped_column(Integer, default=0)
    paths_removed: Mapped[int] = mapped_column(Integer, default=0)
    risk_score_before: Mapped[float] = mapped_column(Float, default=0)
    risk_score_after: Mapped[float] = mapped_column(Float, default=0)
    diff_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    snapshot_id: Mapped[str | None] = mapped_column(ForeignKey("graph_snapshots.id"))
    comparison_id: Mapped[str | None] = mapped_column(ForeignKey("snapshot_comparisons.id"))
    report_type: Mapped[str] = mapped_column(String(64))
    format: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(32), default="complete")
    content_version: Mapped[str] = mapped_column(String(16), default="1.0")
    mime_type: Mapped[str] = mapped_column(String(128))
    generated_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    file_name: Mapped[str] = mapped_column(String(256))
    file_hash: Mapped[str] = mapped_column(String(64))
    storage_path: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(64))


class RiskRuleConfiguration(Base):
    __tablename__ = "risk_rule_configurations"
    __table_args__ = (UniqueConstraint("rule_id", "version", name="uq_rule_config_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    rule_id: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    configuration_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    changed_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AnalystNote(Base):
    __tablename__ = "analyst_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    body: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ApplicationSetting(Base):
    __tablename__ = "application_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    changed_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
