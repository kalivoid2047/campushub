"""Pydantic request/response schemas for the IAM module.

API contract per docs/06-api-design.md §2 (auth flow) and §6 (tenancy/users).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    tenant_slug: str = Field(min_length=1, max_length=63)


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expiry


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: EmailStr
    full_name: str
    status: str
    roles: list[str]

    model_config = {"from_attributes": True}


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)
    role: str = Field(pattern="^(student|lecturer|dept_admin|institution_admin)$")


class CreateTenantRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=63, pattern="^[a-z0-9][a-z0-9-]*$")
    admin_email: EmailStr
    admin_password: str = Field(min_length=8, max_length=128)
    admin_full_name: str = Field(min_length=1, max_length=200)


class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
