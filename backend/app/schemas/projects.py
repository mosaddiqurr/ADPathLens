from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    workspace_id: str
    name: str = Field(min_length=2, max_length=256)
    description: str = Field(default="", max_length=4000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=256)
    description: str | None = Field(default=None, max_length=4000)
    status: str | None = Field(default=None, pattern="^(active|archived)$")


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    name: str
    description: str
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class DemoImportRequest(BaseModel):
    demo: str = Field(default="small", pattern="^(small|medium|before|after)$")
    authorization_confirmed: bool


class ValidationResponse(BaseModel):
    valid: bool
    digest: str
    node_count: int
    relationship_count: int
    messages: list[dict[str, Any]]


class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    name: str
    source_type: str
    import_status: str
    progress_percent: int
    node_count: int
    relationship_count: int
    data_hash: str
    created_at: datetime


class ImportProgressResponse(BaseModel):
    id: str
    status: str
    progress_percent: int
    node_count: int
    relationship_count: int
    validation_summary: dict[str, Any]


class SnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    dataset_id: str | None
    parent_snapshot_id: str | None
    name: str
    snapshot_type: str
    version: int
    revision: int
    created_at: datetime
