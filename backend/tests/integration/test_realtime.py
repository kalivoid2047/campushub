"""WebSocket real-time layer tests (docs/06 section 7).

Covers: ticket issue/redeem (single-use), unauthenticated/forbidden socket
rejection, and live fan-out of a REST-sent message to a subscribed socket.

Uses Starlette's sync TestClient for WebSocket support; the app's DB access
inside the WS handshake is pointed at the test engine via monkeypatching
db.async_session_factory.
"""

import threading

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.core import db
from app.core.db import get_db_session
from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.admin.models import Course, CourseEnrollment, Department, EnrollmentRole
from app.modules.iam.models import Tenant, TenantStatus, User

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def world(session, session_factory, monkeypatch):
    tenant = Tenant(name="RT College", slug="rt-college", status=TenantStatus.ACTIVE)
    session.add(tenant)
    await session.flush()

    def _user(email: str) -> User:
        return User(
            tenant_id=tenant.id,
            email=email,
            password_hash=hash_password("password-123"),
            full_name=email.split("@")[0],
        )

    student, outsider = _user("stud@rt.edu"), _user("outsider@rt.edu")
    session.add_all([student, outsider])
    await session.flush()

    dept = Department(tenant_id=tenant.id, name="Eng", code="ENG")
    session.add(dept)
    await session.flush()
    course = Course(
        tenant_id=tenant.id,
        department_id=dept.id,
        name="Writing",
        code="ENG101",
        term="2026-F",
    )
    session.add(course)
    await session.flush()
    session.add(
        CourseEnrollment(course_id=course.id, user_id=student.id, role=EnrollmentRole.STUDENT)
    )
    await session.commit()

    # Point WS-handshake DB access and HTTP dependency at the test engine.
    monkeypatch.setattr(db, "async_session_factory", session_factory)

    async def _override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_db_session] = _override
    yield {
        "course": course,
        "student_token": create_access_token(
            user_id=student.id, tenant_id=tenant.id, roles=["student"]
        ),
        "outsider_token": create_access_token(
            user_id=outsider.id, tenant_id=tenant.id, roles=["student"]
        ),
    }
    app.dependency_overrides.clear()


def _sync_client() -> TestClient:
    return TestClient(app)


async def test_ticket_is_single_use_and_socket_authz(world):
    with _sync_client() as tc:
        headers = {"Authorization": f"Bearer {world['student_token']}"}
        channel_id = tc.get(
            f"/api/v1/courses/{world['course'].id}/channel", headers=headers
        ).json()["id"]

        # No/garbage ticket → rejected. The rejection surfaces as whatever
        # the underlying test-client websocket transport raises on a
        # failed handshake (its exact type isn't part of our contract —
        # only that the connection is refused), hence the broad catch;
        # kept as nested `with`s (not combined) since pytest.raises must
        # wrap the connect() call specifically, not the whole block.
        with pytest.raises(Exception):  # noqa: B017, SIM117
            with tc.websocket_connect(f"/api/v1/ws/channels/{channel_id}?ticket=junk"):
                pass

        # Outsider ticket → forbidden on a course channel they're not in.
        outsider_ticket = tc.post(
            "/api/v1/ws/ticket",
            headers={"Authorization": f"Bearer {world['outsider_token']}"},
        ).json()["ticket"]
        with pytest.raises(Exception):  # noqa: B017, SIM117
            with tc.websocket_connect(f"/api/v1/ws/channels/{channel_id}?ticket={outsider_ticket}"):
                pass

        # Valid ticket works once...
        ticket = tc.post("/api/v1/ws/ticket", headers=headers).json()["ticket"]
        with tc.websocket_connect(f"/api/v1/ws/channels/{channel_id}?ticket={ticket}"):
            pass
        # ...and is dead on reuse (single-use).
        with pytest.raises(Exception):  # noqa: B017, SIM117
            with tc.websocket_connect(f"/api/v1/ws/channels/{channel_id}?ticket={ticket}"):
                pass


async def test_rest_message_fans_out_to_socket(world):
    with _sync_client() as tc:
        headers = {"Authorization": f"Bearer {world['student_token']}"}
        channel_id = tc.get(
            f"/api/v1/courses/{world['course'].id}/channel", headers=headers
        ).json()["id"]
        ticket = tc.post("/api/v1/ws/ticket", headers=headers).json()["ticket"]

        with tc.websocket_connect(f"/api/v1/ws/channels/{channel_id}?ticket={ticket}") as socket:
            # Send via REST from a parallel thread (TestClient sockets block
            # the portal loop while receiving).
            def _send():
                tc.post(
                    f"/api/v1/channels/{channel_id}/messages",
                    json={"body": "realtime hello"},
                    headers=headers,
                )

            sender = threading.Thread(target=_send)
            sender.start()
            event = socket.receive_json()
            sender.join()

        assert event["type"] == "message.created"
        assert event["body"] == "realtime hello"
        assert event["channel_id"] == channel_id
