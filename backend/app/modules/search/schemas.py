"""Pydantic schemas for the search module (docs/06 section 6)."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class SearchHit(BaseModel):
    kind: str  # resource | announcement | message
    id: uuid.UUID
    title: str
    snippet: str
    context_id: uuid.UUID | None  # module/channel id for navigation
    created_at: datetime


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]
