# CampusHub — Offline Synchronization Design

**Document Phase:** 9 of 18
**Status:** Draft for Approval
**Version:** 1.0
**Date:** 2026-07-15

---

## 1. SQLite Structure (Client)

The local SQLite database mirrors a permission-scoped subset of server tables (Phase 5), with two additions on every syncable table:

| Extra Column | Purpose |
|---|---|
| `sync_status` | `synced` \| `pending_create` \| `pending_update` \| `pending_delete` \| `conflict` |
| `local_version` / `server_version` | Detect divergence since last successful sync |

Mirrored tables (MVP scope): `users` (self + course peers, minimal fields), `courses`, `modules`, `resources` (+ downloaded `resource_versions` blobs on device filesystem, referenced by path), `messages`, `announcements`, `assignments`, `submissions`, `class_sessions`, `attendance_records` (read-only cache).

A dedicated `sync_queue` table records outbound mutations in order:

```
sync_queue(
  id UUID PK,
  entity_table TEXT,
  entity_id UUID,
  operation ENUM(create, update, delete),
  payload JSON,
  client_id UUID,       -- idempotency key
  created_at TIMESTAMP,
  attempt_count INT,
  last_error TEXT NULLABLE
)
```

## 2. Sync Queue

- Every offline mutation (create submission, send message, edit draft) is written to local SQLite **and** appended to `sync_queue` in the same local transaction — the UI never waits on network.
- The Sync Engine (a background isolate/service) drains the queue FIFO per entity type when connectivity is detected, batching via `POST /sync/batch` (Phase 6 §6).
- Each queue item carries a `client_id`; the server treats `client_id` as an idempotency key so retried/duplicate submissions never create duplicate records.
- Successful items are removed from the queue and the corresponding local row's `sync_status` is set to `synced`; failed items increment `attempt_count` and retry with backoff (§9).

## 3. Conflict Resolution

Conflicts are detected via `version` comparison (Phase 5 §1): the client sends the `server_version` it last saw; if the server's current version has advanced, it's a conflict.

| Data Class | Strategy |
|---|---|
| Low-stakes, single-owner (draft submission content, chat message) | **Last-write-wins** with the server's authoritative timestamp; local copy silently reconciled. |
| High-stakes, single-owner (final submission after due date) | **Server wins if already submitted**; client is shown a non-destructive conflict banner and the local draft is preserved as a separate recoverable copy rather than overwritten. |
| Grades and admin-authored data | **Never client-writable offline** — grades are only ever mutated online by lecturers, eliminating this conflict class entirely by design. |
| Shared/multi-editor data (none at MVP; future collaborative docs) | Reserved for future CRDT-based merge (Phase 18 candidate); out of scope for MVP. |

Unresolvable conflicts (rare — e.g., resource deleted server-side while a client had a pending update) are surfaced to the user in a "Sync Issues" screen for manual acknowledgment; never silently dropped.

## 4. Background Sync

- Triggered by: (a) connectivity change (OS network callback), (b) app foreground, (c) periodic background task where the platform supports it (Android WorkManager, iOS BGTaskScheduler; desktop/web run on a timer while the app process is alive).
- Two-phase per cycle: **push** (drain `sync_queue`) then **pull** (`GET /sync/changes?since={cursor}` for incremental server-side changes), applied in that order so a user's own just-made edits aren't clobbered by the pull phase.
- Sync runs are logged locally (timestamp, item counts, failures) for the in-app "Sync Status" screen and support diagnostics.

## 5. Download Manager

- Explicit, user-initiated downloads for resources (individual or "download all module") — CampusHub does not silently mass-download to respect the low-data-usage goal (NFR-9).
- Downloads run through a managed queue with concurrency limits, pause/resume support, and progress reporting; large files (video) support resumable chunked download.
- Downloaded blobs are stored in app-private storage, referenced from SQLite `resource_versions.local_path`; a checksum verification runs after download completes before marking `available` locally.

## 6. Offline Authentication

- On successful online login, the server issues (alongside the standard JWT pair) a client-retained, locally-verifiable **offline session artifact**: a signed structure containing `user_id`, `tenant_id`, role snapshot, and an expiry (default 14 days, institution-configurable).
- App unlock while offline validates this artifact's signature and expiry locally (public key embedded in the client build) — no network call required, and the raw password is never cached.
- If the offline artifact expires while the device remains offline, the client moves to a degraded read-only mode (cached content viewable, no new mutations queued) until the user can reconnect and re-authenticate.
- Optional local device passcode/biometric gate (Flutter `local_auth`) can be layered on top of the offline session for shared-device scenarios.

## 7. Caching Strategy (Client-Local, distinct from server Redis cache in Phase 4)

- SQLite is the durable offline cache — not a TTL-based cache but a long-lived local replica scoped to the user's enrollments/permissions.
- Metadata (courses, modules, assignments, messages) is synced eagerly and kept small; large binary resource content is synced lazily/on-demand via the Download Manager (§5) to control storage and bandwidth.

## 8. Data Expiration

- Cached metadata has no hard expiration but is refreshed on every successful pull sync.
- Downloaded binary resources are retained until the user deletes them, storage pressure triggers an opt-in cleanup prompt (least-recently-accessed first), or the resource is superseded by a new version (old version flagged stale, not auto-deleted, so offline users aren't surprised by disappearing content mid-use).
- Offline session artifacts (§6) expire per their configured TTL and are not renewable without an online check-in.

## 9. Retry Logic

- Exponential backoff with jitter for failed sync-queue items: base 2s, cap 5 minutes, max local retry count before flagging `sync_status = conflict`/error for user visibility rather than retrying silently forever.
- Network-transient errors (timeout, 5xx) retry automatically; validation errors (4xx other than 409) do not retry — they surface immediately as a fixable local issue (e.g., quota exceeded).
- Batch sync calls are chunked to a safe payload size to avoid a single oversized batch permanently failing; chunk size is tunable server-side via config.

---

*Next document: Phase 10 — Virtual Classroom Design.*
