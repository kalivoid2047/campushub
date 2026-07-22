# CampusHub — API Design

**Document Phase:** 6 of 18
**Status:** Draft for Approval
**Version:** 1.0
**Date:** 2026-07-15

---

## 1. Conventions

- Base URL: `https://{tenant-slug}.campushub.app/api/v1` (or `/api/v1` with tenant resolved from JWT/subdomain in single-domain deployments).
- All requests/responses are JSON (`application/json`), UTF-8.
- All timestamps are ISO 8601 UTC.
- Resource IDs are UUIDs (strings).
- Versioning via URL path (`/api/v1`); breaking changes require `/api/v2`.

## 2. Authentication Flow

1. `POST /auth/login` `{email, password}` → `{access_token, refresh_token, expires_in}`.
2. Client stores `access_token` in memory, `refresh_token` in secure storage (Keychain/Keystore/DPAPI-backed secure storage per platform).
3. Every request carries `Authorization: Bearer {access_token}`.
4. On 401 with `token_expired`, client calls `POST /auth/refresh` `{refresh_token}` → new token pair (refresh token rotated; old one invalidated).
5. `POST /auth/logout` invalidates the current refresh token (added to Redis blacklist until natural expiry).
6. Offline: client validates cached JWT locally against stored expiry/signature-derived offline session per Phase 9; no network call required until reconnect.

## 3. Standard Response Envelope

```json
{
  "data": { },
  "meta": { "request_id": "uuid" },
  "errors": null
}
```

Error response:
```json
{
  "data": null,
  "meta": { "request_id": "uuid" },
  "errors": [
    { "code": "VALIDATION_ERROR", "field": "email", "message": "Invalid email format" }
  ]
}
```

## 4. Error Handling Standards

| HTTP Status | Meaning |
|---|---|
| 400 | Validation error (body includes `errors[]` with field-level detail) |
| 401 | Missing/invalid/expired token |
| 403 | Authenticated but not authorized (RBAC/tenant scope failure) |
| 404 | Resource not found (or exists in another tenant — never distinguish, to avoid tenant enumeration) |
| 409 | Conflict (e.g., sync version mismatch, duplicate submission) |
| 413 | Payload too large (upload exceeds quota/limit) |
| 422 | Semantically invalid (e.g., grading score exceeds max) |
| 429 | Rate limited |
| 500 | Unhandled server error (logged with `request_id` for correlation) |

Error codes are stable, machine-readable strings (`VALIDATION_ERROR`, `TENANT_MISMATCH`, `QUOTA_EXCEEDED`, `SYNC_CONFLICT`, etc.) documented in the OpenAPI spec's `components.schemas.ErrorCode` enum.

## 5. Pagination, Filtering, Sorting, Searching

- **Pagination:** cursor-based — `GET /resources?limit=25&cursor={opaque}` → response `meta.next_cursor`. Cursor-based chosen over offset for stability under concurrent writes and offline-sync-friendly incremental fetch.
- **Filtering:** query params per resource, e.g. `GET /assignments?course_id=...&status=submitted`.
- **Sorting:** `?sort=-created_at` (`-` prefix = descending).
- **Searching:** `GET /search?q=...&scope=course:{id}` — see Search module contract below.

## 6. REST Endpoints (Representative Set)

### Auth
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`

### Tenancy & Users
- `POST /admin/tenants` (super admin)
- `GET /admin/tenants/{id}`
- `POST /admin/departments`
- `POST /admin/courses`
- `POST /admin/users` (invite/create)
- `GET /users/me`
- `PATCH /users/me`

### Resources
- `POST /courses/{course_id}/modules`
- `POST /modules/{module_id}/resources` (multipart or presigned-URL flow)
- `GET /modules/{module_id}/resources`
- `GET /resources/{id}` / `GET /resources/{id}/versions`
- `GET /resources/{id}/download` → presigned URL

### Communication
- `GET/POST /channels/{id}/messages`
- `POST /announcements`
- `GET /announcements?scope=course:{id}`
- WebSocket: `wss://.../ws/channels/{id}` for live messages

### Assignments
- `POST /courses/{course_id}/assignments`
- `GET /assignments/{id}`
- `POST /assignments/{id}/submissions` (idempotent via `client_id`)
- `PATCH /submissions/{id}/grade`

### Virtual Classroom
- `POST /courses/{course_id}/sessions`
- `POST /sessions/{id}/start` / `POST /sessions/{id}/end`
- `POST /sessions/{id}/join` → returns WebRTC signaling token + SFU connection info
- `GET /sessions/{id}/recording`
- WebSocket: `wss://.../ws/sessions/{id}/signaling`

### Attendance
- `GET /courses/{course_id}/attendance`
- `POST /sessions/{id}/attendance/manual`

### Search
- `GET /search?q=...&scope=...`

### Admin/Analytics
- `GET /admin/analytics/engagement?course_id=...`
- `GET /admin/storage/usage`
- `GET /admin/audit-logs`

### Sync (Offline Engine Support)
- `POST /sync/batch` — accepts an array of queued client mutations with `client_id`/`version`, returns per-item success/conflict.
- `GET /sync/changes?since={cursor}` — delta pull of server-side changes since last sync checkpoint.

## 7. WebSocket Endpoints

| Endpoint | Purpose |
|---|---|
| `/ws/channels/{id}` | Real-time message delivery for a discussion channel/DM |
| `/ws/sessions/{id}/signaling` | WebRTC offer/answer/ICE candidate exchange for virtual classroom |
| `/ws/notifications` | User-scoped push channel for announcements, grade updates, sync events |

All WebSocket connections authenticate via a short-lived ticket obtained from `POST /ws/ticket` (avoids exposing long-lived JWTs in WS handshake query strings) and are tenant-scoped identically to REST.

## 8. OpenAPI Specification

FastAPI auto-generates the OpenAPI 3.1 schema (`/api/v1/openapi.json`) directly from route type hints and Pydantic models — this is the source of truth and is kept in sync with code by construction. Documentation conventions:
- Every route has a `summary`, `description`, `tags` (module name), and explicit `response_model`.
- Every request/response Pydantic model has field-level descriptions.
- Auth requirements declared via FastAPI `Security` dependencies, surfaced automatically in the spec's `security` blocks.
- The generated spec is published at `/docs` (Swagger UI) and `/redoc` in non-production environments only; disabled or access-restricted in production per Phase 8.

---

*Next document: Phase 7 — UI/UX Documentation.*
