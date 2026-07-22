"""Business logic for the IAM module: login, token rotation, provisioning.

Implements docs/08-security-design.md §2 (auth) and docs/06-api-design.md §2
(auth flow). Refresh tokens rotate on every use; reuse of a rotated token
revokes the whole chain for that user (theft signal).
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.modules.iam.models import RoleName, Tenant, TenantStatus, User, UserStatus
from app.modules.iam.repository import IamRepository
from app.modules.iam.schemas import (
    CreateTenantRequest,
    CreateUserRequest,
    LoginRequest,
    TokenPairResponse,
)


def _invalid_credentials() -> HTTPException:
    # Deliberately generic: never reveal whether the tenant, account, or
    # password was wrong (docs/08-security-design.md §1 information disclosure).
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")


class IamService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = IamRepository(session)
        self._settings = get_settings()

    # --- Auth ---

    async def login(self, request: LoginRequest) -> TokenPairResponse:
        tenant = await self._repo.get_tenant_by_slug(request.tenant_slug)
        if tenant is None or tenant.status != TenantStatus.ACTIVE:
            raise _invalid_credentials()

        user = await self._repo.get_user_by_email(tenant.id, request.email)
        if user is None or user.status != UserStatus.ACTIVE:
            raise _invalid_credentials()
        if not verify_password(request.password, user.password_hash):
            raise _invalid_credentials()

        pair, _ = await self._issue_token_pair(user)
        await self._session.commit()
        return pair

    async def refresh(self, raw_refresh_token: str) -> TokenPairResponse:
        stored = await self._repo.get_refresh_token(hash_refresh_token(raw_refresh_token))
        if stored is None:
            raise _invalid_credentials()

        now = datetime.now(timezone.utc)
        expires_at = stored.expires_at
        if expires_at.tzinfo is None:  # SQLite loses tzinfo; treat as UTC
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if stored.revoked_at is not None:
            # Reuse of a rotated/revoked token — assume theft, kill the chain
            # (docs/08-security-design.md section 2).
            await self._repo.revoke_all_user_refresh_tokens(stored.user_id)
            await self._session.commit()
            raise _invalid_credentials()
        if expires_at < now:
            raise _invalid_credentials()

        user = await self._repo.get_user_by_id(stored.user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise _invalid_credentials()

        pair, new_token_id = await self._issue_token_pair(user)
        await self._repo.revoke_refresh_token(stored, replaced_by_id=new_token_id)
        await self._session.commit()
        return pair

    async def logout(self, raw_refresh_token: str) -> None:
        stored = await self._repo.get_refresh_token(hash_refresh_token(raw_refresh_token))
        if stored is not None and stored.revoked_at is None:
            await self._repo.revoke_refresh_token(stored)
        await self._session.commit()

    # --- Provisioning ---

    async def provision_tenant(self, request: CreateTenantRequest) -> Tenant:
        if await self._repo.get_tenant_by_slug(request.slug) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Tenant slug already exists"
            )
        tenant = await self._repo.create_tenant(request.name, request.slug)
        tenant.status = TenantStatus.ACTIVE

        admin = await self._repo.create_user(
            tenant_id=tenant.id,
            email=request.admin_email,
            password_hash=hash_password(request.admin_password),
            full_name=request.admin_full_name,
        )
        role = await self._repo.get_or_create_system_role(RoleName.INSTITUTION_ADMIN)
        await self._repo.grant_role(admin.id, role.id)

        await self._session.commit()
        return tenant

    async def create_user(self, tenant_id: uuid.UUID, request: CreateUserRequest) -> User:
        existing = await self._repo.get_user_by_email(tenant_id, request.email)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists in this institution",
            )
        user = await self._repo.create_user(
            tenant_id=tenant_id,
            email=request.email,
            password_hash=hash_password(request.password),
            full_name=request.full_name,
        )
        role = await self._repo.get_or_create_system_role(RoleName(request.role))
        await self._repo.grant_role(user.id, role.id)
        await self._session.commit()
        return user

    # --- Helpers ---

    def _role_names(self, user: User) -> list[str]:
        return [grant.role.name.value for grant in user.roles]

    async def _issue_token_pair(self, user: User) -> tuple[TokenPairResponse, uuid.UUID]:
        roles = self._role_names(user)
        access = create_access_token(user_id=user.id, tenant_id=user.tenant_id, roles=roles)
        raw_refresh, refresh_hash = generate_refresh_token()
        stored = await self._repo.store_refresh_token(
            user_id=user.id,
            token_hash=refresh_hash,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=self._settings.jwt_refresh_token_ttl_days),
        )
        pair = TokenPairResponse(
            access_token=access,
            refresh_token=raw_refresh,
            expires_in=self._settings.jwt_access_token_ttl_minutes * 60,
        )
        return pair, stored.id
