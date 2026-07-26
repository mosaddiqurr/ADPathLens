from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.entities import Role


class SetupRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=256)
    password: str = Field(min_length=12, max_length=1024)
    authorization_confirmed: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=256)
    password: str = Field(min_length=12, max_length=1024)
    role: Role


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=256)
    role: Role | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class AuthResponse(BaseModel):
    user: UserResponse
    csrf_token: str


class SetupStatus(BaseModel):
    setup_required: bool
