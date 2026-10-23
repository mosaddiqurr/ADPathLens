from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GraphSummaryResponse(BaseModel):
    snapshot_id: str
    node_count: int
    relationship_count: int
    high_value_count: int
    privileged_count: int
    nodes_by_type: dict[str, int]
    relationships_by_type: dict[str, int]


class NodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    snapshot_id: str
    external_id: str
    node_type: str
    name: str
    display_name: str
    description: str
    domain_name: str | None
    enabled: bool
    high_value: bool
    privileged: bool
    risk_level: str
    metadata_json: dict[str, Any]
    stable_fingerprint: str
    first_seen_at: datetime
    last_seen_at: datetime


class RelationshipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    snapshot_id: str
    external_id: str
    source_node_id: str
    target_node_id: str
    relationship_type: str
    direction: str
    inherited: bool
    active: bool
    risk_weight: float
    confidence: str
    description: str
    evidence_json: dict[str, Any]
    metadata_json: dict[str, Any]
    stable_fingerprint: str
    first_seen_at: datetime
    last_seen_at: datetime


class NodeUpdate(BaseModel):
    high_value: bool | None = None
    description: str | None = Field(default=None, max_length=4000)
    risk_level: str | None = Field(default=None, pattern="^(informational|low|medium|high|critical)$")


class RelationshipUpdate(BaseModel):
    active: bool | None = None
    confidence: str | None = Field(default=None, pattern="^(high|medium|low|unknown)$")
    risk_weight: float | None = Field(default=None, ge=0.1, le=100)
    description: str | None = Field(default=None, max_length=4000)


class PageResponse(BaseModel):
    items: list[dict[str, Any]]
    page: int
    page_size: int
    total: int


class AnalysisRequest(BaseModel):
    start_node_id: str
    target_node_id: str | None = None
    target_kind: Literal["specific", "high_value", "privileged"] = "specific"
    algorithm: Literal["shortest_hops", "lowest_cost", "top_paths", "reverse_reachability"]
    maximum_depth: int = Field(default=12, ge=1, le=12)
    maximum_paths: int = Field(default=10, ge=1, le=25)
    relationship_types: list[str] = Field(default_factory=list, max_length=60)
    excluded_relationship_types: list[str] = Field(default_factory=list, max_length=60)
    source_node_types: list[str] = Field(default_factory=list, max_length=20)
    target_node_types: list[str] = Field(default_factory=list, max_length=20)
    minimum_confidence: Literal["unknown", "low", "medium", "high"] = "low"
    include_disabled: bool = False

    @model_validator(mode="after")
    def validate_target(self) -> "AnalysisRequest":
        if self.target_kind == "specific" and not self.target_node_id:
            raise ValueError("target_node_id is required for a specific target")
        if self.algorithm == "reverse_reachability" and not self.target_node_id:
            raise ValueError("target_node_id is required for reverse reachability")
        overlap = set(self.relationship_types) & set(self.excluded_relationship_types)
        if overlap:
            raise ValueError("relationship types cannot be both allowed and excluded")
        return self


class PathStepResponse(BaseModel):
    position: int
    source_node_id: str
    source_name: str
    source_type: str
    relationship_id: str
    relationship_type: str
    target_node_id: str
    target_name: str
    target_type: str
    step_explanation: str
    remediation_summary: str
    confidence: str
    risk_weight: float
    evidence: dict[str, Any]


class PathResponse(BaseModel):
    id: str
    rank: int
    total_weight: float
    hop_count: int
    risk_score: float
    severity: str
    scoring_components: dict[str, Any]
    confidence: str
    explanation: str
    limitations: str
    steps: list[PathStepResponse]


class AnalysisResponse(BaseModel):
    request_parameters: dict[str, Any] = Field(default_factory=dict)
    id: str
    project_id: str
    snapshot_id: str
    start_node_id: str
    target_node_id: str | None
    algorithm: str
    maximum_depth: int
    path_count: int
    status: str
    started_at: datetime
    completed_at: datetime | None
    truncated: bool
    paths: list[PathResponse]
