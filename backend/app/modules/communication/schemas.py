"""Pydantic schemas for the communication module (docs/06 section 6)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ChannelResponse(BaseModel):
    id: uuid.UUID
    type: str
    course_id: uuid.UUID | None
    name: str | None
    created_at: datetime


class CreateDmRequest(BaseModel):
    recipient_id: uuid.UUID


class SendMessageRequest(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)
    attachments: list[dict] = Field(default_factory=list, max_length=10)
    client_id: uuid.UUID | None = None  # offline dedupe key


class MessageResponse(BaseModel):
    id: uuid.UUID
    channel_id: uuid.UUID
    sender_id: uuid.UUID
    body: str
    attachments: list
    created_at: datetime
    edited_at: datetime | None

    model_config = {"from_attributes": True}


class MessagePage(BaseModel):
    messages: list[MessageResponse]
    next_cursor: str | None  # ISO timestamp of the oldest returned message
    has_more: bool


class CreateAnnouncementRequest(BaseModel):
    scope: str = Field(pattern="^(institution|department|course)$")
    scope_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=20_000)


class AnnouncementResponse(BaseModel):
    id: uuid.UUID
    scope: str
    scope_id: uuid.UUID | None
    title: str
    body: str
    published_by: uuid.UUID
    created_at: datetime
