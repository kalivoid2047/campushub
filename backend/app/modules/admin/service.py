"""Business logic for the admin module: tenant structure management.

Tenant scope always comes from the caller's JWT (docs/08 section 3).
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.modules.admin.models import Course, CourseEnrollment, Department, EnrollmentRole
from app.modules.admin.repository import AdminRepository
from app.modules.admin.schemas import (
    CreateCourseRequest,
    CreateDepartmentRequest,
    EnrollUserRequest,
)


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = AdminRepository(session)

    async def create_department(
        self, user: CurrentUser, request: CreateDepartmentRequest
    ) -> Department:
        department = await self._repo.create_department(user.tenant_id, request.name, request.code)
        await self._session.commit()
        return department

    async def list_departments(self, user: CurrentUser) -> list[Department]:
        return await self._repo.list_departments(user.tenant_id)

    async def create_course(self, user: CurrentUser, request: CreateCourseRequest) -> Course:
        department = await self._repo.get_department(user.tenant_id, request.department_id)
        if department is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Department not found"
            )
        course = await self._repo.create_course(
            tenant_id=user.tenant_id,
            department_id=department.id,
            name=request.name,
            code=request.code,
            term=request.term,
        )
        await self._session.commit()
        return course

    async def list_courses(self, user: CurrentUser) -> list[Course]:
        return await self._repo.list_courses(user.tenant_id)

    async def enroll_user(
        self, user: CurrentUser, course_id: uuid.UUID, request: EnrollUserRequest
    ) -> CourseEnrollment:
        course = await self._repo.get_course(user.tenant_id, course_id)
        if course is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        target = await self._repo.get_tenant_user(user.tenant_id, request.user_id)
        if target is None:
            # Same 404 whether the user doesn't exist or belongs to another
            # tenant — no cross-tenant existence leaks (docs/08 section 1).
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if await self._repo.get_enrollment(course_id, request.user_id) is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already enrolled")
        enrollment = await self._repo.enroll(
            course_id, request.user_id, EnrollmentRole(request.role)
        )
        await self._session.commit()
        return enrollment
