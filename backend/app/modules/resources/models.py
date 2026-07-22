"""Resources ORM models: course modules, resources, resource versions.

Schema per docs/05-database-design.md sections 3.7-3.9. Resources are
soft-deleted (deleted_at) so offline clients holding cached copies are not
surprised by hard-vanishing rows (docs/09 section 8).
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ResourceType(str, enum.Enum):
    DOCUMENT = "document"
    SLIDE = "slide"
    VIDEO = "video"
    LINK = "link"


class CourseModule(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    """A content section within a course (docs/05 section 3.7; named
    CourseModule in code to avoid clashing with Python's 'module')."""

    __tablename__ = "modules"
    __table_args__ = (Index("ix_modules_course", "course_id", "position"),)

    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    resources: Mapped[list["Resource"]] = relationship(back_populates="module")


class Resource(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "resources"
    __table_args__ = (Index("ix_resources_module_deleted", "module_id", "deleted_at"),)

    module_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("modules.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[ResourceType] = mapped_column(
        Enum(ResourceType, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    download_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    module: Mapped[CourseModule] = relationship(back_populates="resources")
    versions: Mapped[list["ResourceVersion"]] = relationship(
        back_populates="resource", cascade="all, delete-orphan"
    )


class ResourceVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "resource_versions"
    __table_args__ = (
        UniqueConstraint("resource_id", "version_number", name="uq_resource_versions"),
    )

    resource_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("resources.id", ondelete="CASCADE"), nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)  # sha256 hex
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)

    resource: Mapped[Resource] = relationship(back_populates="versions")
