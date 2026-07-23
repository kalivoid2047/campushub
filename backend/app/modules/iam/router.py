"""HTTP routes for the IAM module.

Request/response wiring only — business logic lives in service.py.
Two routers: auth (mounted at /api/v1/auth) and tenant/user administration
(mounted at /api/v1/admin). See docs/06-api-design.md section 6.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.security import CurrentUser, get_current_user, require_role
from app.modules.iam.repository import IamRepository
from app.modules.iam.schemas import (
    CreateTenantRequest,
    CreateUserRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TenantResponse,
    TokenPairResponse,
    UserResponse,
)
from app.modules.iam.service import IamService

router = APIRouter()
admin_router = APIRouter()


def _service(session: AsyncSession = Depends(get_db_session)) -> IamService:
    return IamService(session)


def _client_ip(request: Request) -> str | None:
    # Trust X-Forwarded-For's first hop only because the deployment
    # topology (infra/nginx/campushub.conf) always fronts the API with our
    # own reverse proxy, which sets it — never derived from a header an
    # internet client could set directly on a request that skips the proxy.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post("/login", response_model=TokenPairResponse, summary="Log in")
async def login(
    request: LoginRequest,
    http_request: Request,
    service: IamService = Depends(_service),
) -> TokenPairResponse:
    return await service.login(request, client_ip=_client_ip(http_request))


@router.post("/refresh", response_model=TokenPairResponse, summary="Rotate tokens")
async def refresh(
    request: RefreshRequest,
    http_request: Request,
    service: IamService = Depends(_service),
) -> TokenPairResponse:
    return await service.refresh(request.refresh_token, client_ip=_client_ip(http_request))


@router.post("/logout", status_code=204, summary="Log out (revoke refresh token)")
async def logout(
    request: LogoutRequest,
    http_request: Request,
    service: IamService = Depends(_service),
) -> None:
    await service.logout(request.refresh_token, client_ip=_client_ip(http_request))


@router.get("/me", response_model=UserResponse, summary="Current user profile")
async def me(
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    user = await IamRepository(session).get_user_by_id(current.user_id)
    return UserResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        full_name=user.full_name,
        status=user.status.value,
        roles=[g.role.name.value for g in user.roles],
    )


@admin_router.post(
    "/tenants",
    response_model=TenantResponse,
    status_code=201,
    summary="Provision a new institution (super admin only)",
)
async def create_tenant(
    request: CreateTenantRequest,
    current: CurrentUser = Depends(require_role("super_admin")),
    service: IamService = Depends(_service),
) -> TenantResponse:
    tenant = await service.provision_tenant(request, actor_id=current.user_id)
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        status=tenant.status.value,
        created_at=tenant.created_at,
    )


@admin_router.post(
    "/users",
    response_model=UserResponse,
    status_code=201,
    summary="Create a user in the caller's institution",
)
async def create_user(
    request: CreateUserRequest,
    current: CurrentUser = Depends(require_role("institution_admin", "super_admin")),
    service: IamService = Depends(_service),
) -> UserResponse:
    # Tenant scope comes from the caller's JWT, never from the request body
    # (docs/08-security-design.md: never trust client-supplied tenant IDs).
    user = await service.create_user(current.tenant_id, request, actor_id=current.user_id)
    return UserResponse(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        full_name=user.full_name,
        status=user.status.value,
        roles=[request.role],
    )


@admin_router.get(
    "/users",
    response_model=list[UserResponse],
    summary="List users in the caller's institution",
)
async def list_users(
    limit: int = 200,
    offset: int = 0,
    current: CurrentUser = Depends(require_role("dept_admin", "institution_admin", "super_admin")),
    session: AsyncSession = Depends(get_db_session),
) -> list[UserResponse]:
    users = await IamRepository(session).list_users(
        current.tenant_id, limit=min(limit, 500), offset=offset
    )
    return [
        UserResponse(
            id=u.id,
            tenant_id=u.tenant_id,
            email=u.email,
            full_name=u.full_name,
            status=u.status.value,
            roles=[g.role.name.value for g in u.roles],
        )
        for u in users
    ]
