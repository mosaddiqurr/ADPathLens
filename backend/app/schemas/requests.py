from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.core import HeaderPair


class RequestCollectionCreate(BaseModel):
    target_id: str
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=10_000)


class RequestCollectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    target_id: str
    name: str
    description: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class QueryPair(BaseModel):
    name: str = Field(max_length=512)
    value: str = Field(max_length=8192)


class ManualRequestCreate(BaseModel):
    collection_id: str
    target_id: str
    name: str = Field(min_length=1, max_length=160)
    method: Literal["GET", "HEAD", "OPTIONS", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    path: str = Field(min_length=1, max_length=4096)
    query_parameters: list[QueryPair] = Field(default_factory=list, max_length=100)
    headers: list[HeaderPair] = Field(default_factory=list, max_length=50)
    body: str = Field(default="", max_length=1_048_576)
    content_type: str | None = Field(default=None, max_length=255)
    approved_state_change: bool = False
    expected_markers: list[str] = Field(default_factory=list, max_length=20)
    tags: list[str] = Field(default_factory=list, max_length=20)
    sensitivity: Literal["public", "internal", "confidential", "restricted"] = "internal"

    @field_validator("expected_markers", "tags")
    @classmethod
    def bounded_strings(cls, values: list[str]) -> list[str]:
        if any(len(value) > 100 for value in values):
            raise ValueError("Marker and tag values are limited to 100 characters.")
        return sorted(set(values))


class RawRequestImport(BaseModel):
    collection_id: str
    target_id: str
    name: str = Field(min_length=1, max_length=160)
    raw_request: str = Field(min_length=1, max_length=1_048_576)
    approved_state_change: bool = False


class CurlRequestImport(BaseModel):
    collection_id: str
    target_id: str
    name: str = Field(min_length=1, max_length=160)
    command: str = Field(min_length=1, max_length=65_536)
    approved_state_change: bool = False


class ImportedRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    collection_id: str | None
    target_id: str
    name: str
    import_type: str
    method: str
    path: str
    query_parameters: list[list[str]]
    sanitized_headers: list[list[str]]
    content_type: str | None
    body_template: str
    body_hash: str
    is_state_changing: bool
    approved_state_change: bool
    expected_markers: list[str]
    tags: list[str]
    sensitivity: str
    created_at: datetime
    updated_at: datetime


class HarCandidate(BaseModel):
    index: int
    method: str
    path: str
    content_type: str | None
    has_secrets: bool
    is_state_changing: bool
