# CampusHub — Complete Feature Backlog

**Document Phase:** 15 of 18
**Status:** Draft for Approval
**Version:** 1.0
**Date:** 2026-07-15

---

Complexity scale: **S** (< 1 day), **M** (1–3 days), **L** (3–7 days), **XL** (> 1 week, should be split further before starting).

## Epic E1 — Identity & Multi-Tenancy (P0)

| Feature | User Story | Tasks | Dependencies | Priority | Complexity |
|---|---|---|---|---|---|
| Tenant provisioning | Super admin creates a new institution | Task: tenant CRUD API; Task: tenant slug/routing resolution; Task: RLS policy scaffold | DB schema (Phase 5) | Must | L |
| User auth | User logs in/refreshes/logs out | Task: password hashing; Task: JWT issuance; Task: refresh rotation + Redis blacklist | Tenant provisioning | Must | M |
| RBAC enforcement | Any role-gated action is blocked/allowed correctly | Task: role/permission model; Task: FastAPI dependency guards; Task: object-level scope checks | User auth | Must | L |
| Offline auth artifact | User unlocks app offline | Task: signed offline session issuance; Task: client-side signature verification; Task: expiry/degraded-mode handling | User auth | Must | M |

## Epic E2 — Learning Resources (P0)

| Feature | User Story | Tasks | Dependencies | Priority | Complexity |
|---|---|---|---|---|---|
| Resource upload | Lecturer uploads course content | Task: presigned upload flow; Task: version tracking; Task: module organization | Tenant/Auth | Must | L |
| Resource browsing | Student browses module resources | Task: paginated listing API; Task: client resource list UI | Resource upload | Must | M |
| Offline download | Student downloads for offline use | Task: download manager (client); Task: presigned download URL API; Task: checksum verify | Resource browsing, Sync engine | Must | L |

## Epic E9 — Offline Synchronization Engine (P0)

| Feature | User Story | Tasks | Dependencies | Priority | Complexity |
|---|---|---|---|---|---|
| Local SQLite mirror | Client stores permission-scoped data locally | Task: schema mirroring; Task: repository abstraction (local/remote) | Auth | Must | XL (split: per-entity mirror tasks) |
| Sync queue | Offline mutations queue and replay | Task: `sync_queue` table; Task: batch push API (`/sync/batch`); Task: idempotency via `client_id` | Local SQLite mirror | Must | L |
| Conflict resolution | Conflicting edits are resolved per policy | Task: version comparison logic; Task: conflict UI surfacing | Sync queue | Must | M |
| Delta pull sync | Client fetches server-side changes since last sync | Task: `/sync/changes` endpoint; Task: cursor-based change tracking | Sync queue | Must | M |

## Epic E3 — Communication (P1)

| Feature | User Story | Tasks | Dependencies | Priority | Complexity |
|---|---|---|---|---|---|
| Course discussion channels | Students/lecturers discuss course topics | Task: channel/message schema; Task: REST + WebSocket delivery | Auth, Sync engine | Must | L |
| Direct messages | Users message each other | Task: DM channel type; Task: message list UI | Discussion channels | Must | M |
| Announcements | Lecturer/admin broadcasts updates | Task: announcement CRUD; Task: scope-based delivery (course/dept/institution) | Auth | Must | M |
| Offline message queueing | Message sent offline delivers on reconnect | Task: integrate messages into sync queue | Communication, Sync engine | Must | M |

## Epic E4 — Assignments & Grading (P1)

| Feature | User Story | Tasks | Dependencies | Priority | Complexity |
|---|---|---|---|---|---|
| Assignment creation | Lecturer creates assignment | Task: assignment CRUD API; Task: due-date/late-policy logic | Resources | Must | M |
| Offline submission | Student submits, incl. offline | Task: submission schema + client draft flow; Task: sync queue integration; Task: late-flag trigger | Assignment creation, Sync engine | Must | L |
| Grading | Lecturer grades and gives feedback | Task: grading API; Task: rubric support; Task: grading UI | Offline submission | Must | L |

## Epic E8 — Admin & Analytics (P1, basic scope)

| Feature | User Story | Tasks | Dependencies | Priority | Complexity |
|---|---|---|---|---|---|
| Department/course management | Admin manages structure | Task: department/course CRUD; Task: bulk enrollment import | Tenant provisioning | Must | M |
| Storage quota dashboard | Admin monitors storage | Task: quota tracking trigger (Phase 5 §8); Task: usage dashboard UI | Resources | Must | M |
| Basic engagement analytics | Admin views usage stats | Task: `v_course_engagement` view; Task: analytics API + dashboard | Resources, Communication, Assignments | Should | M |
| Audit log viewer | Admin reviews sensitive actions | Task: audit log write hooks across modules; Task: audit viewer UI | All P0/P1 modules | Must | M |

## Epic E5 — Virtual Classroom (P2)

| Feature | User Story | Tasks | Dependencies | Priority | Complexity |
|---|---|---|---|---|---|
| Session scheduling/start | Lecturer creates/starts a session | Task: session CRUD; Task: signaling service scaffold | Auth | Must | L |
| Live video/audio | Participants join a call | Task: SFU deployment; Task: client WebRTC integration | Session scheduling | Must | XL (split: signaling, media negotiation, UI) |
| Screen sharing | Presenter shares screen | Task: display-media track publish; Task: UI tile handling | Live video/audio | Must | M |
| Session chat | In-session text chat | Task: ephemeral session channel (reuse E3) | Communication, Live video/audio | Should | S |
| Recording | Session is recorded | Task: recording worker; Task: storage integration; Task: consent indicator | Live video/audio | Should | L |

## Epic E6 — Attendance (P2)

| Feature | User Story | Tasks | Dependencies | Priority | Complexity |
|---|---|---|---|---|---|
| Automatic attendance | Attendance recorded from session join/leave | Task: join/leave event handling; Task: minimum-duration threshold logic | Virtual Classroom | Must | M |
| Manual attendance | Lecturer marks attendance manually | Task: manual entry API + UI | Attendance schema | Should | S |
| Attendance reporting | Lecturer views attendance per course | Task: reporting view/API + UI | Automatic attendance | Should | M |

## Epic E7 — Search (P3)

| Feature | User Story | Tasks | Dependencies | Priority | Complexity |
|---|---|---|---|---|---|
| Keyword search | Search across resources/discussions | Task: indexed search API (Postgres full-text initially); Task: search UI | Resources, Communication | Should | M |
| Natural-language/semantic search | AI-assisted search | Task: vector index; Task: LLM gateway; Task: NL query parsing | AI Module (Phase 11) | Could | XL |

## Epic E10 — Academic Portfolio (P3)

| Feature | User Story | Tasks | Dependencies | Priority | Complexity |
|---|---|---|---|---|---|
| Portfolio view | Student views completed courses/grades | Task: portfolio aggregation API; Task: portfolio UI | Grading, Enrollment | Should | M |
| Portfolio export | Student exports portfolio | Task: PDF/export generation | Portfolio view | Could | S |

## Post-GA / Future Backlog (Phase 18 pointer)

AI Module features (Phase 11), Digital Student ID, QR Attendance, Timetable, Internship Management, Research Repository, Library Management, Payments, Alumni Portal, Marketplace — tracked as epics in the future-expansion backlog, not detailed here (see Phase 18).

---

*Next document: Phase 16 — Folder Structure.*
