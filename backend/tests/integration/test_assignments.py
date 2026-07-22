"""Assignments module tests (Epic E4).

Covers: creation RBAC, draft→submit lifecycle, late flagging (BR-5),
no-late rejection, grading with max_score check + audit log (BR-3),
grade lock, and the submissions sync handler (offline path, FR-ASG-2).
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core.security import create_access_token, hash_password
from app.modules.admin.models import (
    AuditLog,
    Course,
    CourseEnrollment,
    Department,
    EnrollmentRole,
)
from app.modules.iam.models import Tenant, TenantStatus, User

pytestmark = pytest.mark.asyncio

BATCH = "/api/v1/sync/batch"


@pytest_asyncio.fixture
async def world(session):
    tenant = Tenant(name="Asg College", slug="asg-college", status=TenantStatus.ACTIVE)
    session.add(tenant)
    await session.flush()

    def _user(email: str) -> User:
        return User(
            tenant_id=tenant.id,
            email=email,
            password_hash=hash_password("password-123"),
            full_name=email.split("@")[0],
        )

    lecturer, student, other_student = (
        _user("lect@asg.edu"),
        _user("stud@asg.edu"),
        _user("stud2@asg.edu"),
    )
    session.add_all([lecturer, student, other_student])
    await session.flush()

    dept = Department(tenant_id=tenant.id, name="Math", code="MTH")
    session.add(dept)
    await session.flush()
    course = Course(
        tenant_id=tenant.id,
        department_id=dept.id,
        name="Calculus",
        code="MTH101",
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
            CourseEnrollment(
                course_id=course.id, user_id=other_student.id, role=EnrollmentRole.STUDENT
            ),
        ]
    )
    await session.commit()

    def _hdr(user: User, roles=("student",)) -> dict:
        token = create_access_token(user_id=user.id, tenant_id=tenant.id, roles=list(roles))
        return {"Authorization": f"Bearer {token}"}

    return {
        "tenant": tenant,
        "course": course,
        "users": {"lecturer": lecturer, "student": student, "other": other_student},
        "lecturer": _hdr(lecturer),
        "student": _hdr(student),
        "other": _hdr(other_student),
    }


async def _create_assignment(client, world, **overrides) -> dict:
    payload = {"title": "Problem Set 1", "instructions": "Solve.", "max_score": 50}
    payload.update(overrides)
    resp = await client.post(
        f"/api/v1/courses/{world['course'].id}/assignments",
        json=payload,
        headers=world["lecturer"],
    )
    assert resp.status_code == 201
    return resp.json()


async def test_student_cannot_create_assignment(client, world):
    resp = await client.post(
        f"/api/v1/courses/{world['course'].id}/assignments",
        json={"title": "Nope"},
        headers=world["student"],
    )
    assert resp.status_code == 403


async def test_draft_then_submit_lifecycle(client, world):
    assignment = await _create_assignment(client, world)

    draft = await client.post(
        f"/api/v1/assignments/{assignment['id']}/submissions",
        json={"content": {"text": "wip"}, "finalize": False},
        headers=world["student"],
    )
    assert draft.status_code == 201
    assert draft.json()["status"] == "draft"
    assert draft.json()["submitted_at"] is None

    final = await client.post(
        f"/api/v1/assignments/{assignment['id']}/submissions",
        json={"content": {"text": "done"}, "finalize": True},
        headers=world["student"],
    )
    assert final.json()["status"] == "submitted"
    assert final.json()["version"] == 2  # updated the same submission

    mine = await client.get(
        f"/api/v1/assignments/{assignment['id']}/submissions/me",
        headers=world["student"],
    )
    assert mine.json()["content"] == {"text": "done"}


async def test_late_submission_flagged(client, world):
    past_due = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    assignment = await _create_assignment(client, world, due_at=past_due)
    resp = await client.post(
        f"/api/v1/assignments/{assignment['id']}/submissions",
        json={"content": {"text": "sorry"}, "finalize": True},
        headers=world["student"],
    )
    assert resp.json()["status"] == "late"  # BR-5: flagged, not blocked


async def test_late_rejected_when_disallowed(client, world):
    past_due = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    assignment = await _create_assignment(client, world, due_at=past_due, allow_late=False)
    resp = await client.post(
        f"/api/v1/assignments/{assignment['id']}/submissions",
        json={"content": {}, "finalize": True},
        headers=world["student"],
    )
    assert resp.status_code == 422


async def test_grading_flow_with_audit_log(client, session, world):
    assignment = await _create_assignment(client, world, max_score=50)
    submission = (
        await client.post(
            f"/api/v1/assignments/{assignment['id']}/submissions",
            json={"content": {"text": "answer"}},
            headers=world["student"],
        )
    ).json()

    # Student cannot grade; lecturer over max_score rejected.
    assert (
        await client.patch(
            f"/api/v1/submissions/{submission['id']}/grade",
            json={"score": 40},
            headers=world["student"],
        )
    ).status_code == 403
    assert (
        await client.patch(
            f"/api/v1/submissions/{submission['id']}/grade",
            json={"score": 51},
            headers=world["lecturer"],
        )
    ).status_code == 422

    graded = await client.patch(
        f"/api/v1/submissions/{submission['id']}/grade",
        json={"score": 45, "feedback": "Good work"},
        headers=world["lecturer"],
    )
    assert graded.status_code == 200
    assert graded.json()["score"] == 45

    # Grade lock: regrade and post-grade resubmission both rejected.
    assert (
        await client.patch(
            f"/api/v1/submissions/{submission['id']}/grade",
            json={"score": 10},
            headers=world["lecturer"],
        )
    ).status_code == 409
    assert (
        await client.post(
            f"/api/v1/assignments/{assignment['id']}/submissions",
            json={"content": {"text": "changed my mind"}},
            headers=world["student"],
        )
    ).status_code == 422

    # BR-3: grade write is audit-logged.
    logs = (
        (await session.execute(select(AuditLog).where(AuditLog.action == "grade.created")))
        .scalars()
        .all()
    )
    assert len(logs) == 1
    assert logs[0].meta["score"] == 45


async def test_lecturer_sees_all_submissions_students_do_not(client, world):
    assignment = await _create_assignment(client, world)
    for who in ("student", "other"):
        await client.post(
            f"/api/v1/assignments/{assignment['id']}/submissions",
            json={"content": {"who": who}},
            headers=world[who],
        )

    all_subs = await client.get(
        f"/api/v1/assignments/{assignment['id']}/submissions",
        headers=world["lecturer"],
    )
    assert all_subs.status_code == 200
    assert len(all_subs.json()) == 2

    denied = await client.get(
        f"/api/v1/assignments/{assignment['id']}/submissions",
        headers=world["student"],
    )
    assert denied.status_code == 403


async def test_offline_submission_via_sync_engine(client, world):
    assignment = await _create_assignment(client, world)

    item = {
        "client_id": str(uuid.uuid4()),
        "entity_table": "submissions",
        "entity_id": str(uuid.uuid4()),
        "operation": "create",
        "payload": {
            "assignment_id": assignment["id"],
            "content": {"text": "written on a bus with no signal"},
            "finalize": True,
        },
        "base_version": None,
    }
    resp = await client.post(BATCH, json={"items": [item]}, headers=world["student"])
    result = resp.json()["results"][0]
    assert result["status"] == "applied"

    # Replay (lost ACK) is idempotent.
    replay = await client.post(BATCH, json={"items": [item]}, headers=world["student"])
    assert replay.json()["results"][0] == result

    mine = await client.get(
        f"/api/v1/assignments/{assignment['id']}/submissions/me",
        headers=world["student"],
    )
    assert mine.json()["status"] == "submitted"
    assert mine.json()["content"]["text"] == "written on a bus with no signal"


async def test_offline_conflict_reports_server_state(client, world):
    assignment = await _create_assignment(client, world)
    # Online submit first (version becomes 1).
    await client.post(
        f"/api/v1/assignments/{assignment['id']}/submissions",
        json={"content": {"text": "online v1"}, "finalize": False},
        headers=world["student"],
    )
    # Second device edits online again (version 2).
    await client.post(
        f"/api/v1/assignments/{assignment['id']}/submissions",
        json={"content": {"text": "online v2"}, "finalize": False},
        headers=world["student"],
    )

    stale = {
        "client_id": str(uuid.uuid4()),
        "entity_table": "submissions",
        "entity_id": str(uuid.uuid4()),
        "operation": "update",
        "payload": {
            "assignment_id": assignment["id"],
            "content": {"text": "offline edit of v1"},
            "finalize": False,
        },
        "base_version": 1,  # stale — server is at 2
    }
    resp = await client.post(BATCH, json={"items": [stale]}, headers=world["student"])
    result = resp.json()["results"][0]
    assert result["status"] == "conflict"
    assert result["server_version"] == 2
    assert result["server_payload"]["content"] == {"text": "online v2"}
