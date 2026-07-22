# CampusHub — Security Design

**Document Phase:** 8 of 18
**Status:** Draft for Approval
**Version:** 1.0
**Date:** 2026-07-15

---

## 1. Threat Model (STRIDE Summary)

| Threat | Vector | Mitigation |
|---|---|---|
| Spoofing | Credential stuffing, token forgery | Argon2id password hashing, JWT signature verification (RS256), rate-limited login, MFA future extension point |
| Tampering | Modified requests, file upload payload manipulation | Server-side validation on every field, signed presigned URLs with short TTL, checksum verification on uploads |
| Repudiation | Denial of grading/admin actions | Append-only audit log (Phase 5 `audit_logs`) covering all sensitive mutations |
| Information Disclosure | Cross-tenant data leakage, verbose errors | PostgreSQL RLS, tenant-scoped repository queries, generic error messages (no stack traces in prod) |
| Denial of Service | Auth endpoint flooding, large upload abuse | Rate limiting at gateway, upload size caps, quota enforcement, WebRTC SFU isolated from API compute |
| Elevation of Privilege | RBAC bypass, IDOR on resource IDs | Explicit permission checks per route, object-level ownership/tenant checks before any read/write |

## 2. Authentication

- Password auth with Argon2id hashing (memory-hard, tuned per OWASP recommendations).
- JWT access tokens (RS256, 15-minute TTL) + refresh tokens (7-day TTL, rotated on each use, stored hashed server-side, revocable via Redis blacklist).
- Login endpoint rate-limited per IP and per account; exponential backoff after repeated failures.
- Offline authentication: on successful online login, client caches a locally-verifiable session artifact (signed, tenant/user-bound, time-boxed) enabling app unlock offline without transmitting credentials; full mechanics in Phase 9.
- Future: OAuth2/OIDC and Microsoft Entra ID federation (extension point only, not implemented at MVP — see Phase 18).

## 3. Authorization

- RBAC enforced via FastAPI dependencies on every route (`require_role`, `require_permission`), never left to client-side checks alone.
- Two-layer authorization: (1) role/permission check, (2) object-level scope check (tenant_id match, course enrollment, resource ownership) before returning or mutating any record.
- Default-deny: new routes must explicitly declare required permissions; there is no unauthenticated-by-default route except `/auth/login` and health checks.

## 4. Encryption

- **In transit:** TLS 1.2+ enforced at the NGINX ingress; HTTP→HTTPS redirect; HSTS enabled in production.
- **At rest:** Database-level encryption (managed PostgreSQL provider encryption, or LUKS/volume encryption for self-hosted); object storage server-side encryption (S3 SSE or MinIO encryption at rest).
- **Sensitive columns:** password hashes and offline-token hashes never stored in plaintext; refresh tokens stored hashed (SHA-256) not raw.
- **Client-side:** local SQLite database encrypted at rest using platform-appropriate mechanisms (SQLCipher or platform keystore-backed encryption) given it holds offline copies of institutional data.

## 5. Secure Storage

- Refresh tokens and offline session artifacts stored in platform secure storage (Android Keystore, iOS Keychain, Windows DPAPI, macOS Keychain, Linux Secret Service) via Flutter secure-storage abstraction — never in plain SharedPreferences/localStorage.
- Web platform constraint: browser storage has weaker guarantees; web client uses short-lived in-memory tokens with silent refresh, and offline capability on web is reduced accordingly (documented limitation, consistent with NFR-8 "acceptable feature parity" rather than strict parity).

## 6. File Upload Security

- Server-side MIME/type validation independent of client-supplied `Content-Type`.
- File size limits enforced at gateway and application layer (per-tenant configurable, default caps per resource type).
- Uploaded files scanned for malware where institutional policy requires (pluggable AV-scan hook before a file transitions from `processing` to `available`).
- Files stored with randomized storage keys (not user-supplied filenames) to prevent path traversal; original filename retained only as metadata.
- Presigned upload URLs scoped to a single object, short TTL, and tenant-namespaced key prefix enforced server-side (client cannot choose the key).

## 7. Role-Based Access Control (RBAC) Matrix (Summary)

| Action | Student | Lecturer | Dept Admin | Institution Admin | Super Admin |
|---|---|---|---|---|---|
| View enrolled course content | ✅ | ✅ | ✅ | ✅ | ✅ |
| Upload resources | ❌ | ✅ (own courses) | ✅ | ✅ | ✅ |
| Grade submissions | ❌ | ✅ (own courses) | ✅ | ✅ | ✅ |
| Manage users/roles | ❌ | ❌ | ✅ (dept scope) | ✅ (tenant scope) | ✅ (all tenants) |
| Provision tenants | ❌ | ❌ | ❌ | ❌ | ✅ |
| View audit logs | ❌ | ❌ | Partial (dept scope) | ✅ | ✅ |

Full matrix maintained alongside the `roles.permissions` JSONB schema as an authoritative machine-checkable artifact, not just documentation.

## 8. OWASP Checklist (Top 10, 2021, Applied)

| Risk | Status/Control |
|---|---|
| A01 Broken Access Control | RBAC + tenant RLS + object-level checks (§3) |
| A02 Cryptographic Failures | TLS everywhere, Argon2id, encrypted storage (§4) |
| A03 Injection | ORM (SQLAlchemy) parameterized queries only; no raw SQL string interpolation; input validation via Pydantic |
| A04 Insecure Design | Threat modeling performed pre-implementation (this document); tenant isolation designed in from Phase 4/5, not retrofitted |
| A05 Security Misconfiguration | Hardened host configuration (dedicated service user, minimal packages), no default credentials, `/docs` disabled in prod, secrets via environment/secret manager not source control |
| A06 Vulnerable/Outdated Components | Automated dependency scanning in CI (Phase 13) |
| A07 Identification & Auth Failures | Rate limiting, token rotation, Argon2id (§2) |
| A08 Software/Data Integrity Failures | Signed CI artifacts, checksum-verified uploads, reviewed dependency updates |
| A09 Security Logging/Monitoring Failures | Structured audit logs (§9), centralized log aggregation (Phase 13) |
| A10 Server-Side Request Forgery | Presigned URL generation validated server-side; no user-controlled outbound URL fetching without allowlisting |

## 9. Audit Logging

- Every administrative action, grade change, role change, and authentication event (login, failed login, logout, token refresh) is written to the append-only `audit_logs` table (Phase 5 §3.18).
- Audit entries capture actor, action, target, tenant, IP, and timestamp; retained per institutional/regulatory policy (configurable retention, default 1 year).
- Audit log access itself is RBAC-controlled and read-only via the API — no update/delete endpoint exists.

## 10. Backup Strategy

- PostgreSQL: automated daily full backups + continuous WAL archiving for point-in-time recovery; backups encrypted and stored in a separate object storage bucket/region from primary data.
- Object storage (resources, recordings): versioning enabled on the S3-compatible bucket; cross-region/cross-provider replication for production tenants above a configurable size/criticality threshold.
- Backup retention: 30 daily, 12 monthly snapshots as a baseline policy (tunable per institutional contract).
- Restore procedures tested on a defined cadence (quarterly minimum) in a non-production environment; results logged.

## 11. Disaster Recovery

- **RPO target:** ≤ 1 hour (via WAL archiving/continuous backup).
- **RTO target:** ≤ 4 hours for full platform restoration from backup in a new environment.
- DR runbook (detailed in Phase 13) covers: database restore, object storage restore, secret/config re-provisioning, and validation checklist before reopening traffic.
- Multi-tenant blast-radius containment: because tenants are logically isolated (RLS + namespaced storage), a single-tenant data issue does not require full-platform restore — tenant-scoped restore is a first-class recovery path.

---

*Next document: Phase 9 — Offline Synchronization Design.*
