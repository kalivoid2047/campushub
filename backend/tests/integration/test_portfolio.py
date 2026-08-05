"""Portfolio module tests (FR-PORT-1, Epic E10).

Covers: completed-course + graded-work aggregation, ungraded submissions
excluded, courses with no grades yet still appear (average is null not
zero), and that it's strictly self-service (no roster/other-user leakage).
"""

import pytest
import pytest_asyncio

from app.core.security import create_access_token, hash_password
from app.modules.admin.models import Course, CourseEnrollment, Department, EnrollmentRole
from app.modules.iam.models import Tenant, TenantStatus, User

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def world(session):
    tenant = Tenant(name="Portfolio College", slug="port-college", status=TenantStatus.ACTIVE)
    session.add(tenant)
    await session.flush()

    def _user(email: str) -> User:
        return User(
            tenant_id=tenant.id,
            email=email,
            password_hash=hash_password("password-123"),
            full_name=email.split("@")[0],
        )

    lecturer, student = _user("lect@port.edu"), _user("stud@port.edu")
    session.add_all([lecturer, student])
    await session.flush()

    dept = Department(tenant_id=tenant.id, name="Comp Sci", code="CS")
    session.add(dept)
    await session.flush()
    graded_course = Course(
        tenant_id=tenant.id, department_id=dept.id, name="Algorithms", code="CS201", term="2026-S"
    )
    ungraded_course = Course(
        tenant_id=tenant.id, department_id=dept.id, name="Intro", code="CS101", term="2026-S"
    )
    session.add_all([graded_course, ungraded_course])
    await session.flush()
    session.add_all(
        [
            CourseEnrollment(
                course_id=graded_course.id, user_id=lecturer.id, role=EnrollmentRole.LECTURER
            ),
            CourseEnrollment(
                course_id=graded_course.id, user_id=student.id, role=EnrollmentRole.STUDENT
            ),
            CourseEnrollment(
                course_id=ungraded_course.id, user_id=lecturer.id, role=EnrollmentRole.LECTURER
            ),
            CourseEnrollment(
                course_id=ungraded_course.id, user_id=student.id, role=EnrollmentRole.STUDENT
            ),
        ]
    )
    await session.commit()

    def _hdr(user: User) -> dict:
        token = create_access_token(user_id=user.id, tenant_id=tenant.id, roles=["student"])
        return {"Authorization": f"Bearer {token}"}

    return {
        "graded_course": graded_course,
        "ungraded_course": ungraded_course,
        "users": {"lecturer": lecturer, "student": student},
        "lecturer": _hdr(lecturer),
        "student": _hdr(student),
    }


async def test_portfolio_aggregates_grades_and_excludes_ungraded_work(client, world):
    a1 = (
        await client.post(
            f"/api/v1/courses/{world['graded_course'].id}/assignments",
            json={"title": "PS1", "max_score": 100},
            headers=world["lecturer"],
        )
    ).json()
    a2 = (
        await client.post(
            f"/api/v1/courses/{world['graded_course'].id}/assignments",
            json={"title": "PS2", "max_score": 50},
            headers=world["lecturer"],
        )
    ).json()
    a3_never_graded = (
        await client.post(
            f"/api/v1/courses/{world['graded_course'].id}/assignments",
            json={"title": "PS3", "max_score": 100},
            headers=world["lecturer"],
        )
    ).json()

    sub1 = (
        await client.post(
            f"/api/v1/assignments/{a1['id']}/submissions",
            json={"content": {"a": 1}},
            headers=world["student"],
        )
    ).json()
    sub2 = (
        await client.post(
            f"/api/v1/assignments/{a2['id']}/submissions",
            json={"content": {"a": 1}},
            headers=world["student"],
        )
    ).json()
    # PS3 is submitted but deliberately never graded.
    await client.post(
        f"/api/v1/assignments/{a3_never_graded['id']}/submissions",
        json={"content": {"a": 1}},
        headers=world["student"],
    )

    await client.patch(
        f"/api/v1/submissions/{sub1['id']}/grade",
        json={"score": 90},
        headers=world["lecturer"],
    )
    await client.patch(
        f"/api/v1/submissions/{sub2['id']}/grade",
        json={"score": 25},
        headers=world["lecturer"],
    )

    resp = await client.get("/api/v1/portfolio/me", headers=world["student"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["full_name"] == world["users"]["student"].full_name
    assert len(body["courses"]) == 2

    algo = next(c for c in body["courses"] if c["course_code"] == "CS201")
    assert [e["title"] for e in algo["assignments"]] == ["PS1", "PS2"]
    # 90/100=90%, 25/50=50% -> average 70.0
    assert algo["average_score_percent"] == 70.0
    assert algo["department_name"] == "Comp Sci"

    intro = next(c for c in body["courses"] if c["course_code"] == "CS101")
    assert intro["assignments"] == []
    assert intro["average_score_percent"] is None


async def test_portfolio_is_self_service_only(client, world):
    # The lecturer's own portfolio (empty — they don't submit work) must
    # never include the student's grades; nothing about /portfolio/me takes
    # a user_id from the caller, so there's no roster/IDOR surface to test
    # beyond "each caller sees only their own record."
    resp = await client.get("/api/v1/portfolio/me", headers=world["lecturer"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["full_name"] == world["users"]["lecturer"].full_name
    for course in body["courses"]:
        assert course["assignments"] == []


async def test_portfolio_requires_auth(client, world):
    resp = await client.get("/api/v1/portfolio/me")
    assert resp.status_code == 401
