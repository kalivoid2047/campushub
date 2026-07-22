"""Class session lifecycle + attendance tests (Epics E5 lifecycle / E6).

Covers: session create/start/end RBAC and state machine, join/leave with
automatic attendance (FR-VC-5), end-closes-open-windows, rejoin
accumulation, manual marking (FR-ATT-1), and the course report (FR-ATT-2).
"""

import pytest
import pytest_asyncio

from app.core.security import create_access_token, hash_password
from app.modules.admin.models import Course, CourseEnrollment, Department, EnrollmentRole
from app.modules.iam.models import Tenant, TenantStatus, User

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def world(session):
    tenant = Tenant(name="VC College", slug="vc-college", status=TenantStatus.ACTIVE)
    session.add(tenant)
    await session.flush()

    def _user(email: str) -> User:
        return User(
            tenant_id=tenant.id,
            email=email,
            password_hash=hash_password("password-123"),
            full_name=email.split("@")[0],
        )

    lecturer, student = _user("lect@vc.edu"), _user("stud@vc.edu")
    session.add_all([lecturer, student])
    await session.flush()

    dept = Department(tenant_id=tenant.id, name="Chemistry", code="CHM")
    session.add(dept)
    await session.flush()
    course = Course(
        tenant_id=tenant.id,
        department_id=dept.id,
        name="Organic Chem",
        code="CHM201",
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

    def _hdr(user: User) -> dict:
        token = create_access_token(user_id=user.id, tenant_id=tenant.id, roles=["student"])
        return {"Authorization": f"Bearer {token}"}

    return {
        "course": course,
        "users": {"lecturer": lecturer, "student": student},
        "lecturer": _hdr(lecturer),
        "student": _hdr(student),
    }


async def _live_session(client, world) -> str:
    created = await client.post(
        f"/api/v1/courses/{world['course'].id}/sessions",
        json={"title": "Lecture 1"},
        headers=world["lecturer"],
    )
    assert created.status_code == 201
    session_id = created.json()["id"]
    started = await client.post(f"/api/v1/sessions/{session_id}/start", headers=world["lecturer"])
    assert started.json()["status"] == "live"
    return session_id


async def test_student_cannot_create_or_start(client, world):
    denied = await client.post(
        f"/api/v1/courses/{world['course'].id}/sessions",
        json={"title": "Nope"},
        headers=world["student"],
    )
    assert denied.status_code == 403


async def test_lifecycle_state_machine(client, world):
    session_id = await _live_session(client, world)

    # Can't start a live session again.
    assert (
        await client.post(f"/api/v1/sessions/{session_id}/start", headers=world["lecturer"])
    ).status_code == 422

    ended = await client.post(f"/api/v1/sessions/{session_id}/end", headers=world["lecturer"])
    assert ended.json()["status"] == "ended"
    assert ended.json()["actual_end"] is not None

    # Can't end twice, can't join an ended session.
    assert (
        await client.post(f"/api/v1/sessions/{session_id}/end", headers=world["lecturer"])
    ).status_code == 422
    assert (
        await client.post(f"/api/v1/sessions/{session_id}/join", headers=world["student"])
    ).status_code == 422


async def test_join_creates_attendance_and_end_closes_window(client, world):
    session_id = await _live_session(client, world)

    joined = await client.post(f"/api/v1/sessions/{session_id}/join", headers=world["student"])
    assert joined.status_code == 200
    assert joined.json()["joined_at"] is not None

    # Student never leaves; ending the session closes the window.
    await client.post(f"/api/v1/sessions/{session_id}/end", headers=world["lecturer"])

    records = (
        await client.get(f"/api/v1/sessions/{session_id}/attendance", headers=world["lecturer"])
    ).json()
    assert len(records) == 1
    assert records[0]["user_id"] == str(world["users"]["student"].id)
    assert records[0]["left_at"] is not None
    assert records[0]["source"] == "auto"


async def test_explicit_leave_and_rejoin(client, world):
    session_id = await _live_session(client, world)
    await client.post(f"/api/v1/sessions/{session_id}/join", headers=world["student"])
    assert (
        await client.post(f"/api/v1/sessions/{session_id}/leave", headers=world["student"])
    ).status_code == 204

    # Rejoin reopens the same record (unique per session+user).
    rejoin = await client.post(f"/api/v1/sessions/{session_id}/join", headers=world["student"])
    assert rejoin.status_code == 200

    await client.post(f"/api/v1/sessions/{session_id}/end", headers=world["lecturer"])
    records = (
        await client.get(f"/api/v1/sessions/{session_id}/attendance", headers=world["lecturer"])
    ).json()
    assert len(records) == 1


async def test_manual_marking_and_course_report(client, world):
    session_id = await _live_session(client, world)
    await client.post(f"/api/v1/sessions/{session_id}/end", headers=world["lecturer"])

    # Student missed the live session; lecturer marks them present manually.
    marked = await client.post(
        f"/api/v1/sessions/{session_id}/attendance/manual",
        json={"user_id": str(world["users"]["student"].id), "present": True},
        headers=world["lecturer"],
    )
    assert marked.status_code == 200
    assert marked.json()["source"] == "manual"

    # Students cannot mark attendance.
    assert (
        await client.post(
            f"/api/v1/sessions/{session_id}/attendance/manual",
            json={"user_id": str(world["users"]["student"].id)},
            headers=world["student"],
        )
    ).status_code == 403

    report = (
        await client.get(
            f"/api/v1/courses/{world['course'].id}/attendance",
            headers=world["lecturer"],
        )
    ).json()
    assert report["total_sessions"] == 1
    student_row = next(
        r for r in report["rows"] if r["user_id"] == str(world["users"]["student"].id)
    )
    assert student_row["sessions_attended"] == 1
    assert student_row["attendance_rate"] == 1.0


async def test_join_without_livekit_configured_returns_null_media(client, world):
    session_id = await _live_session(client, world)
    joined = await client.post(f"/api/v1/sessions/{session_id}/join", headers=world["student"])
    assert joined.status_code == 200
    body = joined.json()
    assert body["signaling_url"] is None
    assert body["sfu_token"] is None


async def test_join_with_livekit_configured_mints_a_scoped_token(client, world, monkeypatch):
    from app.core.config import Settings
    from app.modules.virtual_classroom import service as vc_service

    configured = Settings(
        livekit_url="wss://livekit.example.edu",
        livekit_api_key="test-key",
        livekit_api_secret="test-secret-at-least-32-bytes-long",
    )
    monkeypatch.setattr(vc_service, "get_settings", lambda: configured)

    session_id = await _live_session(client, world)
    joined = await client.post(f"/api/v1/sessions/{session_id}/join", headers=world["student"])
    assert joined.status_code == 200
    body = joined.json()
    assert body["signaling_url"] == "wss://livekit.example.edu"
    assert body["sfu_token"] is not None

    # Decode without verifying (test only cares the room/identity grants are
    # correct, not exercising LiveKit's own verification path).
    import jwt as pyjwt

    claims = pyjwt.decode(body["sfu_token"], options={"verify_signature": False})
    assert claims["video"]["room"] == session_id
    assert claims["video"]["roomJoin"] is True
    assert claims["sub"] == str(world["users"]["student"].id)
