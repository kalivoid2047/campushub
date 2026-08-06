"""Business logic for the resources module.

Implements Epic E2 (docs/15-feature-backlog.md): upload/versioning, listing,
download, quota enforcement (docs/05 section 3.19, BR-4), and change-log
emission so offline clients receive resource deltas on pull sync
(docs/09 section 4).

Authorization model (docs/08 section 7): admins operate tenant-wide;
lecturers upload to courses they teach; any enrolled user reads.
"""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import CurrentUser
from app.core.storage import get_storage, sha256_hex
from app.modules.admin.models import EnrollmentRole
from app.modules.admin.repository import AdminRepository
from app.modules.resources.content_validation import matches_declared_type
from app.modules.resources.models import Resource, ResourceType, ResourceVersion
from app.modules.resources.repository import ResourcesRepository
from app.modules.resources.schemas import CreateModuleRequest
from app.modules.sync.models import SyncOperation
from app.modules.sync.repository import SyncRepository

_ADMIN_ROLES = {"dept_admin", "institution_admin", "super_admin"}

# Default per-file cap; tenant quota is the aggregate cap (docs/08 section 6).
MAX_FILE_BYTES = 500 * 1024 * 1024


class ResourcesService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ResourcesRepository(session)
        self._admin_repo = AdminRepository(session)
        self._sync_repo = SyncRepository(session)

    # --- Modules ---

    async def create_module(
        self, user: CurrentUser, course_id: uuid.UUID, request: CreateModuleRequest
    ):
        await self._ensure_course_access(user, course_id, require_lecturer=True)
        module = await self._repo.create_module(
            user.tenant_id, course_id, request.title, request.position
        )
        await self._session.commit()
        return module

    async def list_modules(self, user: CurrentUser, course_id: uuid.UUID):
        await self._ensure_course_access(user, course_id)
        return await self._repo.list_modules(user.tenant_id, course_id)

    # --- Resources ---

    async def upload_resource(
        self,
        user: CurrentUser,
        module_id: uuid.UUID,
        title: str,
        type_: str,
        data: bytes,
    ) -> tuple[Resource, ResourceVersion]:
        module = await self._get_module_or_404(user, module_id)
        await self._ensure_course_access(user, module.course_id, require_lecturer=True)

        resource = await self._repo.create_resource(
            user.tenant_id, module_id, title, ResourceType(type_)
        )
        # Re-fetch with versions/module eager-loaded before storing the first
        # version, so no lazy-load fires outside the async context.
        resource = await self._repo.get_resource(user.tenant_id, resource.id)
        version = await self._store_version(user, resource, data)
        await self._emit_change(user, resource, SyncOperation.CREATE)
        await self._session.commit()
        resource = await self._repo.get_resource(user.tenant_id, resource.id)
        return resource, version

    async def add_version(
        self, user: CurrentUser, resource_id: uuid.UUID, data: bytes
    ) -> tuple[Resource, ResourceVersion]:
        resource = await self._get_resource_or_404(user, resource_id)
        await self._ensure_course_access(user, resource.module.course_id, require_lecturer=True)
        version = await self._store_version(user, resource, data)
        await self._emit_change(user, resource, SyncOperation.UPDATE)
        await self._session.commit()
        resource = await self._repo.get_resource(user.tenant_id, resource.id)
        return resource, version

    async def list_resources(self, user: CurrentUser, module_id: uuid.UUID):
        module = await self._get_module_or_404(user, module_id)
        await self._ensure_course_access(user, module.course_id)
        return await self._repo.list_resources(user.tenant_id, module_id)

    async def get_download(self, user: CurrentUser, resource_id: uuid.UUID):
        resource = await self._get_resource_or_404(user, resource_id)
        await self._ensure_course_access(user, resource.module.course_id)
        version = self._repo.current_version(resource)
        if version is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No file uploaded")
        resource.download_count += 1
        await self._session.commit()
        url = get_storage().presigned_url(version.storage_key)
        return version, url

    async def read_content(
        self, user: CurrentUser, resource_id: uuid.UUID
    ) -> tuple[ResourceVersion, bytes]:
        resource = await self._get_resource_or_404(user, resource_id)
        await self._ensure_course_access(user, resource.module.course_id)
        version = self._repo.current_version(resource)
        if version is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No file uploaded")
        data = await get_storage().read(version.storage_key)
        return version, data

    async def soft_delete(self, user: CurrentUser, resource_id: uuid.UUID) -> None:
        resource = await self._get_resource_or_404(user, resource_id)
        await self._ensure_course_access(user, resource.module.course_id, require_lecturer=True)
        resource.deleted_at = datetime.now(UTC)
        # Release quota for all versions of the deleted resource.
        quota = await self._admin_repo.get_or_create_quota(user.tenant_id)
        quota.used_bytes = max(0, quota.used_bytes - sum(v.size_bytes for v in resource.versions))
        await self._emit_change(user, resource, SyncOperation.DELETE)
        await self._session.commit()

    # --- Helpers ---

    async def _store_version(
        self, user: CurrentUser, resource: Resource, data: bytes
    ) -> ResourceVersion:
        if len(data) == 0:
            raise HTTPException(status_code=422, detail="Empty file")
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail="File exceeds size limit")

        quota = await self._admin_repo.get_or_create_quota(user.tenant_id)
        if quota.used_bytes + len(data) > quota.quota_bytes:
            raise HTTPException(status_code=413, detail="Institution storage quota exceeded")

        # Signature check independent of the client-supplied filename/
        # Content-Type (docs/08 section 6) — both are attacker-controlled.
        if not matches_declared_type(resource.type, data):
            raise HTTPException(
                status_code=422, detail="File content does not match the declared resource type"
            )

        # Randomized, tenant-namespaced key — never the client filename
        # (docs/08 section 6).
        storage_key = f"{user.tenant_id}/resources/{resource.id}/{uuid.uuid4().hex}"
        await get_storage().save(storage_key, data)
        version = await self._repo.add_version(
            resource=resource,
            storage_key=storage_key,
            size_bytes=len(data),
            checksum=sha256_hex(data),
            uploaded_by=user.user_id,
        )
        quota.used_bytes += len(data)
        await self._session.flush()
        return version

    async def _emit_change(
        self, user: CurrentUser, resource: Resource, operation: SyncOperation
    ) -> None:
        version = self._repo.current_version(resource)
        payload = {}
        if operation != SyncOperation.DELETE:
            payload = {
                "title": resource.title,
                "type": resource.type.value,
                "module_id": str(resource.module_id),
                "version_number": version.version_number if version else 0,
                "size_bytes": version.size_bytes if version else 0,
                "checksum": version.checksum if version else "",
            }
        await self._sync_repo.append_change(
            tenant_id=user.tenant_id,
            entity_table="resources",
            entity_id=resource.id,
            operation=operation,
            payload=payload,
            version=version.version_number if version else 1,
            changed_by=user.user_id,
        )

    async def _get_module_or_404(self, user: CurrentUser, module_id: uuid.UUID):
        module = await self._repo.get_module(user.tenant_id, module_id)
        if module is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")
        return module

    async def _get_resource_or_404(self, user: CurrentUser, resource_id: uuid.UUID) -> Resource:
        resource = await self._repo.get_resource(user.tenant_id, resource_id)
        if resource is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
        return resource

    async def _ensure_course_access(
        self, user: CurrentUser, course_id: uuid.UUID, require_lecturer: bool = False
    ) -> None:
        course = await self._admin_repo.get_course(user.tenant_id, course_id)
        if course is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        if user.has_any_role(*_ADMIN_ROLES):
            return
        enrollment = await self._admin_repo.get_enrollment(course_id, user.user_id)
        if enrollment is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not enrolled in course"
            )
        if require_lecturer and enrollment.role not in (
            EnrollmentRole.LECTURER,
            EnrollmentRole.TA,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Lecturer role required for this course",
            )
