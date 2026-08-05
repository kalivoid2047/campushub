"""Search (Epic E7) + admin analytics/audit (Epic E8) tests.

Covers: permission-scoped keyword search across resources/announcements/
messages (FR-SRCH-1) including DM privacy, and the storage/audit/engagement
admin endpoints (FR-ADM-2/3/5).
"""

import io

import pytest
import pytest_asyncio

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.core.storage import reset_storage_for_tests
from app.modules.admin.models import Course, CourseEnrollment, Department, EnrollmentRole
from app.modules.iam.models import Tenant, TenantStatus, User

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path):
    settings = get_settings()
    original = settings.local_storage_path
    settings.local_storage_path = str(tmp_path / "storage")
    reset_storage_for_tests()
    yield
    settings.local_storage_path = original
    reset_storage_for_tests()


@pytest_asyncio.fixture
async def world(session):
    tenant = Tenant(name="Srch College", slug="srch-college", status=TenantStatus.ACTIVE)
    session.add(tenant)
    await session.flush()

    def _user(email: str) -> User:
        return User(
            tenant_id=tenant.id,
            email=email,
            password_hash=hash_password("password-123"),
            full_name=email.split("@")[0],
        )

    admin, lecturer, student, outsider = (
        _user("admin@srch.edu"),
        _user("lect@srch.edu"),
        _user("stud@srch.edu"),
        _user("outsider@srch.edu"),
    )
    session.add_all([admin, lecturer, student, outsider])
    await session.flush()

    dept = Department(tenant_id=tenant.id, name="Biology", code="BIO")
    session.add(dept)
    await session.flush()
    course = Course(
        tenant_id=tenant.id,
        department_id=dept.id,
        name="Genetics",
        code="BIO301",
        term="2026-F",
    )
    session.add(course)
    await session.flush()
    session.add_all(
        [
            CourseEnrollment(
                course_id=course.id, user_id=lecturer.id, role=EnrollmentRole.LECTURER
            ),
            CourseEnrollment(course_id=course.id, user_id=student.id, role=EnrollmentRole.STUDENT),
        ]
    )
    await session.commit()

    def _hdr(user: User, roles=("student",)) -> dict:
        token = create_access_token(user_id=user.id, tenant_id=tenant.id, roles=list(roles))
        return {"Authorization": f"Bearer {token}"}

    return {
        "tenant": tenant,
        "course": course,
        "users": {"admin": admin, "lecturer": lecturer, "student": student, "outsider": outsider},
        "admin": _hdr(admin, ("institution_admin",)),
        "lecturer": _hdr(lecturer),
        "student": _hdr(student),
        "outsider": _hdr(outsider),
    }


async def _seed_content(client, world):
    """One resource, one announcement, one channel message, one DM message,
    all containing the token 'genome'."""
    module = (
        await client.post(
            f"/api/v1/courses/{world['course'].id}/modules",
            json={"title": "Unit 1"},
            headers=world["lecturer"],
        )
    ).json()
    await client.post(
        f"/api/v1/modules/{module['id']}/resources",
        data={"title": "Human genome slides", "type": "slide"},
        files={"file": ("g.pdf", io.BytesIO(b"%PDF-1.4\ndata"), "application/pdf")},
        headers=world["lecturer"],
    )
    await client.post(
        "/api/v1/announcements",
        json={
            "scope": "course",
            "scope_id": str(world["course"].id),
            "title": "Genome lab moved",
            "body": "The genome sequencing lab is now Thursday.",
        },
        headers=world["lecturer"],
    )
    channel_id = (
        await client.get(f"/api/v1/courses/{world['course'].id}/channel", headers=world["student"])
    ).json()["id"]
    await client.post(
        f"/api/v1/channels/{channel_id}/messages",
        json={"body": "anyone understand genome imprinting?"},
        headers=world["student"],
    )
    dm_id = (
        await client.post(
            "/api/v1/channels/dm",
            json={"recipient_id": str(world["users"]["lecturer"].id)},
            headers=world["student"],
        )
    ).json()["id"]
    await client.post(
        f"/api/v1/channels/{dm_id}/messages",
        json={"body": "private genome question about my grade"},
        headers=world["student"],
    )


async def test_search_scoped_to_enrollment(client, world):
    await _seed_content(client, world)

    hits = (
        await client.get("/api/v1/search", params={"q": "genome"}, headers=world["student"])
    ).json()["hits"]
    kinds = sorted(h["kind"] for h in hits)
    # Student sees resource + announcement + course message + own DM.
    assert kinds == ["announcement", "message", "message", "resource"]

    # Outsider (no enrollment) sees nothing.
    outsider_hits = (
        await client.get("/api/v1/search", params={"q": "genome"}, headers=world["outsider"])
    ).json()["hits"]
    assert outsider_hits == []


async def test_admin_search_excludes_others_dms(client, world):
    await _seed_content(client, world)
    hits = (
        await client.get("/api/v1/search", params={"q": "genome"}, headers=world["admin"])
    ).json()["hits"]
    snippets = " ".join(h["snippet"] for h in hits)
    # Admin sees course content but NOT the student-lecturer private DM.
    assert "private genome question" not in snippets
    assert any(h["kind"] == "resource" for h in hits)


async def test_short_query_returns_empty(client, world):
    resp = await client.get("/api/v1/search", params={"q": "g"}, headers=world["student"])
    assert resp.json()["hits"] == []
    assert resp.json()["truncated"] is False


async def test_search_signals_truncation_past_the_per_kind_cap(client, world):
    module = (
        await client.post(
            f"/api/v1/courses/{world['course'].id}/modules",
            json={"title": "Unit 1"},
            headers=world["lecturer"],
        )
    ).json()
    for i in range(25):  # more than the 20-per-kind cap
        await client.post(
            f"/api/v1/modules/{module['id']}/resources",
            data={"title": f"Widget lecture {i}", "type": "slide"},
            files={"file": ("g.pdf", io.BytesIO(b"%PDF-1.4\ndata"), "application/pdf")},
            headers=world["lecturer"],
        )

    resp = await client.get("/api/v1/search", params={"q": "widget"}, headers=world["student"])
    body = resp.json()
    assert len(body["hits"]) == 20
    assert body["truncated"] is True


async def test_storage_usage_endpoint(client, world):
    await _seed_content(client, world)
    usage = await client.get("/api/v1/admin/storage/usage", headers=world["admin"])
    assert usage.status_code == 200
    body = usage.json()
    assert body["used_bytes"] == 13  # len(b"%PDF-1.4\ndata")
    assert body["quota_bytes"] > 0

    denied = await client.get("/api/v1/admin/storage/usage", headers=world["student"])
    assert denied.status_code == 403


async def test_engagement_counts(client, world):
    await _seed_content(client, world)
    counts = (await client.get("/api/v1/admin/analytics/engagement", headers=world["admin"])).json()
    assert counts["users"] == 4
    assert counts["resources"] == 1
    assert counts["messages"] == 2


async def test_audit_log_endpoint(client, session, world):
    # Produce an audit entry via grading flow.
    assignment = (
        await client.post(
            f"/api/v1/courses/{world['course'].id}/assignments",
            json={"title": "PS1", "max_score": 10},
            headers=world["lecturer"],
        )
    ).json()
    submission = (
        await client.post(
            f"/api/v1/assignments/{assignment['id']}/submissions",
            json={"content": {"a": 1}},
            headers=world["student"],
        )
    ).json()
    await client.patch(
        f"/api/v1/submissions/{submission['id']}/grade",
        json={"score": 9},
        headers=world["lecturer"],
    )

    logs = (await client.get("/api/v1/admin/audit-logs", headers=world["admin"])).json()
    assert any(entry["action"] == "grade.created" for entry in logs)

    denied = await client.get("/api/v1/admin/audit-logs", headers=world["student"])
    assert denied.status_code == 403


async def test_list_users_endpoint(client, world):
    resp = await client.get("/api/v1/admin/users", headers=world["admin"])
    assert resp.status_code == 200
    emails = sorted(u["email"] for u in resp.json())
    assert emails == [
        "admin@srch.edu",
        "lect@srch.edu",
        "outsider@srch.edu",
        "stud@srch.edu",
    ]
    lecturer_entry = next(u for u in resp.json() if u["email"] == "lect@srch.edu")
    assert lecturer_entry["roles"] == []  # world's users carry no granted system role

    # dept_admin-tier access is allowed; plain student/lecturer roles are not.
    denied = await client.get("/api/v1/admin/users", headers=world["student"])
    assert denied.status_code == 403


async def test_admin_mutations_are_audit_logged(client, world):
    dept = (
        await client.post(
            "/api/v1/admin/departments",
            json={"name": "Physics", "code": "PHY"},
            headers=world["admin"],
        )
    ).json()
    course = (
        await client.post(
            "/api/v1/admin/courses",
            json={
                "department_id": dept["id"],
                "name": "Mechanics",
                "code": "PHY101",
                "term": "2026-F",
            },
            headers=world["admin"],
        )
    ).json()
    await client.post(
        f"/api/v1/admin/courses/{course['id']}/enrollments",
        json={"user_id": str(world["users"]["outsider"].id), "role": "student"},
        headers=world["admin"],
    )

    logs = (await client.get("/api/v1/admin/audit-logs", headers=world["admin"])).json()
    actions = [entry["action"] for entry in logs]
    assert "department.created" in actions
    assert "course.created" in actions
    assert "enrollment.created" in actions


async def test_my_courses_endpoint(client, world):
    # Student sees only enrolled courses; outsider sees none; admin sees all.
    student_courses = (await client.get("/api/v1/courses", headers=world["student"])).json()
    assert [c["code"] for c in student_courses] == ["BIO301"]

    outsider_courses = (await client.get("/api/v1/courses", headers=world["outsider"])).json()
    assert outsider_courses == []

    admin_courses = (await client.get("/api/v1/courses", headers=world["admin"])).json()
    assert len(admin_courses) == 1
