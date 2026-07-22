"""Data access for the admin module (tenant structure).

Every query filters by tenant_id (docs/05-database-design.md section 1).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import (
    AuditLog,
    Course,
    CourseEnrollment,
    Department,
    EnrollmentRole,
    StorageQuota,
)
from app.modules.iam.models import Tenant, User


class AdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Departments ---

    async def create_department(self, tenant_id: uuid.UUID, name: str, code: str) -> Department:
        department = Department(tenant_id=tenant_id, name=name, code=code)
        self._session.add(department)
        await self._session.flush()
        return department

    async def get_department(
        self, tenant_id: uuid.UUID, department_id: uuid.UUID
    ) -> Department | None:
        result = await self._session.execute(
            select(Department).where(
                Department.id == department_id, Department.tenant_id == tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def list_departments(self, tenant_id: uuid.UUID) -> list[Department]:
        result = await self._session.execute(
            select(Department).where(Department.tenant_id == tenant_id).order_by(Department.code)
        )
        return list(result.scalars())

    # --- Courses ---

    async def create_course(
        self,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID,
        name: str,
        code: str,
        term: str,
    ) -> Course:
        course = Course(
            tenant_id=tenant_id,
            department_id=department_id,
            name=name,
            code=code,
            term=term,
        )
        self._session.add(course)
        await self._session.flush()
        return course

    async def get_course(self, tenant_id: uuid.UUID, course_id: uuid.UUID) -> Course | None:
        result = await self._session.execute(
            select(Course).where(Course.id == course_id, Course.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def list_courses(self, tenant_id: uuid.UUID) -> list[Course]:
        result = await self._session.execute(
            select(Course).where(Course.tenant_id == tenant_id).order_by(Course.code)
        )
        return list(result.scalars())

    async def list_enrolled_courses(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[Course]:
        result = await self._session.execute(
            select(Course)
            .join(CourseEnrollment, CourseEnrollment.course_id == Course.id)
            .where(Course.tenant_id == tenant_id, CourseEnrollment.user_id == user_id)
            .order_by(Course.code)
        )
        return list(result.scalars())

    # --- Enrollments ---

    async def get_enrollment(
        self, course_id: uuid.UUID, user_id: uuid.UUID
    ) -> CourseEnrollment | None:
        result = await self._session.execute(
            select(CourseEnrollment).where(
                CourseEnrollment.course_id == course_id,
                CourseEnrollment.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def enroll(
        self, course_id: uuid.UUID, user_id: uuid.UUID, role: EnrollmentRole
    ) -> CourseEnrollment:
        enrollment = CourseEnrollment(course_id=course_id, user_id=user_id, role=role)
        self._session.add(enrollment)
        await self._session.flush()
        return enrollment

    async def list_all_course_scopes(
        self, tenant_id: uuid.UUID
    ) -> list[tuple[uuid.UUID, uuid.UUID]]:
        """All (course_id, department_id) pairs in the tenant."""
        result = await self._session.execute(
            select(Course.id, Course.department_id).where(Course.tenant_id == tenant_id)
        )
        return [(row[0], row[1]) for row in result]

    async def list_user_course_scopes(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[tuple[uuid.UUID, uuid.UUID]]:
        """(course_id, department_id) pairs the user is enrolled in."""
        result = await self._session.execute(
            select(Course.id, Course.department_id)
            .join(CourseEnrollment, CourseEnrollment.course_id == Course.id)
            .where(Course.tenant_id == tenant_id, CourseEnrollment.user_id == user_id)
        )
        return [(row[0], row[1]) for row in result]

    # --- Users (tenant-scoped lookup for enrollment validation) ---

    async def get_tenant_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> User | None:
        result = await self._session.execute(
            select(User).where(User.id == user_id, User.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    # --- Audit log (read-only; writes happen at the point of action) ---

    async def list_audit_logs(
        self, tenant_id: uuid.UUID, limit: int = 100, offset: int = 0
    ) -> list[AuditLog]:
        result = await self._session.execute(
            select(AuditLog)
            .where(AuditLog.tenant_id == tenant_id)
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars())

    # --- Engagement counts (basic admin analytics, FR-ADM-3) ---

    async def engagement_counts(self, tenant_id: uuid.UUID) -> dict[str, int]:
        from sqlalchemy import func

        from app.modules.assignments.models import Submission
        from app.modules.communication.models import Message
        from app.modules.iam.models import User as UserModel
        from app.modules.resources.models import Resource

        counts = {}
        for name, model in (
            ("users", UserModel),
            ("resources", Resource),
            ("messages", Message),
            ("submissions", Submission),
        ):
            result = await self._session.execute(
                select(func.count(model.id)).where(model.tenant_id == tenant_id)
            )
            counts[name] = int(result.scalar_one())
        return counts

    # --- Storage quota ---

    async def get_or_create_quota(self, tenant_id: uuid.UUID) -> StorageQuota:
        result = await self._session.execute(
            select(StorageQuota).where(StorageQuota.tenant_id == tenant_id)
        )
        quota = result.scalar_one_or_none()
        if quota is None:
            tenant = await self._session.get(Tenant, tenant_id)
            quota = StorageQuota(
                tenant_id=tenant_id,
                used_bytes=0,
                quota_bytes=tenant.storage_quota_bytes if tenant else 0,
            )
            self._session.add(quota)
            await self._session.flush()
        return quota
