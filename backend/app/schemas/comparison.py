from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CONTROL = re.compile(r"[\x00-\x1f\x7f]")
PUBLIC_NAMES = {"*", "public", "anonymous", "unauthenticated"}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class InputData(StrictModel):
    filename: str = Field(min_length=1, max_length=160)
    content: str = Field(max_length=5 * 1024 * 1024)

    @field_validator("filename")
    @classmethod
    def safe_filename(cls, value: str) -> str:
        # Display-only: never join an uploaded name to a filesystem path.
        name = value.replace("\\", "/").rsplit("/", 1)[-1]
        name = CONTROL.sub("", name).strip()
        if not name:
            raise ValueError("A filename is required.")
        name.encode("utf-8")
        return name


class CompareRequest(StrictModel):
    before: InputData
    after: InputData


class AccessRecord(StrictModel):
    principal: str = Field(min_length=1, max_length=256)
    resource: str = Field(min_length=1, max_length=512)
    action: str = Field(min_length=1, max_length=256)
    effect: Literal["allow", "deny"]
    role: str | None = Field(default=None, min_length=1, max_length=128)
    sensitive: bool = False

    @field_validator("principal", "resource", "action", "role")
    @classmethod
    def clean_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value or CONTROL.search(value):
            raise ValueError("Labels must be nonempty and contain no control characters.")
        value.encode("utf-8")
        return value

    @field_validator("principal")
    @classmethod
    def public_alias(cls, value: str) -> str:
        return "Public" if value.casefold() in PUBLIC_NAMES else value

    @property
    def key(self) -> tuple[str, str, str]:
        return self.principal, self.resource, self.action


class InputSummary(StrictModel):
    filename: str
    format: Literal["snapshot", "har"]
    format_label: str
    record_count: int
    warnings: list[str] = Field(default_factory=list)


class Change(StrictModel):
    principal: str
    resource: str
    action: str
    before: str
    after: str
    change: Literal["gained", "lost", "changed"]
    category: str
    summary: str
    severity: Literal["critical", "high", "medium", "low", "info"]
    why: str
    recommendation: str
    evidence: dict[str, Any]


class Summary(StrictModel):
    total: int
    gained: int
    lost: int
    risky: int
    review: int
    unchanged: int


class ComparisonResult(StrictModel):
    schema_version: str = "authzdiff/comparison-v1"
    engine_version: str = "authzdiff-states/1.0 + authzdiff-rules/1.1"
    before: InputSummary
    after: InputSummary
    summary: Summary
    changes: list[Change]
    notes: list[str]
    limitations: list[str]
