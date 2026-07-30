from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FindingCreate(BaseModel):
    comparison_run_id: str
    title: str = Field(min_length=1, max_length=240)
    category: str = Field(min_length=1, max_length=80)
    severity: Literal["informational", "low", "medium", "high", "critical"]
    confidence: Literal["low", "medium", "high"]
    description: str = Field(min_length=1, max_length=20_000)
    impact: str = Field(default="", max_length=10_000)
    remediation: str = Field(default="", max_length=10_000)
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    tags: list[str] = Field(default_factory=list, max_length=20)


class FindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    comparison_run_id: str | None
    fingerprint: str
    title: str
    category: str
    severity: str
    confidence: str
    status: str
    target_snapshot: str
    endpoint_snapshot: str
    expected_behaviour: str
    observed_behaviour: str
    description: str
    impact: str
    reproduction_summary: str
    remediation: str
    reviewer_notes: str
    priority: str
    tags: list[str]
    redaction_summary: str
    limitations: str
    first_seen_at: datetime
    last_seen_at: datetime
    recurrence_count: int
    created_at: datetime
    updated_at: datetime


class FindingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    severity: Literal["informational", "low", "medium", "high", "critical"] | None = None
    confidence: Literal["low", "medium", "high"] | None = None
    status: (
        Literal[
            "candidate",
            "open",
            "triaged",
            "in_progress",
            "needs_review",
            "confirmed",
            "false_positive",
            "accepted_risk",
            "resolved",
            "reopened",
        ]
        | None
    ) = None
    description: str | None = Field(default=None, max_length=20_000)
    impact: str | None = Field(default=None, max_length=10_000)
    remediation: str | None = Field(default=None, max_length=10_000)
    reviewer_notes: str | None = Field(default=None, max_length=10_000)
    priority: Literal["low", "normal", "high", "urgent"] | None = None
    tags: list[str] | None = Field(default=None, max_length=20)
    status_note: str = Field(default="", max_length=500)


class FindingNoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)


class FindingNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    finding_id: str
    author_id: str
    body: str
    created_at: datetime
    updated_at: datetime


class FindingStatusHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    finding_id: str
    from_status: str | None
    to_status: str
    changed_by: str
    note: str
    created_at: datetime


class FindingEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    finding_id: str
    observation_id: str | None
    comparison_run_id: str | None
    evidence_type: str
    sanitized_excerpt: str
    excerpt_hash: str
    safe_metadata: dict[str, object]
    created_at: datetime


class ReportCreate(BaseModel):
    format: Literal["json", "csv", "html", "pdf"]


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    format: str
    status: str
    generated_by: str
    generated_at: datetime
    file_name: str
    content_hash: str
    file_hash: str | None
    error_message: str | None
