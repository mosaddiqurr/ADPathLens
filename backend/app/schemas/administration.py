from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RiskRuleConfigurationCreate(BaseModel):
    enabled: bool = True
    relationship_weights: dict[str, float] = Field(default_factory=dict)
    scoring_overrides: dict[str, float] = Field(default_factory=dict)

    @field_validator("relationship_weights")
    @classmethod
    def validate_weights(cls, value: dict[str, float]) -> dict[str, float]:
        if len(value) > 100 or any(weight < 0.1 or weight > 100 for weight in value.values()):
            raise ValueError("relationship weights must be between 0.1 and 100")
        return value


class RiskRuleConfigurationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    rule_id: str
    version: int
    enabled: bool
    configuration_json: dict[str, Any]
    changed_by: str
    created_at: datetime


class SettingUpdate(BaseModel):
    value: int | bool | str


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str | None
    action: str
    entity_type: str
    entity_id: str | None
    summary: str
    source_ip: str | None
    context_json: dict[str, Any]
    created_at: datetime
