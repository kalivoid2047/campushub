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
    # True when at least one kind (resource/announcement/message) hit its
    # per-kind cap and was truncated — there may be more matches than
    # shown; the client should prompt the user to narrow the query rather
    # than silently implying `hits` is the complete result set.
    truncated: bool = False
