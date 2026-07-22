"""HTTP routes for the resources module (docs/06-api-design.md section 6).

Mounted at /api/v1. Upload is multipart in development (local storage);
the S3 presigned-upload flow slots in behind the same service layer later.
"""

import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.security import CurrentUser, get_current_user
from app.modules.resources.repository import ResourcesRepository
from app.modules.resources.schemas import (
    CreateModuleRequest,
    DownloadResponse,
    ModuleResponse,
    ResourceResponse,
    ResourceVersionResponse,
)
from app.modules.resources.service import ResourcesService

router = APIRouter()


def _service(session: AsyncSession = Depends(get_db_session)) -> ResourcesService:
    return ResourcesService(session)


def _to_resource_response(resource, repo: ResourcesRepository) -> ResourceResponse:
    version = repo.current_version(resource)
    return ResourceResponse(
        id=resource.id,
        module_id=resource.module_id,
        title=resource.title,
        type=resource.type.value,
        download_count=resource.download_count,
        current_version=(ResourceVersionResponse.model_validate(version) if version else None),
        created_at=resource.created_at,
        updated_at=resource.updated_at,
    )


@router.post(
    "/courses/{course_id}/modules",
    response_model=ModuleResponse,
    status_code=201,
    summary="Create a content module in a course",
)
async def create_module(
    course_id: uuid.UUID,
    request: CreateModuleRequest,
    user: CurrentUser = Depends(get_current_user),
    service: ResourcesService = Depends(_service),
) -> ModuleResponse:
    return await service.create_module(user, course_id, request)


@router.get(
    "/courses/{course_id}/modules",
    response_model=list[ModuleResponse],
    summary="List modules in a course",
)
async def list_modules(
    course_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    service: ResourcesService = Depends(_service),
) -> list[ModuleResponse]:
    return await service.list_modules(user, course_id)


@router.post(
    "/modules/{module_id}/resources",
    response_model=ResourceResponse,
    status_code=201,
    summary="Upload a resource to a module",
)
async def upload_resource(
    module_id: uuid.UUID,
    title: str = Form(min_length=1, max_length=300),
    type: str = Form(pattern="^(document|slide|video|link)$"),
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    service: ResourcesService = Depends(_service),
    session: AsyncSession = Depends(get_db_session),
) -> ResourceResponse:
    data = await file.read()
    resource, _ = await service.upload_resource(user, module_id, title, type, data)
    return _to_resource_response(resource, ResourcesRepository(session))


@router.post(
    "/resources/{resource_id}/versions",
    response_model=ResourceResponse,
    status_code=201,
    summary="Upload a new version of an existing resource",
)
async def add_version(
    resource_id: uuid.UUID,
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    service: ResourcesService = Depends(_service),
    session: AsyncSession = Depends(get_db_session),
) -> ResourceResponse:
    data = await file.read()
    resource, _ = await service.add_version(user, resource_id, data)
    return _to_resource_response(resource, ResourcesRepository(session))


@router.get(
    "/modules/{module_id}/resources",
    response_model=list[ResourceResponse],
    summary="List resources in a module",
)
async def list_resources(
    module_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    service: ResourcesService = Depends(_service),
    session: AsyncSession = Depends(get_db_session),
) -> list[ResourceResponse]:
    repo = ResourcesRepository(session)
    resources = await service.list_resources(user, module_id)
    return [_to_resource_response(r, repo) for r in resources]


@router.get(
    "/resources/{resource_id}/download",
    response_model=DownloadResponse,
    summary="Get a download URL (S3) or inline indicator (local storage)",
)
async def get_download(
    resource_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    service: ResourcesService = Depends(_service),
) -> DownloadResponse:
    version, url = await service.get_download(user, resource_id)
    return DownloadResponse(
        download_url=url,
        inline=url is None,
        size_bytes=version.size_bytes,
        checksum=version.checksum,
    )


@router.get(
    "/resources/{resource_id}/content",
    summary="Stream resource bytes (local-storage deployments)",
)
async def read_content(
    resource_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    service: ResourcesService = Depends(_service),
) -> Response:
    version, data = await service.read_content(user, resource_id)
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"X-Checksum-Sha256": version.checksum},
    )


@router.delete(
    "/resources/{resource_id}",
    status_code=204,
    summary="Soft-delete a resource",
)
async def delete_resource(
    resource_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    service: ResourcesService = Depends(_service),
) -> None:
    await service.soft_delete(user, resource_id)
