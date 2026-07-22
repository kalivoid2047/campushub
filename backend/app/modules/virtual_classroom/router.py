"""HTTP routes for the virtual classroom module (docs/06 section 6).

Mounted at /api/v1. Media-plane credentials (signaling_url/sfu_token) are
returned by /join, minted per-participant against LiveKit (docs/10). They
are null when the LiveKit server isn't configured — session lifecycle and
attendance still function without it.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.security import CurrentUser, get_current_user
from app.core.storage import get_storage
from app.modules.virtual_classroom.models import RecordingStatus
from app.modules.virtual_classroom.schemas import (
    CreateSessionRequest,
    JoinResponse,
    RecordingResponse,
    SessionResponse,
)
from app.modules.virtual_classroom.service import VirtualClassroomService

router = APIRouter()


def _service(session: AsyncSession = Depends(get_db_session)) -> VirtualClassroomService:
    return VirtualClassroomService(session)


def _recording_response(r) -> RecordingResponse:
    return RecordingResponse(
        id=r.id,
        status=r.status.value,
        duration_seconds=r.duration_seconds,
        size_bytes=r.size_bytes,
        created_at=r.created_at,
        download_url=(
            get_storage().presigned_url(r.storage_key)
            if r.status == RecordingStatus.AVAILABLE
            else None
        ),
    )


def _response(s) -> SessionResponse:
    return SessionResponse(
        id=s.id,
        course_id=s.course_id,
        title=s.title,
        status=s.status.value,
        scheduled_start=s.scheduled_start,
        scheduled_end=s.scheduled_end,
        actual_start=s.actual_start,
        actual_end=s.actual_end,
        created_by=s.created_by,
    )


@router.post(
    "/courses/{course_id}/sessions",
    response_model=SessionResponse,
    status_code=201,
    summary="Create a class session (lecturer)",
)
async def create_session(
    course_id: uuid.UUID,
    request: CreateSessionRequest,
    user: CurrentUser = Depends(get_current_user),
    service: VirtualClassroomService = Depends(_service),
) -> SessionResponse:
    return _response(await service.create_session(user, course_id, request))


@router.get(
    "/courses/{course_id}/sessions",
    response_model=list[SessionResponse],
    summary="List course sessions",
)
async def list_sessions(
    course_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    service: VirtualClassroomService = Depends(_service),
) -> list[SessionResponse]:
    return [_response(s) for s in await service.list_sessions(user, course_id)]


@router.post(
    "/sessions/{session_id}/start",
    response_model=SessionResponse,
    summary="Start a session (lecturer)",
)
async def start_session(
    session_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    service: VirtualClassroomService = Depends(_service),
) -> SessionResponse:
    return _response(await service.start(user, session_id))


@router.post(
    "/sessions/{session_id}/end",
    response_model=SessionResponse,
    summary="End a session (lecturer); closes open attendance windows",
)
async def end_session(
    session_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    service: VirtualClassroomService = Depends(_service),
) -> SessionResponse:
    return _response(await service.end(user, session_id))


@router.post(
    "/sessions/{session_id}/join",
    response_model=JoinResponse,
    summary="Join a live session (records attendance)",
)
async def join_session(
    session_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    service: VirtualClassroomService = Depends(_service),
) -> JoinResponse:
    _, record, media = await service.join(user, session_id)
    return JoinResponse(
        session_id=session_id,
        joined_at=record.joined_at,
        signaling_url=media.signaling_url,
        sfu_token=media.sfu_token,
    )


@router.post(
    "/sessions/{session_id}/leave",
    status_code=204,
    summary="Leave a session (closes the attendance window)",
)
async def leave_session(
    session_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    service: VirtualClassroomService = Depends(_service),
) -> None:
    await service.leave(user, session_id)


@router.post(
    "/sessions/{session_id}/recording/start",
    response_model=RecordingResponse,
    status_code=201,
    summary="Start recording a live session (lecturer)",
)
async def start_recording(
    session_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    service: VirtualClassroomService = Depends(_service),
) -> RecordingResponse:
    return _recording_response(await service.start_recording(user, session_id))


@router.post(
    "/sessions/{session_id}/recording/stop",
    response_model=RecordingResponse,
    summary="Stop the in-progress recording (lecturer)",
)
async def stop_recording(
    session_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    service: VirtualClassroomService = Depends(_service),
) -> RecordingResponse:
    return _recording_response(await service.stop_recording(user, session_id))


@router.get(
    "/sessions/{session_id}/recordings",
    response_model=list[RecordingResponse],
    summary="List recordings for a session",
)
async def list_recordings(
    session_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    service: VirtualClassroomService = Depends(_service),
) -> list[RecordingResponse]:
    return [_recording_response(r) for r in await service.list_recordings(user, session_id)]
