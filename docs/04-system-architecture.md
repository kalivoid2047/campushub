# CampusHub — System Architecture Document

**Document Phase:** 4 of 18
**Status:** Draft for Approval
**Version:** 1.0
**Date:** 2026-07-15

---

## 1. Overall Architecture

CampusHub follows a **modular, microservice-ready, offline-first** architecture. At MVP, backend modules are deployed as a single FastAPI application organized into isolated feature modules (modular monolith) so that any module can later be extracted into an independent service without a rewrite. The client is a single Flutter codebase applying Clean Architecture + Repository Pattern, with a local SQLite store as the primary data source and PostgreSQL (via the API) as the sync target.

```
┌─────────────────────────────────────────────────────────────────┐
│                         Flutter Client                          │
│   (Android / iOS / Windows / macOS / Linux / Web)                │
│   Presentation → Domain (UseCases) → Data (Repository) → SQLite  │
│                         ▲        │ Sync Engine                   │
└─────────────────────────┼────────┼───────────────────────────────┘
                           │        ▼
                     WebSocket   REST/HTTPS (JWT)
                           │        │
┌──────────────────────────▼────────▼──────────────────────────────┐
│                         API Gateway (NGINX)                      │
└──────────────────────────┬────────────────────────────────────────┘
                           │
┌──────────────────────────▼────────────────────────────────────────┐
│                     FastAPI Backend (Modular Monolith)            │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌──────┐│
│  │  IAM/     │ │ Resources │ │ Comms     │ │ Assignments│ │ ... ││
│  │  Tenancy  │ │  Module   │ │  Module   │ │  Module    │ │      ││
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘ └──────┘│
│  ┌───────────┐ ┌───────────┐ ┌───────────┐                       │
│  │ Virtual   │ │ Search    │ │ Admin/    │                       │
│  │ Classroom │ │  Module   │ │ Analytics │                       │
│  └───────────┘ └───────────┘ └───────────┘                       │
└───┬─────────────┬─────────────┬──────────────┬────────────────────┘
    │              │             │              │
┌───▼───┐     ┌────▼────┐   ┌────▼─────┐   ┌────▼──────┐
│Postgres│     │  Redis  │   │ MinIO/S3 │   │ WebRTC SFU│
│(system │     │(cache,  │   │ (object  │   │ (media    │
│of record)│   │ pub/sub,│   │ storage) │   │  routing) │
│        │     │ sessions)│   │          │   │           │
└────────┘     └─────────┘   └──────────┘   └───────────┘
```

## 2. Component Diagram

**Client-side components:**
- **Presentation layer** — Flutter widgets, Material 3, state management (feature-first folders).
- **Domain layer** — use cases / business logic, platform-agnostic.
- **Data layer** — repositories abstracting SQLite (offline) and REST/WebSocket (remote) data sources.
- **Sync Engine** — background service reconciling local SQLite changes with backend via a sync queue (Phase 9).

**Backend modules (each with its own router, service, repository layers):**
- IAM/Tenancy — auth, users, roles, tenant provisioning.
- Resources — course content upload/versioning/download.
- Communication — channels, DMs, announcements, WebSocket fan-out.
- Assignments — creation, submission, grading.
- Virtual Classroom — session lifecycle, signaling, recording metadata.
- Attendance — derived from Virtual Classroom + manual entry.
- Search — indexed query across permitted resources.
- Admin/Analytics — tenant configuration, usage dashboards, audit log.

**Shared infrastructure:**
- PostgreSQL — system of record, row-level tenant isolation.
- Redis — cache, pub/sub for WebSocket fan-out across backend instances, rate limiting, session/refresh-token blacklist.
- MinIO (dev) / S3-compatible (prod) — object storage for resources and recordings.
- WebRTC SFU + signaling service — real-time media routing for virtual classroom.
- NGINX — API gateway / reverse proxy / TLS termination / load balancing.

## 3. Deployment Diagram

> **Note (v1.1):** CampusHub does not use Docker, containers, or Kubernetes. All services run as native processes (see Phase 13 v2.0).

**Development:** FastAPI (uvicorn), PostgreSQL, Redis, and MinIO all run as natively installed local services on the developer machine; the SFU is added as a native binary when the Virtual Classroom module begins.

**Production:**
```
Internet → NGINX (native install, TLS via certbot) → Linux host(s)
              ├── uvicorn API workers (systemd: campushub-api.service, N workers)
              ├── WebSocket traffic on same API processes (scale-safe via Redis pub/sub)
              ├── WebRTC SFU (native binary on dedicated host, UDP-exposed)
              ├── Background worker (systemd: campushub-worker.service)
              ├── Managed/Native PostgreSQL (primary + replica)
              ├── Managed/Native Redis
              └── S3-compatible Object Storage (managed S3 or native MinIO)
CI/CD: GitHub Actions → build/test/scan → package wheel + Flutter artifacts → SSH deploy + systemd restart
```

## 4. Microservices / Modules Strategy

CampusHub ships at MVP as a **modular monolith** to reduce operational overhead for a solo developer, with strict internal boundaries (separate routers, services, repositories, and — where practical — separate schemas/tables per module) so that high-load modules (notably Virtual Classroom and Search) can be extracted into standalone services later without cross-module refactors. Extraction candidates, in priority order: (1) Virtual Classroom/Signaling, (2) Notification/Sync worker, (3) Search indexing.

## 5. Security Architecture

Summarized here; full detail in Phase 8.
- JWT access tokens (short-lived) + refresh tokens (rotated, stored hashed).
- RBAC enforced via FastAPI dependency injection at every route.
- Tenant ID embedded in JWT claims and enforced at the repository query layer (defense in depth: never trust client-supplied tenant IDs).
- TLS everywhere; encryption at rest for object storage and sensitive PostgreSQL columns.
- API Gateway enforces rate limiting and request validation before traffic reaches application code.

## 6. Data Flow (Representative: Assignment Submission)

1. Student drafts submission in Flutter client → written immediately to local SQLite with `sync_status = pending`.
2. Sync Engine detects connectivity → sends submission to `POST /assignments/{id}/submissions` with JWT.
3. API Gateway validates TLS/rate limits → routes to FastAPI Assignments module.
4. Backend validates RBAC + tenant scope → persists to PostgreSQL → uploads any attachment to S3/MinIO → publishes event to Redis pub/sub.
5. WebSocket service pushes real-time notification to the lecturer's connected clients.
6. Client receives ACK → updates local `sync_status = synced`.

## 7. API Gateway

NGINX serves as the single ingress point: TLS termination, routing to FastAPI/WebSocket backends, request size limits (for uploads), and basic rate limiting. Full request/response contract in Phase 6.

## 8. Caching Strategy

- Redis caches: user session/permission lookups, frequently-read resource metadata, search result pages, rate-limit counters.
- Cache invalidation: write-through on mutation of the underlying entity (resource update, role change) plus TTL as a safety net (see Phase 4 companion in Phase 6/9 for specifics).
- Client-side cache: SQLite acts as a durable, long-TTL cache for offline-first behavior, distinct from Redis's short-lived server-side cache.

## 9. Offline Synchronization (Architecture-Level Summary)

Each client maintains a local SQLite database mirroring the subset of tenant data relevant to the user. Mutations are appended to a local sync queue and replayed against the backend when connectivity is available, with server-side conflict detection via versioning. Full design in Phase 9.

## 10. Storage Strategy

- **Development:** MinIO native binary (S3-compatible API, local-disk-backed), or plain local filesystem storage in early development.
- **Production:** Any S3-compatible provider (AWS S3, or self-hosted MinIO cluster) behind the same API abstraction so the backend code is storage-provider-agnostic.
- Object keys are namespaced per-tenant (`/{tenant_id}/{module}/{resource_id}/...`) to reinforce isolation even at the storage layer.
- Presigned URLs used for direct client upload/download where appropriate, reducing backend bandwidth load.

---

*Next document: Phase 5 — Database Design Document.*
