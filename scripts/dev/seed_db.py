"""Seed the local dev database with fixture data.

Creates a demo tenant with admin/lecturer/student accounts, one department,
one course with enrollments, a module, and a welcome announcement.

Run from backend/ (so `app` is importable) with migrations already applied:
    python ../scripts/dev/seed_db.py
or via `make seed`.

Credentials created (dev only — never reuse in production):
    admin@demo.edu / demo-admin-pass      (institution_admin)
    lecturer@demo.edu / demo-lect-pass    (student platform role; lecturer on the course)
    student@demo.edu / demo-stud-pass     (student)
Tenant slug: demo-college
"""

import asyncio

from sqlalchemy import select

from app.core.db import async_session_factory
from app.core.security import hash_password
from app.modules.admin.models import Course, CourseEnrollment, Department, EnrollmentRole
from app.modules.communication.models import Announcement, AnnouncementScope
from app.modules.iam.models import RoleName, Tenant, TenantStatus, User
from app.modules.iam.repository import IamRepository
from app.modules.resources.models import CourseModule


async def seed() -> None:
    async with async_session_factory() as session:
        existing = await session.execute(select(Tenant).where(Tenant.slug == "demo-college"))
        if existing.scalar_one_or_none() is not None:
            print("demo-college tenant already exists — nothing to do")
            return

        tenant = Tenant(name="Demo College", slug="demo-college", status=TenantStatus.ACTIVE)
        session.add(tenant)
        await session.flush()

        repo = IamRepository(session)

        async def make_user(email: str, password: str, name: str, role: RoleName) -> User:
            user = await repo.create_user(
                tenant_id=tenant.id,
                email=email,
                password_hash=hash_password(password),
                full_name=name,
            )
            system_role = await repo.get_or_create_system_role(role)
            await repo.grant_role(user.id, system_role.id)
            return user

        admin = await make_user(
            "admin@demo.edu",
            "demo-admin-pass",
            "Demo Admin",
            RoleName.INSTITUTION_ADMIN,
        )
        lecturer = await make_user(
            "lecturer@demo.edu", "demo-lect-pass", "Demo Lecturer", RoleName.STUDENT
        )
        student = await make_user(
            "student@demo.edu", "demo-stud-pass", "Demo Student", RoleName.STUDENT
        )

        dept = Department(tenant_id=tenant.id, name="Computer Science", code="CS")
        session.add(dept)
        await session.flush()

        course = Course(
            tenant_id=tenant.id,
            department_id=dept.id,
            name="Introduction to Programming",
            code="CS101",
            term="2026-F",
        )
        session.add(course)
        await session.flush()

        session.add_all(
            [
                CourseEnrollment(
                    course_id=course.id,
                    user_id=lecturer.id,
                    role=EnrollmentRole.LECTURER,
                ),
                CourseEnrollment(
                    course_id=course.id,
                    user_id=student.id,
                    role=EnrollmentRole.STUDENT,
                ),
                CourseModule(
                    tenant_id=tenant.id,
                    course_id=course.id,
                    title="Week 1 — Getting Started",
                    position=1,
                ),
                Announcement(
                    tenant_id=tenant.id,
                    scope=AnnouncementScope.INSTITUTION,
                    scope_id=None,
                    title="Welcome to CampusHub",
                    body="Your campus, one app. Explore CS101 to get started.",
                    published_by=admin.id,
                ),
            ]
        )
        await session.commit()
        print("Seeded demo-college with admin/lecturer/student accounts and CS101.")


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
