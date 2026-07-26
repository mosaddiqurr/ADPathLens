from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReportCreate(BaseModel):
    snapshot_id: str | None = None
    comparison_id: str | None = None
    report_type: str = Field(default="findings", pattern="^(findings|executive|comparison)$")
    format: str = Field(pattern="^(html|pdf|json|csv)$")

    @model_validator(mode="after")
    def validate_source(self) -> "ReportCreate":
        if not self.snapshot_id and not self.comparison_id:
            raise ValueError("snapshot_id or comparison_id is required")
        if self.report_type == "comparison" and not self.comparison_id:
            raise ValueError("comparison_id is required for comparison reports")
        return self


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    snapshot_id: str | None
    comparison_id: str | None
    report_type: str
    format: str
    status: str
    content_version: str
    mime_type: str
    generated_by: str
    generated_at: datetime
    file_name: str
    file_hash: str
    size_bytes: int
    error_code: str | None
