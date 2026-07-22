"""Sync engine ORM models: server-side change log and applied-op ledger.

Implements the server half of docs/09-offline-sync.md:
- `sync_changes` is the append-only change log that powers cursor-based
  delta pull (GET /sync/changes?since=cursor). Every mutation applied
  through the sync engine (and, as feature modules adopt it, every
  server-side mutation) appends one row. The BIGINT identity `id` IS the
  cursor — monotonic, gap-tolerant.
- `sync_applied_ops` is the idempotency ledger keyed by the client-generated
  `client_id` (docs/09 section 2): replaying a batch after a lost ACK
  returns the stored result instead of double-applying.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Enum, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base import Base, utcnow


class SyncOperation(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class SyncChange(Base):
    __tablename__ = "sync_changes"
    __table_args__ = (Index("ix_sync_changes_tenant_id_id", "tenant_id", "id"),)

    # BIGINT identity: doubles as the pull cursor. SQLite variant is plain
    # INTEGER because SQLite only autoincrements INTEGER PRIMARY KEY.
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    entity_table: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    operation: Mapped[SyncOperation] = mapped_column(
        Enum(SyncOperation, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    # Snapshot of the entity after the change (empty for deletes) so pulling
    # clients can apply without a second fetch (docs/09 section 4 pull phase).
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class SyncAppliedOp(Base):
    __tablename__ = "sync_applied_ops"

    client_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    entity_table: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    # The exact per-item result originally returned, replayed verbatim on
    # duplicate submission (idempotency, docs/09 section 2).
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
