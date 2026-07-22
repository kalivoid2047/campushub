"""HTTP routes for the admin module (tenant structure).

Mounted at /api/v1/admin. Structure management requires institution_admin
or super_admin; dept_admin may create courses (docs/08 section 7 RBAC matrix).
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.security import CurrentUser, get_current_user, require_role
from app.modules.admin.repository import AdminRepository
from app.modules.admin.schemas import (
    AuditLogEntry,
    CourseResponse,
    CreateCourseRequest,
    CreateDepartmentRequest,
    DepartmentResponse,
    EngagementResponse,
    EnrollmentResponse,
    EnrollUserRequest,
    StorageUsageResponse,
)
from app.modules.admin.service import AdminService

router = APIRouter()
member_router = APIRouter()  # mounted at /api/v1 — member-scoped, not admin-only

_STRUCTURE_ADMIN = require_role("institution_admin", "super_admin")
_COURSE_ADMIN = require_role("dept_admin", "institution_admin", "super_admin")


def _service(session: AsyncSession = Depends(get_db_session)) -> AdminService:
    return AdminService(session)


@router.post(
    "/departments",
    response_model=DepartmentResponse,
    status_code=201,
    summary="Create a department",
)
async def create_department(
    request: CreateDepartmentRequest,
    user: CurrentUser = Depends(_STRUCTURE_ADMIN),
    service: AdminService = Depends(_service),
) -> DepartmentResponse:
    return await service.create_department(user, request)


@router.get(
    "/departments",
    response_model=list[DepartmentResponse],
    summary="List departments",
)
async def list_departments(
    user: CurrentUser = Depends(_COURSE_ADMIN),
    service: AdminService = Depends(_service),
) -> list[DepartmentResponse]:
    return await service.list_departments(user)


@router.post(
    "/courses",
    response_model=CourseResponse,
    status_code=201,
    summary="Create a course",
)
async def create_course(
    request: CreateCourseRequest,
    user: CurrentUser = Depends(_COURSE_ADMIN),
    service: AdminService = Depends(_service),
) -> CourseResponse:
    return await service.create_course(user, request)


@router.get("/courses", response_model=list[CourseResponse], summary="List courses")
async def list_courses(
    user: CurrentUser = Depends(_COURSE_ADMIN),
    service: AdminService = Depends(_service),
) -> list[CourseResponse]:
    return await service.list_courses(user)


@router.get(
    "/storage/usage",
    response_model=StorageUsageResponse,
    summary="Tenant storage usage vs quota",
)
async def storage_usage(
    user: CurrentUser = Depends(_STRUCTURE_ADMIN),
    session: AsyncSession = Depends(get_db_session),
) -> StorageUsageResponse:
    quota = await AdminRepository(session).get_or_create_quota(user.tenant_id)
    await session.commit()
    return StorageUsageResponse(
        used_bytes=quota.used_bytes,
        quota_bytes=quota.quota_bytes,
        percent_used=(
            round(quota.used_bytes / quota.quota_bytes * 100, 2) if quota.quota_bytes else 0.0
        ),
    )


@router.get(
    "/audit-logs",
    response_model=list[AuditLogEntry],
    summary="Tenant audit trail (read-only, newest first)",
)
async def audit_logs(
    limit: int = 100,
    offset: int = 0,
    user: CurrentUser = Depends(_STRUCTURE_ADMIN),
    session: AsyncSession = Depends(get_db_session),
) -> list[AuditLogEntry]:
    rows = await AdminRepository(session).list_audit_logs(
        user.tenant_id, limit=min(limit, 500), offset=offset
    )
    return [
        AuditLogEntry(
            id=r.id,
            actor_id=r.actor_id,
            action=r.action,
            target_type=r.target_type,
            target_id=r.target_id,
            metadata=r.meta,
            ip_address=r.ip_address,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get(
    "/analytics/engagement",
    response_model=EngagementResponse,
    summary="Basic tenant engagement counts (FR-ADM-3)",
)
async def engagement(
    user: CurrentUser = Depends(_STRUCTURE_ADMIN),
    session: AsyncSession = Depends(get_db_session),
) -> EngagementResponse:
    counts = await AdminRepository(session).engagement_counts(user.tenant_id)
    return EngagementResponse(**counts)


@router.post(
    "/courses/{course_id}/enrollments",
    response_model=EnrollmentResponse,
    status_code=201,
    summary="Enroll a user in a course",
)
async def enroll_user(
    course_id: uuid.UUID,
    request: EnrollUserRequest,
    user: CurrentUser = Depends(_COURSE_ADMIN),
    service: AdminService = Depends(_service),
) -> EnrollmentResponse:
    enrollment = await service.enroll_user(user, course_id, request)
    return EnrollmentResponse(
        id=enrollment.id,
        course_id=enrollment.course_id,
        user_id=enrollment.user_id,
        role=enrollment.role.value,
        enrolled_at=enrollment.enrolled_at,
    )


@member_router.get(
    "/courses",
    response_model=list[CourseResponse],
    summary="Courses the caller belongs to (all courses for admins)",
)
async def my_courses(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[CourseResponse]:
    repo = AdminRepository(session)
    if user.has_any_role("dept_admin", "institution_admin", "super_admin"):
        return await repo.list_courses(user.tenant_id)
    return await repo.list_enrolled_courses(user.tenant_id, user.user_id)
