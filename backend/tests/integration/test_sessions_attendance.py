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


def _configured_settings(**overrides):
    from app.core.config import Settings

    return Settings(
        livekit_url="wss://livekit.example.edu",
        livekit_api_key="test-key",
        livekit_api_secret="test-secret-at-least-32-bytes-long",
        s3_endpoint_url="http://minio.example.edu:9000",
        s3_bucket="recordings",
        **overrides,
    )


class _FakeEgress:
    """Stands in for LiveKit's Egress service (no real SFU in tests)."""

    def __init__(self):
        self.stopped_ids: list[str] = []

    async def start_room_composite_egress(self, request):
        import livekit.api as lk

        return lk.EgressInfo(egress_id="EG_fake123", status=lk.EgressStatus.EGRESS_ACTIVE)

    async def stop_egress(self, request):
        import livekit.api as lk

        self.stopped_ids.append(request.egress_id)
        return lk.EgressInfo(
            egress_id=request.egress_id,
            status=lk.EgressStatus.EGRESS_COMPLETE,
            file_results=[lk.FileInfo(size=12345, duration=90_000_000_000)],  # 90s, in ns
        )

    async def list_egress(self, request):
        import livekit.api as lk

        return lk.ListEgressResponse(
            items=[
                lk.EgressInfo(
                    egress_id=request.egress_id,
                    status=lk.EgressStatus.EGRESS_COMPLETE,
                    file_results=[lk.FileInfo(size=999, duration=5_000_000_000)],  # 5s
                )
            ]
        )


class _FakeLiveKitAPI:
    def __init__(self, *args, **kwargs):
        self.egress = _FakeEgress()

    async def aclose(self):
        pass


def _patch_livekit(monkeypatch, settings):
    from app.modules.virtual_classroom import service as vc_service

    monkeypatch.setattr(vc_service, "get_settings", lambda: settings)
    monkeypatch.setattr(vc_service.livekit_api, "LiveKitAPI", _FakeLiveKitAPI)


async def test_recording_requires_livekit_and_storage_configured(client, world):
    session_id = await _live_session(client, world)
    resp = await client.post(
        f"/api/v1/sessions/{session_id}/recording/start", headers=world["lecturer"]
    )
    assert resp.status_code == 422


async def test_recording_requires_lecturer(client, world, monkeypatch):
    _patch_livekit(monkeypatch, _configured_settings())
    session_id = await _live_session(client, world)
    resp = await client.post(
        f"/api/v1/sessions/{session_id}/recording/start", headers=world["student"]
    )
    assert resp.status_code == 403


async def test_recording_start_stop_lifecycle(client, world, monkeypatch):
    _patch_livekit(monkeypatch, _configured_settings())
    session_id = await _live_session(client, world)

    started = await client.post(
        f"/api/v1/sessions/{session_id}/recording/start", headers=world["lecturer"]
    )
    assert started.status_code == 201
    assert started.json()["status"] == "processing"

    # A second start while one is already active is rejected.
    conflict = await client.post(
        f"/api/v1/sessions/{session_id}/recording/start", headers=world["lecturer"]
    )
    assert conflict.status_code == 409

    stopped = await client.post(
        f"/api/v1/sessions/{session_id}/recording/stop", headers=world["lecturer"]
    )
    assert stopped.status_code == 200
    body = stopped.json()
    assert body["status"] == "available"
    assert body["duration_seconds"] == 90
    assert body["size_bytes"] == 12345

    # Nothing left in progress to stop.
    assert (
        await client.post(
            f"/api/v1/sessions/{session_id}/recording/stop", headers=world["lecturer"]
        )
    ).status_code == 422


async def test_list_recordings_reconciles_processing_status(client, world, monkeypatch):
    _patch_livekit(monkeypatch, _configured_settings())
    session_id = await _live_session(client, world)
    await client.post(
        f"/api/v1/sessions/{session_id}/recording/start", headers=world["lecturer"]
    )

    # Listing (not stopping) also reconciles against the Egress API, so a
    # recording that finished on LiveKit's side shows up as available even
    # if nobody called /recording/stop.
    listed = await client.get(
        f"/api/v1/sessions/{session_id}/recordings", headers=world["student"]
    )
    assert listed.status_code == 200
    [recording] = listed.json()
    assert recording["status"] == "available"
    assert recording["duration_seconds"] == 5
    assert recording["size_bytes"] == 999


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
