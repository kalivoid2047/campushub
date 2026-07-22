# CampusHub — Software Requirements Specification (IEEE 830)

**Document Phase:** 2 of 18
**Status:** Draft for Approval
**Version:** 1.0
**Date:** 2026-07-15

---

## 1. Introduction

### 1.1 Purpose
This document specifies the functional and non-functional requirements of CampusHub, a multi-tenant, offline-first Digital Campus Platform. It is intended for the development team (currently a solo developer using AI-assisted tooling), and any future contributors, as the authoritative requirements baseline.

### 1.2 Scope
CampusHub provides learning resource management, communication, virtual classrooms, assignment/grading workflows, attendance tracking, and administrative tenant management for colleges and universities, across Android, iOS, Windows, macOS, Linux, and Web, with offline-first operation. See Phase 1 §7 for detailed in/out-of-scope items.

### 1.3 Definitions, Acronyms, Abbreviations

| Term | Definition |
|---|---|
| Tenant | An isolated institution instance within the shared CampusHub system |
| RBAC | Role-Based Access Control |
| SFU | Selective Forwarding Unit (WebRTC media routing) |
| JWT | JSON Web Token |
| MVP | Minimum Viable Product |
| Offline-first | Architecture where local data/actions are primary and remote sync is secondary/eventual |
| CRDT | Conflict-free Replicated Data Type (potential conflict-resolution technique) |
| LMS | Learning Management System |

### 1.4 References
- Phase 1: Project Charter
- IEEE Std 830-1998, Recommended Practice for Software Requirements Specifications
- OWASP Application Security Verification Standard (referenced in Phase 8)

## 2. Overall Description

### 2.1 Product Perspective
CampusHub is a new, standalone, multi-tenant SaaS-capable product. It is not an extension of an existing system. It consists of a Flutter client (all platforms), a FastAPI backend, PostgreSQL as the system of record, SQLite for on-device offline storage, Redis for caching/session/pub-sub, MinIO/S3 for object storage, and WebRTC for real-time video.

### 2.2 Product Functions (Summary)
- Institution, department, and user management (multi-tenant)
- Learning resource publishing, browsing, and offline download
- Discussion, messaging, and announcements
- Assignment creation, submission, and grading
- Virtual classroom sessions with recording
- Attendance tracking
- Search across resources
- Administrative analytics and access control

### 2.3 User Characteristics

| User Class | Technical Proficiency | Primary Needs |
|---|---|---|
| Student | Low–Medium | Simple, reliable access to content, submissions, and communication, including offline |
| Lecturer | Medium | Efficient content authoring, grading, virtual class delivery |
| Department/Institution Admin | Medium–High | User, permission, storage, and analytics oversight |
| Platform Super-Admin | High | Multi-tenant provisioning, system health, global configuration |

### 2.4 Assumptions and Dependencies
- Devices support modern Flutter runtime requirements per platform.
- Institutions provide (or CampusHub hosts) PostgreSQL, Redis, and S3-compatible storage.
- WebRTC virtual classroom requires a signaling server and (at scale) a TURN/SFU service.
- Initial release does not depend on external identity providers (Entra ID is future work).

## 3. Functional Requirements

Requirements are grouped by module and numbered `FR-<Module>-<n>`. Priority: **M**ust, **S**hould, **C**ould (MoSCoW).

### 3.1 Identity, Tenancy & Access (FR-IAM)
- FR-IAM-1 (M): System shall support registration and management of multiple isolated institutions (tenants) within one deployment.
- FR-IAM-2 (M): System shall support user roles: Student, Lecturer, Department Admin, Institution Admin, Super Admin.
- FR-IAM-3 (M): System shall authenticate users via JWT access tokens with refresh token rotation.
- FR-IAM-4 (M): System shall enforce RBAC on every API endpoint.
- FR-IAM-5 (M): System shall isolate all tenant data such that no query can return cross-tenant records.
- FR-IAM-6 (S): System shall support OAuth-based login as a future extension point (not implemented at MVP).
- FR-IAM-7 (M): System shall support offline authentication via securely cached credentials/tokens with defined expiry (see Phase 9).

### 3.2 Learning Resources (FR-RES)
- FR-RES-1 (M): Lecturers shall upload resources (documents, slides, video, links) to a course/module.
- FR-RES-2 (M): Students shall browse and download resources for offline access.
- FR-RES-3 (M): System shall version resources and show latest vs. superseded versions.
- FR-RES-4 (S): System shall track per-resource download/view counts for engagement analytics.
- FR-RES-5 (M): System shall support folder/module-based organization mirroring course structure.

### 3.3 Communication (FR-COM)
- FR-COM-1 (M): System shall support course-scoped discussion channels.
- FR-COM-2 (M): System shall support direct messaging between users within a tenant.
- FR-COM-3 (M): System shall support institution/department/course-scoped announcements.
- FR-COM-4 (M): Messages sent offline shall queue and deliver on reconnect.
- FR-COM-5 (S): System shall support message search within a channel/conversation.

### 3.4 Assignments & Grading (FR-ASG)
- FR-ASG-1 (M): Lecturers shall create assignments with due dates, instructions, and attachments.
- FR-ASG-2 (M): Students shall submit assignments, including drafting offline and syncing on reconnect.
- FR-ASG-3 (M): Lecturers shall grade submissions with numeric/rubric scores and feedback text.
- FR-ASG-4 (M): System shall enforce and display due dates, late-submission status.
- FR-ASG-5 (S): System shall support rubric-based grading templates.

### 3.5 Virtual Classroom (FR-VC)
- FR-VC-1 (M): Lecturers shall create and start scheduled or ad-hoc virtual class sessions.
- FR-VC-2 (M): System shall support live audio/video via WebRTC for session participants.
- FR-VC-3 (M): System shall support screen sharing during a session.
- FR-VC-4 (S): System shall support session recording and storage for later playback.
- FR-VC-5 (M): System shall track attendance automatically based on session join/leave events.
- FR-VC-6 (S): System shall support in-session text chat.
- FR-VC-7 (C): System shall support a shared whiteboard during sessions.

### 3.6 Attendance (FR-ATT)
- FR-ATT-1 (M): System shall record attendance per session/class automatically from virtual classroom join events, and support manual marking for in-person sessions.
- FR-ATT-2 (S): Lecturers shall view attendance reports per course.

### 3.7 Search (FR-SRCH)
- FR-SRCH-1 (M): System shall support keyword search across resources, discussions, and announcements within a tenant, scoped to the user's permissions.
- FR-SRCH-2 (C): System shall support natural-language search (AI module, Phase 11).

### 3.8 Administration (FR-ADM)
- FR-ADM-1 (M): Institution Admins shall manage departments, courses, and user accounts within their tenant.
- FR-ADM-2 (M): Institution Admins shall configure storage quotas and view usage.
- FR-ADM-3 (M): Institution Admins shall view basic engagement analytics (active users, submissions, resource usage).
- FR-ADM-4 (M): Super Admins shall provision new tenants and configure system-wide settings.
- FR-ADM-5 (M): System shall maintain audit logs of administrative and security-relevant actions.

### 3.9 Offline Synchronization (FR-SYNC)
- FR-SYNC-1 (M): System shall cache resources, discussions, and assignment data locally via SQLite for offline access.
- FR-SYNC-2 (M): System shall queue create/update actions performed offline and synchronize them when connectivity resumes.
- FR-SYNC-3 (M): System shall detect and resolve sync conflicts per the strategy defined in Phase 9.
- FR-SYNC-4 (S): System shall show users clear sync status (pending, synced, conflict).

### 3.10 Academic Portfolio (FR-PORT)
- FR-PORT-1 (S): Students shall maintain a portfolio of completed courses, grades, and selected work products, exportable for personal use.

## 4. Non-Functional Requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-1 | Performance | 95th-percentile API response time < 300ms under nominal load (excluding file transfer/video) |
| NFR-2 | Scalability | Backend services shall be stateless and horizontally scalable behind a load balancer/API gateway |
| NFR-3 | Availability | Production target of 99.5% uptime for core (non-video) services |
| NFR-4 | Offline Capability | Core read/draft workflows shall function with zero network connectivity, per Phase 9 |
| NFR-5 | Data Isolation | No cross-tenant data access under any authenticated or unauthenticated request path |
| NFR-6 | Security | All data in transit encrypted (TLS 1.2+); sensitive data at rest encrypted; passwords hashed with a modern algorithm (e.g., Argon2id) |
| NFR-7 | Accessibility | UI shall meet WCAG 2.1 AA where feasible on each target platform |
| NFR-8 | Portability | Single Flutter codebase shall target Android, iOS, Windows, macOS, Linux, and Web with acceptable feature parity |
| NFR-9 | Data Usage | Client shall minimize bandwidth via pagination, compression, and selective sync, given low-bandwidth target users |
| NFR-10 | Maintainability | Backend and frontend shall follow modular/clean architecture enabling independent module evolution |
| NFR-11 | Observability | All services shall emit structured logs and metrics suitable for centralized monitoring |
| NFR-12 | Backup/Recovery | Production data shall be backed up on a defined schedule with tested restore procedures (Phase 8/13) |

## 5. Business Rules

- BR-1: A user account belongs to exactly one tenant (institution); cross-tenant accounts are not supported at MVP.
- BR-2: Only Institution Admins and Super Admins may create/modify department and course structures.
- BR-3: Grades may only be modified by the assigning lecturer or an admin, and all changes are audit-logged.
- BR-4: Storage quota enforcement occurs at the tenant level; uploads exceeding quota are rejected with a clear error.
- BR-5: A submission after the due date is flagged "late" but not blocked, unless the lecturer disables late submissions for that assignment.

## 6. System Constraints

- Must use the fixed technology stack defined in Phase 1 (Flutter, FastAPI, PostgreSQL, SQLite, Redis, WebSockets, WebRTC, MinIO/S3, JWT).
- Must support offline-first operation without requiring a persistent connection for core workflows.
- Must maintain strict tenant isolation from the first implemented milestone, not retrofitted later.

## 7. Acceptance Criteria (Sample, System-Level)

- AC-1: A newly provisioned tenant is fully isolated — no user, resource, or message from Tenant A is visible or queryable from Tenant B's context, verified by automated isolation tests.
- AC-2: A student can view previously downloaded resources and draft an assignment submission with the device in airplane mode; upon reconnect, the submission syncs without data loss.
- AC-3: A lecturer can start a virtual class, share their screen, and have session attendance automatically recorded for all participants who joined.
- AC-4: All authentication endpoints reject invalid/expired tokens and enforce RBAC per Phase 8 threat model.

## 8. Future Enhancements

See Phase 18 (Future Expansion) for the full list: AI Tutor, Marketplace, Digital Student ID, QR Attendance, Timetable, Student Portfolio expansion, Internship Management, Research Repository, Library Management, Payments, Alumni Portal, and Microsoft Entra ID integration.

---

*Next document: Phase 3 — Product Requirements Document.*
