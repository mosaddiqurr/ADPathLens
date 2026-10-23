from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    snapshot_id: str
    node_id: str | None
    relationship_id: str | None
    privilege_path_id: str | None
    rule_id: str | None
    rule_version: str
    title: str
    category: str
    severity: str
    confidence: str
    internal_score: float
    priority: str
    status: str
    description: str
    technical_explanation: str
    impact: str
    evidence: dict[str, Any]
    contributing_signals: list[str]
    reducing_signals: list[str]
    remediation: str
    validation_steps: list[str]
    limitations: str
    reviewer_notes: str
    stable_fingerprint: str
    first_seen_at: datetime
    last_seen_at: datetime
    recurrence_count: int
    created_by: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class FindingCreate(BaseModel):
    snapshot_id: str
    title: str = Field(min_length=3, max_length=256)
    category: str = Field(min_length=2, max_length=128)
    severity: str = Field(pattern="^(informational|low|medium|high|critical)$")
    confidence: str = Field(pattern="^(unknown|low|medium|high)$")
    description: str = Field(min_length=3, max_length=8000)
    technical_explanation: str = Field(default="", max_length=8000)
    impact: str = Field(min_length=3, max_length=8000)
    remediation: str = Field(min_length=3, max_length=8000)
    validation_steps: list[str] = Field(default_factory=list, max_length=20)
    limitations: str = Field(default="", max_length=4000)
    node_id: str | None = None
    relationship_id: str | None = None
    privilege_path_id: str | None = None


class FindingUpdate(BaseModel):
    status: str | None = Field(
        default=None,
        pattern=(
            "^(draft|open|confirmed|acknowledged|mitigated|accepted_risk|false_positive|"
            "triaged|in_progress|reopened|planned_remediation|resolved|retest_required|closed)$"
        ),
    )
    priority: str | None = Field(default=None, pattern="^(low|medium|high|urgent)$")
    severity: str | None = Field(default=None, pattern="^(informational|low|medium|high|critical)$")
    reviewer_notes: str | None = Field(default=None, max_length=8000)
    status_note: str = Field(default="", max_length=4000)


class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=8000)


class NoteUpdate(BaseModel):
    body: str = Field(min_length=1, max_length=8000)


class NoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    entity_type: str
    entity_id: str
    body: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class RiskSummaryResponse(BaseModel):
    snapshot_id: str
    total: int
    by_severity: dict[str, int]
    by_status: dict[str, int]
    by_category: dict[str, int]


class FindingHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    finding_id: str
    previous_status: str | None
    new_status: str
    note: str
    changed_by: str
    changed_at: datetime
