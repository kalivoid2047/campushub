"""Pydantic schemas for the resources module (docs/06-api-design.md section 6)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateModuleRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    position: int = Field(default=0, ge=0)


class ModuleResponse(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    position: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ResourceVersionResponse(BaseModel):
    id: uuid.UUID
    version_number: int
    size_bytes: int
    checksum: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ResourceResponse(BaseModel):
    id: uuid.UUID
    module_id: uuid.UUID
    title: str
    type: str
    download_count: int
    current_version: ResourceVersionResponse | None
    created_at: datetime
    updated_at: datetime


class DownloadResponse(BaseModel):
    """Either a presigned URL (S3 backend) or an inline indicator that the
    client should stream from the /content endpoint (local backend)."""

    download_url: str | None
    inline: bool
    size_bytes: int
    checksum: str
