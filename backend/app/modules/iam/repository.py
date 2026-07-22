"""Data access for the IAM module.

Only this layer issues SQLAlchemy queries (Repository Pattern,
docs/17-coding-standards.md §2). User lookups are always tenant-scoped
(docs/05-database-design.md §1).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.iam.models import (
    RefreshToken,
    Role,
    RoleName,
    Tenant,
    User,
    UserRole,
)


class IamRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Tenants ---

    async def get_tenant_by_slug(self, slug: str) -> Tenant | None:
        result = await self._session.execute(select(Tenant).where(Tenant.slug == slug))
        return result.scalar_one_or_none()

    async def create_tenant(self, name: str, slug: str) -> Tenant:
        tenant = Tenant(name=name, slug=slug)
        self._session.add(tenant)
        await self._session.flush()
        return tenant

    # --- Users ---

    async def get_user_by_email(self, tenant_id: uuid.UUID, email: str) -> User | None:
        result = await self._session.execute(
            select(User)
            .where(User.tenant_id == tenant_id, User.email == email.lower())
            .options(selectinload(User.roles).selectinload(UserRole.role))
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self._session.execute(
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.roles).selectinload(UserRole.role))
        )
        return result.scalar_one_or_none()

    async def list_users(
        self, tenant_id: uuid.UUID, limit: int = 200, offset: int = 0
    ) -> list[User]:
        result = await self._session.execute(
            select(User)
            .where(User.tenant_id == tenant_id)
            .options(selectinload(User.roles).selectinload(UserRole.role))
            .order_by(User.full_name)
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars())

    async def create_user(
        self, tenant_id: uuid.UUID, email: str, password_hash: str, full_name: str
    ) -> User:
        user = User(
            tenant_id=tenant_id,
            email=email.lower(),
            password_hash=password_hash,
            full_name=full_name,
        )
        self._session.add(user)
        await self._session.flush()
        return user

    # --- Roles ---

    async def get_or_create_system_role(self, name: RoleName) -> Role:
        result = await self._session.execute(
            select(Role).where(Role.tenant_id.is_(None), Role.name == name)
        )
        role = result.scalar_one_or_none()
        if role is None:
            role = Role(tenant_id=None, name=name, permissions={})
            self._session.add(role)
            await self._session.flush()
        return role

    async def grant_role(self, user_id: uuid.UUID, role_id: uuid.UUID) -> UserRole:
        grant = UserRole(user_id=user_id, role_id=role_id)
        self._session.add(grant)
        await self._session.flush()
        return grant

    # --- Refresh tokens ---

    async def store_refresh_token(
        self, user_id: uuid.UUID, token_hash: str, expires_at: datetime
    ) -> RefreshToken:
        token = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self._session.add(token)
        await self._session.flush()
        return token

    async def get_refresh_token(self, token_hash: str) -> RefreshToken | None:
        result = await self._session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke_refresh_token(
        self, token: RefreshToken, replaced_by_id: uuid.UUID | None = None
    ) -> None:
        token.revoked_at = datetime.now(timezone.utc)
        token.replaced_by_id = replaced_by_id
        await self._session.flush()

    async def revoke_all_user_refresh_tokens(self, user_id: uuid.UUID) -> None:
        result = await self._session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
            )
        )
        now = datetime.now(timezone.utc)
        for token in result.scalars():
            token.revoked_at = now
        await self._session.flush()
