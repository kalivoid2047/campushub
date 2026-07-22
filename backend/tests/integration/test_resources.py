"""Resources module tests (Epic E2) + admin structure endpoints.

Covers docs/15-feature-backlog.md E2 acceptance: upload/versioning, listing,
download with checksum, RBAC (lecturer-only upload, enrollment-gated read),
tenant isolation, quota enforcement (BR-4), soft delete, and sync-change
emission for offline delta pull.
"""

import io
import uuid

import pytest
import pytest_asyncio

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.core.storage import reset_storage_for_tests
from app.modules.admin.models import CourseEnrollment, EnrollmentRole
from app.modules.iam.models import Tenant, TenantStatus, User

pytestmark = pytest.mark.asyncio

CHANGES = "/api/v1/sync/changes"


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
    """Tenant with admin/lecturer/student users; department+course built via API
    in the tests that need them."""
    tenant = Tenant(name="Res College", slug="res-college", status=TenantStatus.ACTIVE)
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
        _user("admin@res.edu"),
        _user("lect@res.edu"),
        _user("stud@res.edu"),
        _user("outsider@res.edu"),
    )
    session.add_all([admin, lecturer, student, outsider])
    await session.commit()

    def _token(user: User, roles: list[str]) -> dict:
        token = create_access_token(user_id=user.id, tenant_id=tenant.id, roles=roles)
        return {"Authorization": f"Bearer {token}"}

    return {
        "tenant": tenant,
        "users": {"admin": admin, "lecturer": lecturer, "student": student, "outsider": outsider},
        "admin": _token(admin, ["institution_admin"]),
        "lecturer": _token(lecturer, ["student"]),  # platform role; course role via enrollment
        "student": _token(student, ["student"]),
        "outsider": _token(outsider, ["student"]),
    }


async def _build_course(client, session, world) -> dict:
    dept = await client.post(
        "/api/v1/admin/departments",
        json={"name": "Computer Science", "code": "CS"},
        headers=world["admin"],
    )
    assert dept.status_code == 201
    course = await client.post(
        "/api/v1/admin/courses",
        json={
            "department_id": dept.json()["id"],
            "name": "Data Structures",
            "code": "CS201",
            "term": "2026-F",
        },
        headers=world["admin"],
    )
    assert course.status_code == 201
    course_id = course.json()["id"]

    for key, role in (("lecturer", EnrollmentRole.LECTURER), ("student", EnrollmentRole.STUDENT)):
        session.add(
            CourseEnrollment(
                course_id=uuid.UUID(course_id),
                user_id=world["users"][key].id,
                role=role,
            )
        )
    await session.commit()

    module = await client.post(
        f"/api/v1/courses/{course_id}/modules",
        json={"title": "Week 1", "position": 1},
        headers=world["lecturer"],
    )
    assert module.status_code == 201
    return {"course_id": course_id, "module_id": module.json()["id"]}


def _upload_kwargs(title="Lecture Notes", content=b"hello campus"):
    return {
        "data": {"title": title, "type": "document"},
        "files": {"file": ("notes.pdf", io.BytesIO(content), "application/pdf")},
    }


async def test_admin_structure_and_enrollment_flow(client, session, world):
    built = await _build_course(client, session, world)
    enroll = await client.post(
        f"/api/v1/admin/courses/{built['course_id']}/enrollments",
        json={"user_id": str(world["users"]["outsider"].id), "role": "student"},
        headers=world["admin"],
    )
    assert enroll.status_code == 201
    dup = await client.post(
        f"/api/v1/admin/courses/{built['course_id']}/enrollments",
        json={"user_id": str(world["users"]["outsider"].id), "role": "student"},
        headers=world["admin"],
    )
    assert dup.status_code == 409


async def test_structure_requires_admin_role(client, session, world):
    resp = await client.post(
        "/api/v1/admin/departments",
        json={"name": "X", "code": "X"},
        headers=world["student"],
    )
    assert resp.status_code == 403


async def test_upload_list_download_roundtrip(client, session, world):
    built = await _build_course(client, session, world)
    content = b"offline-first course material"

    up = await client.post(
        f"/api/v1/modules/{built['module_id']}/resources",
        **_upload_kwargs(content=content),
        headers=world["lecturer"],
    )
    assert up.status_code == 201
    resource = up.json()
    assert resource["current_version"]["version_number"] == 1
    assert resource["current_version"]["size_bytes"] == len(content)

    listing = await client.get(
        f"/api/v1/modules/{built['module_id']}/resources", headers=world["student"]
    )
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    download = await client.get(
        f"/api/v1/resources/{resource['id']}/download", headers=world["student"]
    )
    assert download.status_code == 200
    assert download.json()["inline"] is True  # local backend

    blob = await client.get(f"/api/v1/resources/{resource['id']}/content", headers=world["student"])
    assert blob.status_code == 200
    assert blob.content == content
    assert blob.headers["X-Checksum-Sha256"] == resource["current_version"]["checksum"]

    # download_count incremented by the /download call
    relist = await client.get(
        f"/api/v1/modules/{built['module_id']}/resources", headers=world["student"]
    )
    assert relist.json()[0]["download_count"] == 1


async def test_student_cannot_upload(client, session, world):
    built = await _build_course(client, session, world)
    resp = await client.post(
        f"/api/v1/modules/{built['module_id']}/resources",
        **_upload_kwargs(),
        headers=world["student"],
    )
    assert resp.status_code == 403


async def test_unenrolled_user_cannot_read(client, session, world):
    built = await _build_course(client, session, world)
    resp = await client.get(
        f"/api/v1/modules/{built['module_id']}/resources", headers=world["outsider"]
    )
    assert resp.status_code == 403


async def test_cross_tenant_module_is_404(client, session, world):
    built = await _build_course(client, session, world)
    other = create_access_token(
        user_id=uuid.uuid4(), tenant_id=uuid.uuid4(), roles=["institution_admin"]
    )
    resp = await client.get(
        f"/api/v1/modules/{built['module_id']}/resources",
        headers={"Authorization": f"Bearer {other}"},
    )
    assert resp.status_code == 404  # not 403 — never confirm existence (docs/08)


async def test_new_version_supersedes(client, session, world):
    built = await _build_course(client, session, world)
    up = await client.post(
        f"/api/v1/modules/{built['module_id']}/resources",
        **_upload_kwargs(content=b"v1"),
        headers=world["lecturer"],
    )
    resource_id = up.json()["id"]

    v2 = await client.post(
        f"/api/v1/resources/{resource_id}/versions",
        files={"file": ("notes2.pdf", io.BytesIO(b"v2 content"), "application/pdf")},
        headers=world["lecturer"],
    )
    assert v2.status_code == 201
    assert v2.json()["current_version"]["version_number"] == 2

    blob = await client.get(f"/api/v1/resources/{resource_id}/content", headers=world["student"])
    assert blob.content == b"v2 content"


async def test_quota_enforced(client, session, world):
    built = await _build_course(client, session, world)
    world["tenant"].storage_quota_bytes = 10  # tiny quota
    await session.commit()

    resp = await client.post(
        f"/api/v1/modules/{built['module_id']}/resources",
        **_upload_kwargs(content=b"this payload exceeds ten bytes"),
        headers=world["lecturer"],
    )
    assert resp.status_code == 413
    assert "quota" in resp.json()["detail"].lower()


async def test_soft_delete_and_sync_changes(client, session, world):
    built = await _build_course(client, session, world)
    up = await client.post(
        f"/api/v1/modules/{built['module_id']}/resources",
        **_upload_kwargs(),
        headers=world["lecturer"],
    )
    resource_id = up.json()["id"]

    delete = await client.delete(f"/api/v1/resources/{resource_id}", headers=world["lecturer"])
    assert delete.status_code == 204

    listing = await client.get(
        f"/api/v1/modules/{built['module_id']}/resources", headers=world["student"]
    )
    assert listing.json() == []

    # Offline clients see the full lifecycle via delta pull.
    pull = (await client.get(CHANGES, headers=world["student"])).json()
    ops = [(c["entity_table"], c["operation"]) for c in pull["changes"]]
    assert ("resources", "create") in ops
    assert ("resources", "delete") in ops
