"""IAM/Tenancy ORM models: tenants, users, roles, user_roles, refresh_tokens.

Schema per docs/05-database-design.md §3.1–3.3. Refresh tokens are stored
hashed and revocable per docs/08-security-design.md §2.
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
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base import (
    Base,
    TenantScopedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class TenantStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PROVISIONING = "provisioning"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    PENDING = "pending"


class RoleName(str, enum.Enum):
    STUDENT = "student"
    LECTURER = "lecturer"
    DEPT_ADMIN = "dept_admin"
    INSTITUTION_ADMIN = "institution_admin"
    SUPER_ADMIN = "super_admin"


class Tenant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(String(63), unique=True, nullable=False)
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, values_callable=lambda e: [m.value for m in e]),
        default=TenantStatus.PROVISIONING,
        nullable=False,
    )
    storage_quota_bytes: Mapped[int] = mapped_column(
        BigInteger, default=10 * 1024**3, nullable=False
    )

    users: Mapped[list["User"]] = relationship(back_populates="tenant")


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),)

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, values_callable=lambda e: [m.value for m in e]),
        default=UserStatus.ACTIVE,
        nullable=False,
    )
    offline_token_hash: Mapped[str | None] = mapped_column(Text, nullable=True)

    tenant: Mapped[Tenant] = relationship(back_populates="users")
    roles: Mapped[list["UserRole"]] = relationship(back_populates="user")


class Role(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),)

    # Nullable tenant_id: NULL = system-wide role (docs/05-database-design.md §3.3).
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    name: Mapped[RoleName] = mapped_column(
        Enum(RoleName, values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    permissions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class UserRole(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "role_id",
            "scope_department_id",
            "scope_course_id",
            name="uq_user_roles_grant",
        ),
        Index("ix_user_roles_user", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    # Optional scoping of a grant to a department or course (docs/05 §3.3).
    scope_department_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    scope_course_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)

    user: Mapped[User] = relationship(back_populates="roles")
    role: Mapped[Role] = relationship()


class RefreshToken(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("ix_refresh_tokens_user", "user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Rotation chain: the token that replaced this one, for reuse detection
    # (docs/08-security-design.md §2 — rotated on each use).
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
