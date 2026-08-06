"""Declarative base and shared model mixins.

Implements the cross-cutting column conventions from docs/05-database-design.md §1:
UUID PKs (client-generatable for offline creation), created_at/updated_at on all
tables, version counters on mutation-tracked tables, and tenant_id on every
tenant-scoped table (RLS enforcement is applied in the Alembic migration,
Postgres-only).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class VersionMixin:
    """Optimistic-concurrency / sync-conflict detection counter (docs/09-offline-sync.md §3)."""

    version: Mapped[int] = mapped_column(Integer, default=1)


class TenantScopedMixin:
    """Every tenant-scoped table carries tenant_id (docs/05-database-design.md §1)."""

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True
    )
