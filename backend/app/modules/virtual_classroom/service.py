"""Business logic for the virtual classroom module (Epic E5, lifecycle plane).

Session lifecycle: scheduled → live → ended (or cancelled). Join/leave
events automatically create/close attendance records (FR-VC-5/FR-ATT-1);
ending a session closes any open attendance windows. The WebRTC media plane
(docs/10) attaches behind /join without changing this contract.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from livekit import api as livekit_api
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import CurrentUser
from app.modules.admin.repository import AdminRepository
from app.modules.attendance.models import AttendanceRecord, AttendanceSource
from app.modules.sync.models import SyncOperation
from app.modules.sync.repository import SyncRepository
from app.modules.virtual_classroom.models import (
    ClassSession,
    RecordingStatus,
    SessionRecording,
    SessionStatus,
)
from app.modules.virtual_classroom.repository import VirtualClassroomRepository
from app.modules.virtual_classroom.schemas import CreateSessionRequest
from app.shared.audit import record_audit_event

_ADMIN_ROLES = {"dept_admin", "institution_admin", "super_admin"}

# Room-join tokens are short-lived: a client that doesn't connect promptly
# after /join must call it again rather than holding a long-lived media
# credential (docs/08-security-design.md §2 token-lifetime philosophy).
_LIVEKIT_TOKEN_TTL = timedelta(minutes=10)


@dataclass
class MediaJoinInfo:
    signaling_url: str | None
    sfu_token: str | None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class VirtualClassroomService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = VirtualClassroomRepository(session)
        self._admin_repo = AdminRepository(session)
        self._sync_repo = SyncRepository(session)

    async def create_session(
        self, user: CurrentUser, course_id: uuid.UUID, request: CreateSessionRequest
    ) -> ClassSession:
        await self._ensure_course_member(user, course_id, require_lecturer=True)
        class_session = await self._repo.create_session(
            tenant_id=user.tenant_id,
            course_id=course_id,
            title=request.title,
            scheduled_start=request.scheduled_start,
            scheduled_end=request.scheduled_end,
            created_by=user.user_id,
        )
        await self._emit(user, class_session)
        await self._session.commit()
        return class_session

    async def list_sessions(self, user: CurrentUser, course_id: uuid.UUID):
        await self._ensure_course_member(user, course_id)
        return await self._repo.list_sessions(user.tenant_id, course_id)

    async def start(self, user: CurrentUser, session_id: uuid.UUID) -> ClassSession:
        class_session = await self._get_checked(user, session_id, require_lecturer=True)
        if class_session.status != SessionStatus.SCHEDULED:
            raise HTTPException(status_code=422, detail="Session is not startable")
        class_session.status = SessionStatus.LIVE
        class_session.actual_start = _utcnow()
        await self._emit(user, class_session)
        await self._session.commit()
        return class_session

    async def end(self, user: CurrentUser, session_id: uuid.UUID) -> ClassSession:
        class_session = await self._get_checked(user, session_id, require_lecturer=True)
        if class_session.status != SessionStatus.LIVE:
            raise HTTPException(status_code=422, detail="Session is not live")
        now = _utcnow()
        class_session.status = SessionStatus.ENDED
        class_session.actual_end = now

        # Close any attendance windows still open (participants who never
        # sent an explicit leave).
        from sqlalchemy import select

        result = await self._session.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.class_session_id == class_session.id,
                AttendanceRecord.left_at.is_(None),
            )
        )
        for record in result.scalars():
            record.left_at = now
            joined_at = _aware(record.joined_at) or now
            record.duration_seconds = int((now - joined_at).total_seconds())

        await self._emit(user, class_session)
        await self._session.commit()
        return class_session

    async def join(
        self, user: CurrentUser, session_id: uuid.UUID
    ) -> tuple[ClassSession, AttendanceRecord, MediaJoinInfo]:
        class_session = await self._get_checked(user, session_id)
        if class_session.status != SessionStatus.LIVE:
            raise HTTPException(status_code=422, detail="Session is not live")

        record = await self._repo.get_attendance(class_session.id, user.user_id)
        now = _utcnow()
        if record is None:
            record = AttendanceRecord(
                class_session_id=class_session.id,
                user_id=user.user_id,
                joined_at=now,
                source=AttendanceSource.AUTO,
            )
            self._repo.add_attendance(record)
        elif record.left_at is not None:
            # Rejoin: reopen the window; total duration accumulates on leave.
            record.left_at = None
        await self._session.commit()

        media = self._media_join_info(user, class_session)
        return class_session, record, media

    def _media_join_info(self, user: CurrentUser, class_session: ClassSession) -> MediaJoinInfo:
        """Mints a LiveKit room-join token (docs/10-virtual-classroom.md).

        Returns signaling_url=None when LiveKit isn't configured (e.g. local
        dev without the SFU running) — attendance/lifecycle still work, the
        client just can't open the media connection.
        """
        settings = get_settings()
        if not (settings.livekit_url and settings.livekit_api_key and settings.livekit_api_secret):
            return MediaJoinInfo(signaling_url=None, sfu_token=None)

        token = (
            livekit_api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
            .with_identity(str(user.user_id))
            .with_name(str(user.user_id))
            .with_grants(
                livekit_api.VideoGrants(
                    room_join=True,
                    room=str(class_session.id),
                    can_publish=True,
                    can_subscribe=True,
                )
            )
            .with_ttl(_LIVEKIT_TOKEN_TTL)
            .to_jwt()
        )
        return MediaJoinInfo(signaling_url=settings.livekit_url, sfu_token=token)

    async def leave(self, user: CurrentUser, session_id: uuid.UUID) -> AttendanceRecord:
        class_session = await self._get_checked(user, session_id)
        record = await self._repo.get_attendance(class_session.id, user.user_id)
        if record is None or record.joined_at is None:
            raise HTTPException(status_code=422, detail="Not in this session")
        if record.left_at is None:
            now = _utcnow()
            record.left_at = now
            joined_at = _aware(record.joined_at) or now
            record.duration_seconds += int((now - joined_at).total_seconds())
            await self._session.commit()
        return record

    # --- Recording (Epic E5, manual lecturer-triggered start/stop) ---

    async def start_recording(self, user: CurrentUser, session_id: uuid.UUID) -> SessionRecording:
        class_session = await self._get_checked(user, session_id, require_lecturer=True)
        if class_session.status != SessionStatus.LIVE:
            raise HTTPException(status_code=422, detail="Session is not live")
        if await self._repo.get_active_recording(class_session.id) is not None:
            raise HTTPException(status_code=409, detail="A recording is already in progress")

        settings = get_settings()
        if not (settings.livekit_url and settings.livekit_api_key and settings.livekit_api_secret):
            raise HTTPException(
                status_code=422, detail="Recording is not configured for this server"
            )
        if not (settings.s3_endpoint_url and settings.s3_bucket):
            raise HTTPException(
                status_code=422, detail="Recording storage is not configured for this server"
            )

        storage_key = f"recordings/{user.tenant_id}/{class_session.id}/{uuid.uuid4()}.mp4"
        client = livekit_api.LiveKitAPI(
            settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret
        )
        try:
            info = await client.egress.start_room_composite_egress(
                livekit_api.RoomCompositeEgressRequest(
                    room_name=str(class_session.id),
                    layout="grid",
                    file_outputs=[
                        livekit_api.EncodedFileOutput(
                            file_type=livekit_api.EncodedFileType.MP4,
                            filepath=storage_key,
                            s3=livekit_api.S3Upload(
                                access_key=settings.s3_access_key or "",
                                secret=settings.s3_secret_key or "",
                                bucket=settings.s3_bucket,
                                endpoint=settings.s3_endpoint_url,
                                force_path_style=True,
                            ),
                        )
                    ],
                )
            )
        except Exception as error:  # LiveKit server unreachable/rejected the request
            raise HTTPException(
                status_code=502, detail=f"Failed to start recording: {error}"
            ) from None
        finally:
            await client.aclose()

        recording = await self._repo.create_recording(class_session.id, storage_key, info.egress_id)
        await record_audit_event(
            self._session,
            tenant_id=user.tenant_id,
            actor_id=user.user_id,
            action="recording.started",
            target_type="session_recording",
            target_id=recording.id,
            meta={"class_session_id": str(class_session.id)},
        )
        await self._session.commit()
        return recording

    async def stop_recording(self, user: CurrentUser, session_id: uuid.UUID) -> SessionRecording:
        class_session = await self._get_checked(user, session_id, require_lecturer=True)
        recording = await self._repo.get_active_recording(class_session.id)
        if recording is None:
            raise HTTPException(status_code=422, detail="No recording is in progress")

        settings = get_settings()
        client = livekit_api.LiveKitAPI(
            settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret
        )
        try:
            info = await client.egress.stop_egress(
                livekit_api.StopEgressRequest(egress_id=recording.egress_id)
            )
        except Exception as error:
            raise HTTPException(status_code=502, detail=f"Failed to stop recording: {error}") from None
        finally:
            await client.aclose()

        self._apply_egress_info(recording, info)
        await record_audit_event(
            self._session,
            tenant_id=user.tenant_id,
            actor_id=user.user_id,
            action="recording.stopped",
            target_type="session_recording",
            target_id=recording.id,
            meta={"class_session_id": str(class_session.id), "status": recording.status.value},
        )
        await self._session.commit()
        return recording

    async def list_recordings(
        self, user: CurrentUser, session_id: uuid.UUID
    ) -> list[SessionRecording]:
        class_session = await self._get_checked(user, session_id)
        recordings = await self._repo.list_recordings(class_session.id)

        # Best-effort reconciliation: LiveKit's egress completion lands
        # asynchronously and there's no webhook receiver here, so any
        # still-PROCESSING recording is polled against the Egress API on
        # read. A failure here just leaves the row PROCESSING for next time.
        pending = [r for r in recordings if r.status == RecordingStatus.PROCESSING]
        settings = get_settings()
        if pending and settings.livekit_url and settings.livekit_api_key and settings.livekit_api_secret:
            client = livekit_api.LiveKitAPI(
                settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret
            )
            try:
                for recording in pending:
                    response = await client.egress.list_egress(
                        livekit_api.ListEgressRequest(egress_id=recording.egress_id)
                    )
                    if response.items:
                        self._apply_egress_info(recording, response.items[0])
                await self._session.commit()
            except Exception:
                pass
            finally:
                await client.aclose()
        return recordings

    def _apply_egress_info(self, recording: SessionRecording, info) -> None:
        if info.status == livekit_api.EgressStatus.EGRESS_COMPLETE:
            recording.status = RecordingStatus.AVAILABLE
            if info.file_results:
                file_info = info.file_results[0]
                recording.size_bytes = file_info.size
                # LiveKit reports duration in nanoseconds.
                recording.duration_seconds = int(file_info.duration / 1_000_000_000)
        elif info.status in (
            livekit_api.EgressStatus.EGRESS_FAILED,
            livekit_api.EgressStatus.EGRESS_ABORTED,
        ):
            recording.status = RecordingStatus.FAILED
        # else: still STARTING/ACTIVE/ENDING — leave as PROCESSING.

    # --- Helpers ---

    async def _get_checked(
        self, user: CurrentUser, session_id: uuid.UUID, require_lecturer: bool = False
    ) -> ClassSession:
        class_session = await self._repo.get_session(user.tenant_id, session_id)
        if class_session is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        await self._ensure_course_member(
            user, class_session.course_id, require_lecturer=require_lecturer
        )
        return class_session

    async def _ensure_course_member(
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
        if require_lecturer and enrollment.role.value not in ("lecturer", "ta"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Lecturer role required for this course",
            )

    async def _emit(self, user: CurrentUser, class_session: ClassSession) -> None:
        await self._sync_repo.append_change(
            tenant_id=user.tenant_id,
            entity_table="class_sessions",
            entity_id=class_session.id,
            operation=SyncOperation.UPDATE if class_session.actual_start else SyncOperation.CREATE,
            payload={
                "course_id": str(class_session.course_id),
                "title": class_session.title,
                "status": class_session.status.value,
            },
            version=1,
            changed_by=user.user_id,
        )
