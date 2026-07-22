# CampusHub

Multi-tenant, offline-first Digital Campus Platform. See [docs/00-implementation-roadmap.md](docs/00-implementation-roadmap.md) for the build sequence and [docs/](docs/) for the full planning and architecture documentation set (Phases 1–18).

**Note:** This project does not use Docker or containers. Development and production run natively (local PostgreSQL/Redis installs in dev; systemd-managed processes behind NGINX in production).

## Repository Layout

- `client/` — Flutter app (Android, iOS, Windows, macOS, Linux, Web)
- `backend/` — FastAPI application (modular monolith, see [docs/04-system-architecture.md](docs/04-system-architecture.md))
- `infra/` — NGINX and systemd configs for native production deployment
- `docs/` — Planning, architecture, and design documentation
- `scripts/` — Dev, CI, and ops helper scripts

## Getting Started (Development)

Prerequisites (installed natively on your machine):

- Python 3.12+
- PostgreSQL 16+ (running locally, with a `campushub` database/user)
- Redis 7+ (running locally)
- Flutter SDK (stable channel)
- MinIO server binary *(optional in early development — the storage layer falls back to local filesystem storage when S3 settings are absent)*

```bash
cp .env.example .env      # then edit values for your local setup
make install              # create venv + install backend deps
make migrate              # apply database migrations
make seed                 # seed dev fixture data
make run                  # start the API at http://localhost:8000
```

Then run the Flutter client against the local API:

```bash
cd client
flutter run --dart-define=API_BASE_URL=http://localhost:8000
```

See [docs/13-deployment-guide.md](docs/13-deployment-guide.md) for full environment setup and [docs/17-coding-standards.md](docs/17-coding-standards.md) before contributing.

## Status

Planning complete (Phases 1–18 + roadmap). **Backend MVP feature surface implemented** (68 passing tests, ruff/black clean):

- ✅ Foundation: schema + Alembic migrations (0001–0006, with Postgres RLS), JWT auth with refresh rotation, RBAC, tenant provisioning
- ✅ Sync core: idempotent `/sync/batch`, cursor-based `/sync/changes`, conflict detection, entity-handler registry — with two registered entities: `submissions` and `messages`
- ✅ Admin: departments, courses, enrollments, storage usage, audit logs, engagement analytics
- ✅ Resources: upload/versioning/download, quota enforcement, local/S3 storage abstraction
- ✅ Communication: course channels, DMs, offline-deduped messages (both REST and sync-queue paths), scoped announcements
- ✅ Assignments: draft→submit→grade lifecycle, late flagging, offline submissions via sync engine, grade audit logging
- ✅ Virtual classroom lifecycle + attendance (auto from join/leave, manual marking, course reports)
- ✅ **WebRTC media plane**: self-hosted [LiveKit](https://livekit.io) SFU (native binary, `infra/systemd/campushub-livekit.service` + `infra/livekit/livekit.yaml` — no containers). `POST /sessions/{id}/join` mints a short-lived (10-minute), per-participant, room-scoped LiveKit access token via `livekit-api`; null when LiveKit isn't configured, so lifecycle/attendance keep working without it
- ✅ Search: permission-scoped keyword search (resources/announcements/messages)
- ✅ Real-time: WebSocket tickets + live channel fan-out

**Flutter client in progress** (42 passing tests, analyze clean):

- ✅ Core: ApiClient (bearer + single 401-refresh-retry, presigned-URL fetch without leaking the bearer token), SecureStore abstraction, SQLite entity cache + sync queue + downloads table, push-then-pull SyncEngine, SyncScheduler (immediate + periodic + reconnect-triggered background sync)
- ✅ Auth: login screen, refresh rotation with theft-signal teardown, offline logout
- ✅ Courses → modules → resources browsing (network-first, offline cache fallback), announcements feed, sync-status chip + manual sync
- ✅ Assignments: list + submit sheet; offline submissions queue to sync_queue and drain through /sync/batch on reconnect (verified end-to-end contract match with the backend sync handler)
- ✅ Download manager: resource files downloaded to app-local storage for offline reading, staleness detection on server-side version change, works against both the local-storage content stream and S3 presigned URLs
- ✅ Messaging: course discussion channels + DMs, paginated message history, WebSocket ticket handshake with live message fan-out, tap-a-sender-to-DM — offline-capable: a message composed offline queues locally with an optimistic "Sending…" bubble and drains through /sync/batch on reconnect (known limitation: the optimistic item uses the client-generated id, not the eventual server id, so a rare duplicate can appear until the thread next refreshes)
- ✅ Search: debounced permission-scoped keyword search with tap-through to the relevant resource/message screen
- ✅ Virtual classroom + attendance: session list/create/start/end/join/leave, per-course attendance report, and now a **live call screen** (`livekit_client`) — "Join" opens a real audio/video call (mic/camera toggle, participant grid) when the backend's LiveKit server is configured, and falls back to an attendance-only confirmation when it isn't

Every planning-doc epic now has both a backend and a client implementation. Remaining known gaps: session recording (FR-VC-4, deferred — see docs/10-virtual-classroom.md §4), a course-member directory for starting DMs outside a shared channel, and exercising the Postgres RLS policies for real (dev tests run on SQLite; install PostgreSQL 16 locally and run `make migrate` to verify). See [docs/00-implementation-roadmap.md](docs/00-implementation-roadmap.md) for what's next.
