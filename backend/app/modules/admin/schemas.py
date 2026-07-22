"""Pydantic schemas for the admin module (docs/06-api-design.md section 6)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateDepartmentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=32)


class DepartmentResponse(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateCourseRequest(BaseModel):
    department_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=32)
    term: str = Field(min_length=1, max_length=32)


class CourseResponse(BaseModel):
    id: uuid.UUID
    department_id: uuid.UUID
    name: str
    code: str
    term: str
    created_at: datetime

    model_config = {"from_attributes": True}


class EnrollUserRequest(BaseModel):
    user_id: uuid.UUID
    role: str = Field(pattern="^(student|lecturer|ta)$")


class EnrollmentResponse(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    enrolled_at: datetime


class StorageUsageResponse(BaseModel):
    used_bytes: int
    quota_bytes: int
    percent_used: float


class AuditLogEntry(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    action: str
    target_type: str | None
    target_id: uuid.UUID | None
    metadata: dict
    ip_address: str | None
    created_at: datetime


class EngagementResponse(BaseModel):
    users: int
    resources: int
    messages: int
    submissions: int
