"""Business logic for the IAM module: login, token rotation, provisioning.

Implements docs/08-security-design.md §2 (auth) and docs/06-api-design.md §2
(auth flow). Refresh tokens rotate on every use; reuse of a rotated token
revokes the whole chain for that user (theft signal).
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.rate_limit import login_rate_limiter
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
from app.shared.audit import record_audit_event


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

    async def login(
        self, request: LoginRequest, *, client_ip: str | None = None
    ) -> TokenPairResponse:
        account_key = f"acct:{request.tenant_slug}:{request.email.lower()}"
        ip_key = f"ip:{client_ip}" if client_ip else None
        limiter_keys = tuple(k for k in (account_key, ip_key) if k)

        wait = login_rate_limiter.seconds_until_allowed(*limiter_keys)
        if wait is not None:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Try again later.",
                headers={"Retry-After": str(int(wait) + 1)},
            )

        tenant = await self._repo.get_tenant_by_slug(request.tenant_slug)
        if tenant is None or tenant.status != TenantStatus.ACTIVE:
            login_rate_limiter.record_failure(*limiter_keys)
            raise _invalid_credentials()

        user = await self._repo.get_user_by_email(tenant.id, request.email)
        if user is None or user.status != UserStatus.ACTIVE:
            login_rate_limiter.record_failure(*limiter_keys)
            await record_audit_event(
                self._session,
                tenant_id=tenant.id,
                actor_id=None,
                action="auth.login_failed",
                ip_address=client_ip,
                meta={"email": request.email},
            )
            raise _invalid_credentials()
        if not verify_password(request.password, user.password_hash):
            login_rate_limiter.record_failure(*limiter_keys)
            await record_audit_event(
                self._session,
                tenant_id=tenant.id,
                actor_id=user.id,
                action="auth.login_failed",
                target_type="user",
                target_id=user.id,
                ip_address=client_ip,
            )
            raise _invalid_credentials()

        login_rate_limiter.record_success(*limiter_keys)
        pair, _ = await self._issue_token_pair(user)
        await record_audit_event(
            self._session,
            tenant_id=tenant.id,
            actor_id=user.id,
            action="auth.login_succeeded",
            target_type="user",
            target_id=user.id,
            ip_address=client_ip,
        )
        await self._session.commit()
        return pair

    async def refresh(
        self, raw_refresh_token: str, *, client_ip: str | None = None
    ) -> TokenPairResponse:
        stored = await self._repo.get_refresh_token(hash_refresh_token(raw_refresh_token))
        if stored is None:
            raise _invalid_credentials()

        now = datetime.now(UTC)
        expires_at = stored.expires_at
        if expires_at.tzinfo is None:  # SQLite loses tzinfo; treat as UTC
            expires_at = expires_at.replace(tzinfo=UTC)

        if stored.revoked_at is not None:
            # Reuse of a rotated/revoked token — assume theft, kill the chain
            # (docs/08-security-design.md section 2). This is the single
            # highest-signal auth event in the system — always worth an
            # audit entry even if the victim user has since been deleted.
            await self._repo.revoke_all_user_refresh_tokens(stored.user_id)
            victim = await self._repo.get_user_by_id(stored.user_id)
            if victim is not None:
                await record_audit_event(
                    self._session,
                    tenant_id=victim.tenant_id,
                    actor_id=victim.id,
                    action="auth.refresh_token_reuse_detected",
                    target_type="user",
                    target_id=victim.id,
                    ip_address=client_ip,
                )
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

    async def logout(self, raw_refresh_token: str, *, client_ip: str | None = None) -> None:
        stored = await self._repo.get_refresh_token(hash_refresh_token(raw_refresh_token))
        if stored is not None and stored.revoked_at is None:
            await self._repo.revoke_refresh_token(stored)
            user = await self._repo.get_user_by_id(stored.user_id)
            if user is not None:
                await record_audit_event(
                    self._session,
                    tenant_id=user.tenant_id,
                    actor_id=user.id,
                    action="auth.logout",
                    target_type="user",
                    target_id=user.id,
                    ip_address=client_ip,
                )
        await self._session.commit()

    # --- Provisioning ---

    async def provision_tenant(
        self, request: CreateTenantRequest, *, actor_id: uuid.UUID | None = None
    ) -> Tenant:
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

        # Logged against the new tenant's own audit trail — there is no
        # platform-wide log, and a fresh institution's history reasonably
        # starts with "how it came to exist" (docs/08 section 9).
        await record_audit_event(
            self._session,
            tenant_id=tenant.id,
            actor_id=actor_id,
            action="tenant.created",
            target_type="tenant",
            target_id=tenant.id,
            meta={"slug": tenant.slug},
        )
        await self._session.commit()
        return tenant

    async def create_user(
        self, tenant_id: uuid.UUID, request: CreateUserRequest, *, actor_id: uuid.UUID
    ) -> User:
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
        await record_audit_event(
            self._session,
            tenant_id=tenant_id,
            actor_id=actor_id,
            action="user.created",
            target_type="user",
            target_id=user.id,
            meta={"role": request.role},
        )
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
            expires_at=datetime.now(UTC)
            + timedelta(days=self._settings.jwt_refresh_token_ttl_days),
        )
        pair = TokenPairResponse(
            access_token=access,
            refresh_token=raw_refresh,
            expires_in=self._settings.jwt_access_token_ttl_minutes * 60,
        )
        return pair, stored.id
