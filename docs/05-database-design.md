# CampusHub — Database Design Document

**Document Phase:** 5 of 18
**Status:** Draft for Approval
**Version:** 1.0
**Date:** 2026-07-15

---

## 1. Design Principles

- Every tenant-scoped table carries a `tenant_id` foreign key and is protected by **PostgreSQL Row-Level Security (RLS)** policies, so isolation is enforced at the database engine level, not just application code.
- Normalized to 3NF for transactional tables; selective denormalization (e.g., cached counters) only where read performance demands it, documented inline.
- Soft-delete (`deleted_at`) on user-facing entities where recoverability matters (resources, submissions); hard-delete for ephemeral/audit-irrelevant data.
- All primary keys are UUIDv7 (time-ordered) for safe client-side generation (supports offline creation) and index locality.
- All tables have `created_at`, `updated_at`; mutation-tracked tables also have `version` (optimistic concurrency / sync conflict detection, see Phase 9).

## 2. Entity-Relationship Diagram (Textual)

```
Tenant (Institution) ──< Department ──< Course ──< CourseEnrollment >── User
   │                                        │
   │                                        ├──< Module ──< Resource ──< ResourceVersion
   │                                        ├──< Assignment ──< Submission ──< Grade
   │                                        ├──< Channel ──< Message
   │                                        ├──< Announcement
   │                                        └──< ClassSession ──< AttendanceRecord
   │                                                       └──< SessionRecording
   │
   ├──< Role ──< UserRole >── User
   ├──< AuditLog
   └──< StorageQuota
```

## 3. Core Tables

### 3.1 `tenants`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | TEXT | |
| slug | TEXT UNIQUE | subdomain/routing key |
| status | ENUM(active, suspended, provisioning) | |
| storage_quota_bytes | BIGINT | |
| created_at, updated_at | TIMESTAMPTZ | |

### 3.2 `users`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| tenant_id | UUID FK → tenants | RLS key |
| email | TEXT | UNIQUE per tenant |
| password_hash | TEXT | Argon2id |
| full_name | TEXT | |
| status | ENUM(active, disabled, pending) | |
| offline_token_hash | TEXT NULLABLE | see Phase 9 |
| created_at, updated_at | TIMESTAMPTZ | |

### 3.3 `roles` / `user_roles`
- `roles`: id, tenant_id (nullable for system-wide roles), name (`student`, `lecturer`, `dept_admin`, `institution_admin`, `super_admin`), permissions (JSONB).
- `user_roles`: user_id, role_id, scope (`department_id`/`course_id` nullable for scoped grants).

### 3.4 `departments`
id, tenant_id, name, code, created_at, updated_at.

### 3.5 `courses`
id, tenant_id, department_id, name, code, term, created_at, updated_at.

### 3.6 `course_enrollments`
id, course_id, user_id, role (`student`/`lecturer`/`ta`), enrolled_at.

### 3.7 `modules`
id, course_id, title, position (INT, ordering), created_at, updated_at.

### 3.8 `resources`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| tenant_id | UUID FK | |
| module_id | UUID FK → modules | |
| title | TEXT | |
| type | ENUM(document, slide, video, link) | |
| current_version_id | UUID FK → resource_versions | |
| download_count | INT DEFAULT 0 | denormalized counter |
| deleted_at | TIMESTAMPTZ NULLABLE | |
| created_at, updated_at | TIMESTAMPTZ | |

### 3.9 `resource_versions`
id, resource_id, storage_key (S3 path), size_bytes, checksum, version_number, uploaded_by, created_at.

### 3.10 `channels` / `messages`
- `channels`: id, tenant_id, course_id (nullable — DMs have no course), type (`course`, `dm`), created_at.
- `messages`: id, channel_id, sender_id, body, attachments (JSONB), client_id (UUID for offline dedupe), created_at, edited_at.

### 3.11 `announcements`
id, tenant_id, scope (`institution`/`department`/`course`), scope_id, title, body, published_by, published_at.

### 3.12 `assignments`
id, tenant_id, course_id, title, instructions, due_at, allow_late, max_score, rubric (JSONB nullable), created_by, created_at, updated_at.

### 3.13 `submissions`
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | client-generated (offline creation) |
| assignment_id | UUID FK | |
| student_id | UUID FK | |
| content (JSONB / attachments) | | |
| status | ENUM(draft, submitted, late, graded) | |
| client_id | UUID | idempotency key for sync dedupe |
| version | INT | optimistic concurrency |
| submitted_at | TIMESTAMPTZ NULLABLE | |
| created_at, updated_at | TIMESTAMPTZ | |

### 3.14 `grades`
id, submission_id, grader_id, score, feedback, rubric_scores (JSONB), graded_at.

### 3.15 `class_sessions`
id, tenant_id, course_id, title, scheduled_start, scheduled_end, actual_start, actual_end, status (`scheduled`, `live`, `ended`, `cancelled`), created_by.

### 3.16 `attendance_records`
id, class_session_id, user_id, joined_at, left_at, duration_seconds, source (`auto`/`manual`), marked_by (nullable, for manual).

### 3.17 `session_recordings`
id, class_session_id, storage_key, duration_seconds, size_bytes, status (`processing`, `available`, `failed`), created_at.

### 3.18 `audit_logs`
id, tenant_id, actor_id, action, target_type, target_id, metadata (JSONB), ip_address, created_at. (Append-only, no update/delete.)

### 3.19 `storage_quotas`
tenant_id (PK/FK), used_bytes, quota_bytes, updated_at.

### 3.20 `sync_queue` (client-side SQLite only — mirrored conceptually, not a Postgres table)
See Phase 9 for the offline schema; not part of the server database.

## 4. Relationships Summary

- `tenants (1) — (N) users, departments, courses, ...` — every tenant-scoped table FKs to `tenants.id`.
- `courses (1) — (N) modules (1) — (N) resources (1) — (N) resource_versions`.
- `courses (1) — (N) assignments (1) — (N) submissions (1) — (1) grades`.
- `courses (1) — (N) class_sessions (1) — (N) attendance_records, session_recordings`.
- `users (M) — (N) courses` via `course_enrollments`.
- `users (M) — (N) roles` via `user_roles` (with optional scope).

## 5. Indexes

| Table | Index | Purpose |
|---|---|---|
| users | (tenant_id, email) UNIQUE | login lookup, isolation |
| resources | (module_id, deleted_at) | listing active resources |
| messages | (channel_id, created_at DESC) | paginated channel history |
| submissions | (assignment_id, student_id) UNIQUE | one submission record per student per assignment (latest) |
| submissions | (student_id, status) | student dashboard queries |
| attendance_records | (class_session_id, user_id) UNIQUE | dedupe join events |
| audit_logs | (tenant_id, created_at DESC) | audit review, partitionable |
| All tenant-scoped tables | (tenant_id, ...) composite as leading column | RLS + query performance |

## 6. Constraints

- Foreign keys with `ON DELETE RESTRICT` for financial/academic-record-bearing relations (grades, submissions); `ON DELETE CASCADE` for purely compositional data (resource_versions under resources).
- `CHECK` constraint on `grades.score BETWEEN 0 AND assignments.max_score` (enforced at application layer + DB check where feasible).
- `UNIQUE (tenant_id, email)` on users prevents duplicate accounts per institution while allowing the same email across tenants.
- `NOT NULL tenant_id` on every tenant-scoped table, enforced together with RLS policy `USING (tenant_id = current_setting('app.current_tenant')::uuid)`.

## 7. Views

- `v_course_engagement` — aggregates resource downloads, message counts, and submission rates per course for admin analytics (Phase 4 §admin module).
- `v_student_attendance_summary` — per-student attendance percentage per course, computed from `attendance_records`.
- `v_storage_usage_by_department` — rolls up `resources.size` via `resource_versions` grouped by department, feeding quota dashboards.

## 8. Stored Procedures / Triggers

- **Trigger** `trg_update_storage_usage` — on `resource_versions` INSERT, increments `storage_quotas.used_bytes`; on resource deletion, decrements. Keeps quota tracking accurate without application-layer race conditions.
- **Trigger** `trg_touch_updated_at` — generic `BEFORE UPDATE` trigger setting `updated_at = now()` on all tables that have the column.
- **Trigger** `trg_submission_late_flag` — on `submissions` INSERT/UPDATE, sets `status = 'late'` automatically if `submitted_at > assignment.due_at` and `assignment.allow_late = true`; rejects (or flags, per business rule) if `allow_late = false`.
- **Function** `fn_check_tenant_isolation()` — used in automated test suite (Phase 12) to assert no query plan can bypass RLS.

## 9. Data Dictionary (Excerpt — Full Dictionary Maintained as Generated Artifact from Schema Migrations)

| Field | Definition |
|---|---|
| `tenant_id` | Foreign key to the owning institution; present on all tenant-scoped rows; drives RLS. |
| `client_id` | Client-generated UUID used to deduplicate offline-created records (submissions, messages) during sync replay. |
| `version` | Monotonically incrementing integer used for optimistic concurrency control and conflict detection during sync (Phase 9). |
| `status` (submissions) | Lifecycle state: `draft → submitted → (late) → graded`. |
| `source` (attendance_records) | Distinguishes automatic WebRTC-derived attendance from manually marked attendance. |

*Full data dictionary is generated and kept current via schema migration tooling (Alembic) rather than maintained by hand; this document defines the authoritative intent that migrations must implement.*

---

*Next document: Phase 6 — API Design.*
