from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ComparisonCreate(BaseModel):
    before_snapshot_id: str
    after_snapshot_id: str


class ComparisonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    status: str
    before_snapshot_id: str
    after_snapshot_id: str
    nodes_added: int
    nodes_removed: int
    nodes_changed: int
    nodes_unchanged: int
    relationships_added: int
    relationships_removed: int
    relationships_changed: int
    relationships_unchanged: int
    paths_added: int
    paths_removed: int
    paths_unchanged: int
    findings_added: int
    findings_resolved: int
    findings_reopened: int
    severity_changes: int
    risk_score_before: float
    risk_score_after: float
    remediation_outcomes: dict[str, object]
    error_code: str | None
    created_by: str
    created_at: datetime


class ComparisonItemPage(BaseModel):
    comparison_id: str
    category: str
    items: list[dict[str, object]]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
