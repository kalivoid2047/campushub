# CampusHub — Virtual Classroom Design

**Document Phase:** 10 of 18
**Status:** Draft for Approval
**Version:** 1.0
**Date:** 2026-07-15

---

> **Implementation note (added post-selection):** the SFU is **LiveKit**,
> self-hosted as a single native binary (no containers, consistent with the
> project's native-install policy — see `infra/systemd/campushub-livekit.service`
> and `infra/livekit/livekit.yaml`). Chosen over mediasoup (a library, not a
> turnkey server — more integration work) and Janus/Jitsi (heavier plugin or
> stack coupling) for the strongest Flutter SDK (`livekit_client`) and
> lowest integration cost for a solo-developer timeline. The backend mints
> short-lived (10-minute) room-join tokens per participant via `livekit-api`
> in `VirtualClassroomService._media_join_info` — see `POST /sessions/{id}/join`.
> Recording (section 4 below) is not yet implemented; session lifecycle,
> attendance, and live audio/video/screen-share are.

## 1. Video Architecture

CampusHub uses a **Selective Forwarding Unit (SFU)** model rather than mesh or MCU, chosen for scalability (mesh degrades quickly beyond ~4 participants; MCU costs server-side transcoding CPU that doesn't suit a solo-developer-run platform):

```
Participant Clients (Flutter, WebRTC) ──ICE/DTLS/SRTP──> SFU (LiveKit, self-hosted native binary)
                                                              │
                                                     selectively forwards
                                                     each participant's stream
                                                     to every other participant
                                                              │
                                                     Signaling handled by LiveKit itself
                                                     (client connects directly to LiveKit's
                                                     wss:// endpoint using a token minted by
                                                     the backend — no custom signaling relay)
```

- Signaling: the backend does **not** relay WebRTC signaling itself — the Flutter client connects directly to LiveKit's `wss://` endpoint (returned as `signaling_url` from `POST /sessions/{id}/join`) using a per-participant token (`sfu_token`) that LiveKit's own client SDK uses to complete the room-join handshake, offer/answer, and ICE exchange. This is simpler than the originally-planned custom `/ws/sessions/{id}/signaling` relay and is the standard LiveKit integration pattern.
- TURN: LiveKit has built-in TURN support (`turn` config block in `livekit.yaml`) for participants behind restrictive NATs/firewalls (common on institutional networks) — configure this before production use; not enabled in the default dev config.
- The SFU runs as its own native process (`infra/systemd/campushub-livekit.service`) on a host with UDP ports exposed, isolated from the general API compute pool.

## 2. Screen Sharing

- Implemented as an additional WebRTC media track (`getDisplayMedia` equivalent via Flutter WebRTC plugin) published alongside camera/mic, tagged with a `track_type: screen` metadata attribute so clients can render it full-size distinctly from camera tiles.
- Only one active screen-share per session at MVP (simplifies UI and bandwidth budgeting); presenter role required to start a share.

## 3. Attendance

- The signaling service emits `participant_joined`/`participant_left` events (with timestamps) to the Attendance module, which writes `attendance_records` (Phase 5 §3.16) automatically, computing `duration_seconds`.
- A configurable minimum-duration threshold (default 5 minutes) determines whether a join counts as "attended" vs. a brief connection blip, avoiding false attendance from failed join attempts.
- Manual override/marking remains available to lecturers for in-person or edge-case sessions (FR-ATT-1).

## 4. Recording

- Recording is performed server-side by a dedicated **Recording Worker** that subscribes to the SFU as a passive participant (not client-side, to guarantee consistent output regardless of participant device performance) and composites the active speaker/screen-share view.
- Recorded output is written directly to object storage (MinIO/S3) via streaming upload; `session_recordings.status` transitions `processing → available` once the worker finalizes and validates the file.
- Recording start/stop is explicit and lecturer-controlled; a visible on-screen indicator is shown to all participants for consent/awareness while recording is active (privacy/compliance requirement, ties into Phase 8 audit logging).

## 5. Chat

- In-session chat reuses the existing Communication module's channel/message infrastructure (Phase 5 §3.10): each `class_session` has an associated ephemeral `channel` scoped to session participants, so no separate chat subsystem is built.
- Session chat history is retained and viewable post-session by enrolled course members, consistent with the course's discussion history.

## 6. Whiteboard

- Marked **Could-have (C)** per Phase 2 FR-VC-7 — deferred past MVP. Recommended future implementation: a lightweight vector-based shared canvas synced via the existing WebSocket signaling channel (operational-transform or simple last-writer-wins per stroke, given low collaborative-conflict stakes), rendered client-side with Flutter's `CustomPainter`. Not required for GA.

## 7. Bandwidth Optimization

- Adaptive bitrate/simulcast: clients publish multiple quality layers where device/network permits; the SFU forwards the appropriate layer per receiver based on their measured downlink (directly supports NFR-9 low-data-usage goal and the platform's low-bandwidth target users).
- Audio-only fallback mode: clients on severely constrained connections can join with video disabled entirely, reducing bandwidth by an order of magnitude while preserving participation.
- Video tile resolution scales down automatically as participant count grows (grid layout requests lower-resolution layers for non-focused tiles).
- Screen-share track is prioritized over camera tracks in bandwidth allocation, since content legibility matters more than face video during teaching.

## 8. Recording Storage

- Recordings are stored in the same tenant-namespaced object storage bucket structure as resources (`/{tenant_id}/recordings/{session_id}/...`), inheriting the same encryption-at-rest, backup, and quota-accounting mechanisms defined in Phase 8 and Phase 5.
- Recording file size counts against the tenant's storage quota (`storage_quotas`), with admins able to configure automatic recording expiration/archival policy (e.g., auto-delete after 180 days) to manage storage cost — configurable per institution, off by default (manual deletion) to avoid unexpected data loss.
- Playback is served via presigned, time-limited URLs identical to the resource download pattern (Phase 6 §6), never via direct public bucket access.

---

*Next document: Phase 11 — AI Module.*
