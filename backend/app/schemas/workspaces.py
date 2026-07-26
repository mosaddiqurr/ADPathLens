from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=256)
    description: str = Field(default="", max_length=4000)


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class MembershipCreate(BaseModel):
    user_id: str
    role: str = Field(pattern="^(administrator|analyst|viewer)$")


class MembershipUpdate(BaseModel):
    role: str = Field(pattern="^(administrator|analyst|viewer)$")


class MembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    user_id: str
    role: str
    created_by: str
    created_at: datetime
