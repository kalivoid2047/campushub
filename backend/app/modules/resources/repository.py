"""Data access for the resources module.

Every query is tenant-scoped (docs/05-database-design.md section 1).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.resources.models import CourseModule, Resource, ResourceType, ResourceVersion


class ResourcesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Modules ---

    async def create_module(
        self, tenant_id: uuid.UUID, course_id: uuid.UUID, title: str, position: int
    ) -> CourseModule:
        module = CourseModule(
            tenant_id=tenant_id, course_id=course_id, title=title, position=position
        )
        self._session.add(module)
        await self._session.flush()
        return module

    async def get_module(self, tenant_id: uuid.UUID, module_id: uuid.UUID) -> CourseModule | None:
        result = await self._session.execute(
            select(CourseModule).where(
                CourseModule.id == module_id, CourseModule.tenant_id == tenant_id
            )
        )
        return result.scalar_one_or_none()

    async def list_modules(self, tenant_id: uuid.UUID, course_id: uuid.UUID) -> list[CourseModule]:
        result = await self._session.execute(
            select(CourseModule)
            .where(
                CourseModule.course_id == course_id,
                CourseModule.tenant_id == tenant_id,
            )
            .order_by(CourseModule.position, CourseModule.created_at)
        )
        return list(result.scalars())

    # --- Resources ---

    async def create_resource(
        self,
        tenant_id: uuid.UUID,
        module_id: uuid.UUID,
        title: str,
        type_: ResourceType,
    ) -> Resource:
        resource = Resource(tenant_id=tenant_id, module_id=module_id, title=title, type=type_)
        self._session.add(resource)
        await self._session.flush()
        return resource

    async def get_resource(
        self, tenant_id: uuid.UUID, resource_id: uuid.UUID, include_deleted: bool = False
    ) -> Resource | None:
        query = (
            select(Resource)
            .where(Resource.id == resource_id, Resource.tenant_id == tenant_id)
            .options(selectinload(Resource.versions), selectinload(Resource.module))
            # Refresh identity-mapped instances so a re-fetch after adding a
            # version sees the up-to-date versions collection.
            .execution_options(populate_existing=True)
        )
        if not include_deleted:
            query = query.where(Resource.deleted_at.is_(None))
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def list_resources(self, tenant_id: uuid.UUID, module_id: uuid.UUID) -> list[Resource]:
        result = await self._session.execute(
            select(Resource)
            .where(
                Resource.module_id == module_id,
                Resource.tenant_id == tenant_id,
                Resource.deleted_at.is_(None),
            )
            .options(selectinload(Resource.versions))
            .order_by(Resource.created_at)
        )
        return list(result.scalars())

    # --- Versions ---

    async def add_version(
        self,
        resource: Resource,
        storage_key: str,
        size_bytes: int,
        checksum: str,
        uploaded_by: uuid.UUID,
    ) -> ResourceVersion:
        next_number = max((v.version_number for v in resource.versions), default=0) + 1
        version = ResourceVersion(
            resource_id=resource.id,
            storage_key=storage_key,
            size_bytes=size_bytes,
            checksum=checksum,
            version_number=next_number,
            uploaded_by=uploaded_by,
        )
        self._session.add(version)
        await self._session.flush()
        resource.current_version_id = version.id
        await self._session.flush()
        return version

    def current_version(self, resource: Resource) -> ResourceVersion | None:
        for version in resource.versions:
            if version.id == resource.current_version_id:
                return version
        return None
