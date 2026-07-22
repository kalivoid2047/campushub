"""Offline message sync handler tests (FR-COM-4, docs/09).

Covers: happy-path create via /sync/batch, idempotent replay, course-channel
enrollment gating, DM membership gating, unknown channel, invalid payload,
and that the message shows up through the ordinary REST history endpoint
(proving the handler and the REST path agree on what a "message" is).
"""

import uuid

import pytest
import pytest_asyncio

from app.core.security import create_access_token, hash_password
from app.modules.admin.models import Course, CourseEnrollment, Department, EnrollmentRole
from app.modules.iam.models import Tenant, TenantStatus, User

pytestmark = pytest.mark.asyncio

BATCH = "/api/v1/sync/batch"


@pytest_asyncio.fixture
async def world(session):
    tenant = Tenant(name="Sync Comm College", slug="sync-comm", status=TenantStatus.ACTIVE)
    session.add(tenant)
    await session.flush()

    def _user(email: str) -> User:
        return User(
            tenant_id=tenant.id,
            email=email,
            password_hash=hash_password("password-123"),
            full_name=email.split("@")[0],
        )

    student, outsider, other = (
        _user("stud@sync.edu"),
        _user("outsider@sync.edu"),
        _user("other@sync.edu"),
    )
    session.add_all([student, outsider, other])
    await session.flush()

    dept = Department(tenant_id=tenant.id, name="Art", code="ART")
    session.add(dept)
    await session.flush()
    course = Course(
        tenant_id=tenant.id,
        department_id=dept.id,
        name="Painting",
        code="ART101",
        term="2026-F",
    )
    session.add(course)
    await session.flush()
    session.add(
        CourseEnrollment(course_id=course.id, user_id=student.id, role=EnrollmentRole.STUDENT)
    )
    await session.commit()

    def _hdr(user: User) -> dict:
        token = create_access_token(user_id=user.id, tenant_id=tenant.id, roles=["student"])
        return {"Authorization": f"Bearer {token}"}

    return {
        "course": course,
        "users": {"student": student, "outsider": outsider, "other": other},
        "student": _hdr(student),
        "outsider": _hdr(outsider),
        "other": _hdr(other),
    }


def _item(channel_id, body="hello", client_id=None):
    return {
        "client_id": str(client_id or uuid.uuid4()),
        "entity_table": "messages",
        "entity_id": str(uuid.uuid4()),
        "operation": "create",
        "payload": {"channel_id": str(channel_id), "body": body},
        "base_version": None,
    }


async def test_offline_message_applies_and_appears_in_history(client, world):
    channel_id = (
        await client.get(f"/api/v1/courses/{world['course'].id}/channel", headers=world["student"])
    ).json()["id"]

    item = _item(channel_id, body="written on the bus")
    resp = await client.post(BATCH, json={"items": [item]}, headers=world["student"])
    result = resp.json()["results"][0]
    assert result["status"] == "applied"

    history = (
        await client.get(f"/api/v1/channels/{channel_id}/messages", headers=world["student"])
    ).json()
    assert history["messages"][0]["body"] == "written on the bus"


async def test_replay_is_idempotent(client, world):
    channel_id = (
        await client.get(f"/api/v1/courses/{world['course'].id}/channel", headers=world["student"])
    ).json()["id"]
    item = _item(channel_id)

    first = await client.post(BATCH, json={"items": [item]}, headers=world["student"])
    replay = await client.post(BATCH, json={"items": [item]}, headers=world["student"])
    assert first.json()["results"][0] == replay.json()["results"][0]

    history = (
        await client.get(f"/api/v1/channels/{channel_id}/messages", headers=world["student"])
    ).json()
    assert len(history["messages"]) == 1


async def test_unenrolled_user_is_rejected(client, world):
    channel_id = (
        await client.get(f"/api/v1/courses/{world['course'].id}/channel", headers=world["student"])
    ).json()["id"]

    resp = await client.post(BATCH, json={"items": [_item(channel_id)]}, headers=world["outsider"])
    result = resp.json()["results"][0]
    assert result["status"] == "error"
    assert result["error_code"] == "FORBIDDEN"


async def test_unknown_channel_is_rejected(client, world):
    resp = await client.post(BATCH, json={"items": [_item(uuid.uuid4())]}, headers=world["student"])
    result = resp.json()["results"][0]
    assert result["status"] == "error"
    assert result["error_code"] == "NOT_FOUND"


async def test_empty_body_is_rejected(client, world):
    channel_id = (
        await client.get(f"/api/v1/courses/{world['course'].id}/channel", headers=world["student"])
    ).json()["id"]
    resp = await client.post(
        BATCH, json={"items": [_item(channel_id, body="   ")]}, headers=world["student"]
    )
    result = resp.json()["results"][0]
    assert result["status"] == "error"
    assert result["error_code"] == "INVALID_PAYLOAD"


async def test_dm_membership_gating(client, world):
    dm = await client.post(
        "/api/v1/channels/dm",
        json={"recipient_id": str(world["users"]["outsider"].id)},
        headers=world["student"],
    )
    channel_id = dm.json()["id"]

    # Either party in the DM can send.
    ok = await client.post(BATCH, json={"items": [_item(channel_id)]}, headers=world["student"])
    assert ok.json()["results"][0]["status"] == "applied"

    # A third party with no membership in this DM is rejected.
    denied = await client.post(BATCH, json={"items": [_item(channel_id)]}, headers=world["other"])
    result = denied.json()["results"][0]
    assert result["status"] == "error"
    assert result["error_code"] == "FORBIDDEN"
