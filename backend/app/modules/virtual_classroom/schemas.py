"""Pydantic schemas for the virtual classroom module (docs/06 section 6)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None


class SessionResponse(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    status: str
    scheduled_start: datetime | None
    scheduled_end: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None
    created_by: uuid.UUID


class JoinResponse(BaseModel):
    session_id: uuid.UUID
    joined_at: datetime
    # Media-plane connection details land with the WebRTC milestone
    # (docs/10); None until then.
    signaling_url: str | None = None
    sfu_token: str | None = None


class RecordingResponse(BaseModel):
    id: uuid.UUID
    status: str
    duration_seconds: int
    size_bytes: int
    created_at: datetime
    # A time-limited direct download link once the recording is available
    # (docs/04 section 10 presigned-URL pattern); None while still processing
    # or if the storage backend can't presign.
    download_url: str | None = None
