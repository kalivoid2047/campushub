"""Communication module tests (Epic E3).

Covers: course channel lazy creation + enrollment gating, DM creation/reuse,
message send with client_id dedupe (FR-COM-4), history pagination,
announcement scope RBAC + visibility, sync change emission.
"""

import uuid

import pytest
import pytest_asyncio

from app.core.security import create_access_token, hash_password
from app.modules.admin.models import Course, CourseEnrollment, Department, EnrollmentRole
from app.modules.iam.models import Tenant, TenantStatus, User

pytestmark = pytest.mark.asyncio

CHANGES = "/api/v1/sync/changes"


@pytest_asyncio.fixture
async def world(session):
    tenant = Tenant(name="Comm College", slug="comm-college", status=TenantStatus.ACTIVE)
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
        _user("admin@comm.edu"),
        _user("lect@comm.edu"),
        _user("stud@comm.edu"),
        _user("outsider@comm.edu"),
    )
    session.add_all([admin, lecturer, student, outsider])
    await session.flush()

    dept = Department(tenant_id=tenant.id, name="Physics", code="PHY")
    session.add(dept)
    await session.flush()
    course = Course(
        tenant_id=tenant.id,
        department_id=dept.id,
        name="Mechanics",
        code="PHY101",
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

    def _hdr(user: User, roles: list[str]) -> dict:
        token = create_access_token(user_id=user.id, tenant_id=tenant.id, roles=roles)
        return {"Authorization": f"Bearer {token}"}

    return {
        "tenant": tenant,
        "course": course,
        "dept": dept,
        "users": {"admin": admin, "lecturer": lecturer, "student": student, "outsider": outsider},
        "admin": _hdr(admin, ["institution_admin"]),
        "lecturer": _hdr(lecturer, ["student"]),
        "student": _hdr(student, ["student"]),
        "outsider": _hdr(outsider, ["student"]),
    }


async def test_course_channel_lazy_creation_and_gating(client, world):
    url = f"/api/v1/courses/{world['course'].id}/channel"
    first = await client.get(url, headers=world["student"])
    assert first.status_code == 200
    channel = first.json()
    assert channel["type"] == "course"

    again = await client.get(url, headers=world["lecturer"])
    assert again.json()["id"] == channel["id"]  # reused, not duplicated

    blocked = await client.get(url, headers=world["outsider"])
    assert blocked.status_code == 403


async def test_message_roundtrip_and_pagination(client, world):
    channel_id = (
        await client.get(f"/api/v1/courses/{world['course'].id}/channel", headers=world["student"])
    ).json()["id"]

    for i in range(3):
        resp = await client.post(
            f"/api/v1/channels/{channel_id}/messages",
            json={"body": f"message {i}"},
            headers=world["student"],
        )
        assert resp.status_code == 201

    page = (
        await client.get(
            f"/api/v1/channels/{channel_id}/messages",
            params={"limit": 2},
            headers=world["lecturer"],
        )
    ).json()
    assert len(page["messages"]) == 2
    assert page["messages"][0]["body"] == "message 2"  # newest first
    assert page["has_more"] is True

    older = (
        await client.get(
            f"/api/v1/channels/{channel_id}/messages",
            params={"limit": 2, "before": page["next_cursor"]},
            headers=world["lecturer"],
        )
    ).json()
    assert [m["body"] for m in older["messages"]] == ["message 0"]


async def test_offline_client_id_dedupes(client, world):
    channel_id = (
        await client.get(f"/api/v1/courses/{world['course'].id}/channel", headers=world["student"])
    ).json()["id"]

    client_id = str(uuid.uuid4())
    body = {"body": "sent from offline queue", "client_id": client_id}
    first = await client.post(
        f"/api/v1/channels/{channel_id}/messages", json=body, headers=world["student"]
    )
    replay = await client.post(
        f"/api/v1/channels/{channel_id}/messages", json=body, headers=world["student"]
    )
    assert first.json()["id"] == replay.json()["id"]

    page = (
        await client.get(f"/api/v1/channels/{channel_id}/messages", headers=world["student"])
    ).json()
    assert len(page["messages"]) == 1


async def test_dm_creation_reuse_and_privacy(client, world):
    recipient = world["users"]["lecturer"]
    dm = await client.post(
        "/api/v1/channels/dm",
        json={"recipient_id": str(recipient.id)},
        headers=world["student"],
    )
    assert dm.status_code == 200
    dm_id = dm.json()["id"]

    # Same pair → same channel (either direction).
    again = await client.post(
        "/api/v1/channels/dm",
        json={"recipient_id": str(world["users"]["student"].id)},
        headers=world["lecturer"],
    )
    assert again.json()["id"] == dm_id

    await client.post(
        f"/api/v1/channels/{dm_id}/messages",
        json={"body": "private"},
        headers=world["student"],
    )
    snoop = await client.get(f"/api/v1/channels/{dm_id}/messages", headers=world["outsider"])
    assert snoop.status_code == 403


async def test_announcement_scopes_and_visibility(client, world):
    # Institution-wide requires admin.
    denied = await client.post(
        "/api/v1/announcements",
        json={"scope": "institution", "title": "Nope", "body": "x"},
        headers=world["student"],
    )
    assert denied.status_code == 403

    inst = await client.post(
        "/api/v1/announcements",
        json={"scope": "institution", "title": "Campus closed Friday", "body": "..."},
        headers=world["admin"],
    )
    assert inst.status_code == 201

    # Lecturer can announce to their own course; student cannot.
    course_ok = await client.post(
        "/api/v1/announcements",
        json={
            "scope": "course",
            "scope_id": str(world["course"].id),
            "title": "Quiz moved",
            "body": "...",
        },
        headers=world["lecturer"],
    )
    assert course_ok.status_code == 201
    course_denied = await client.post(
        "/api/v1/announcements",
        json={
            "scope": "course",
            "scope_id": str(world["course"].id),
            "title": "x",
            "body": "x",
        },
        headers=world["student"],
    )
    assert course_denied.status_code == 403

    # Enrolled student sees both; outsider sees only institution-wide.
    student_view = (await client.get("/api/v1/announcements", headers=world["student"])).json()
    assert {a["title"] for a in student_view} == {"Campus closed Friday", "Quiz moved"}

    outsider_view = (await client.get("/api/v1/announcements", headers=world["outsider"])).json()
    assert {a["title"] for a in outsider_view} == {"Campus closed Friday"}


async def test_messages_and_announcements_emit_sync_changes(client, world):
    channel_id = (
        await client.get(f"/api/v1/courses/{world['course'].id}/channel", headers=world["student"])
    ).json()["id"]
    await client.post(
        f"/api/v1/channels/{channel_id}/messages",
        json={"body": "hello"},
        headers=world["student"],
    )
    await client.post(
        "/api/v1/announcements",
        json={"scope": "institution", "title": "T", "body": "B"},
        headers=world["admin"],
    )

    pull = (await client.get(CHANGES, headers=world["student"])).json()
    tables = {c["entity_table"] for c in pull["changes"]}
    assert {"messages", "announcements"} <= tables
