"""Pydantic schemas for the sync API (docs/06-api-design.md section 6, Sync).

POST /sync/batch  — push queued client mutations (idempotent per client_id)
GET  /sync/changes — cursor-based delta pull of server-side changes
"""

import enum
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SyncOperationIn(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class SyncItemStatus(str, enum.Enum):
    APPLIED = "applied"
    CONFLICT = "conflict"
    ERROR = "error"


class SyncBatchItem(BaseModel):
    client_id: uuid.UUID  # idempotency key, generated client-side (docs/09 s2)
    entity_table: str = Field(min_length=1, max_length=64)
    entity_id: uuid.UUID  # client-generated UUID (docs/05 s1)
    operation: SyncOperationIn
    payload: dict = Field(default_factory=dict)
    # The server version the client last saw; None for creates. A mismatch
    # with the current server version is a conflict (docs/09 s3).
    base_version: int | None = None


class SyncBatchRequest(BaseModel):
    items: list[SyncBatchItem] = Field(min_length=1, max_length=200)


class SyncItemResult(BaseModel):
    client_id: uuid.UUID
    status: SyncItemStatus
    entity_id: uuid.UUID
    new_version: int | None = None
    # On conflict: the server's current state so the client can reconcile
    # without an extra round trip.
    server_version: int | None = None
    server_payload: dict | None = None
    error_code: str | None = None
    error_message: str | None = None


class SyncBatchResponse(BaseModel):
    results: list[SyncItemResult]


class SyncChangeOut(BaseModel):
    cursor: int
    entity_table: str
    entity_id: uuid.UUID
    operation: SyncOperationIn
    payload: dict
    version: int
    changed_at: datetime


class SyncPullResponse(BaseModel):
    changes: list[SyncChangeOut]
    next_cursor: int
    has_more: bool
