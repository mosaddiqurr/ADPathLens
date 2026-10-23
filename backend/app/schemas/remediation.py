from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RemediationPlanCreate(BaseModel):
    source_snapshot_id: str
    name: str = Field(min_length=3, max_length=256)
    description: str = Field(default="", max_length=4000)


class RemediationPlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=256)
    description: str | None = Field(default=None, max_length=4000)
    status: str | None = Field(
        default=None,
        pattern="^(draft|ready|simulated|accepted|completed|cancelled)$",
    )


class RemediationPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    source_snapshot_id: str
    name: str
    description: str
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class RemediationActionCreate(BaseModel):
    finding_id: str | None = None
    action_type: str = Field(
        pattern=(
            "^(remove_relationship|disable_relationship|remove_node|disable_account|"
            "remove_group_membership|remove_local_admin|remove_password_reset|"
            "remove_gpo_control|remove_privileged_session|mark_no_longer_high_value|"
            "change_relationship_weight)$"
        )
    )
    target_node_id: str | None = None
    target_relationship_id: str | None = None
    description: str = Field(min_length=3, max_length=4000)
    proposed_change: dict[str, Any] = Field(default_factory=dict)
    priority: str = Field(default="medium", pattern="^(low|medium|high|urgent)$")
    assigned_to: str | None = None
    due_at: datetime | None = None
    expected_outcome: str = Field(default="", max_length=8000)

    @model_validator(mode="after")
    def validate_target(self) -> "RemediationActionCreate":
        node_actions = {"remove_node", "disable_account", "mark_no_longer_high_value"}
        if self.action_type in node_actions and not self.target_node_id:
            raise ValueError("target_node_id is required for this action")
        if self.action_type not in node_actions and not self.target_relationship_id:
            raise ValueError("target_relationship_id is required for this action")
        return self


class RemediationActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    remediation_plan_id: str
    finding_id: str | None
    action_type: str
    target_node_id: str | None
    target_relationship_id: str | None
    description: str
    proposed_change: dict[str, Any]
    before_value: dict[str, Any]
    priority: str
    status: str
    validation_notes: str
    assigned_to: str | None
    due_at: datetime | None
    progress_percent: int
    expected_outcome: str
    actual_outcome: str
    verification_state: str
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RemediationActionUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=3, max_length=4000)
    proposed_change: dict[str, Any] | None = None
    priority: str | None = Field(default=None, pattern="^(low|medium|high|urgent)$")
    status: str | None = Field(
        default=None,
        pattern="^(proposed|planned|in_progress|blocked|accepted|rejected|simulated|completed|verified|cancelled)$",
    )
    validation_notes: str | None = Field(default=None, max_length=4000)
    assigned_to: str | None = None
    due_at: datetime | None = None
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    expected_outcome: str | None = Field(default=None, max_length=8000)
    actual_outcome: str | None = Field(default=None, max_length=8000)
    verification_state: str | None = Field(
        default=None,
        pattern="^(not_verified|verification_unavailable|no_measurable_change|path_removed|path_shortened|path_changed|finding_resolved|finding_reopened|new_risk_introduced|verified)$",
    )
    history_note: str = Field(default="", max_length=4000)


class RemediationHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    remediation_action_id: str
    previous_status: str | None
    new_status: str
    previous_progress: int | None
    new_progress: int
    note: str
    changed_by: str
    changed_at: datetime


class RemediationPreviewResponse(BaseModel):
    plan_id: str
    simulation_only: bool = True
    source_node_count: int
    preview_node_count: int
    source_relationship_count: int
    preview_relationship_count: int
    actions_applied: int
    warnings: list[str]
