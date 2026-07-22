# CampusHub — Testing Strategy

**Document Phase:** 12 of 18
**Status:** Draft for Approval
**Version:** 1.0
**Date:** 2026-07-15

---

## 1. Test Plan Overview

| Level | Owner (solo-dev context) | Tooling | Frequency |
|---|---|---|---|
| Unit | Developer, AI-assisted generation reviewed by developer | pytest (backend), flutter_test (client) | Every commit (CI) |
| Integration | Developer | pytest against locally installed Postgres/Redis (dedicated test database) | Every PR (CI) |
| Performance | Developer, scheduled | Locust/k6 | Pre-release, monthly in production-like staging |
| Load | Developer, scheduled | k6 | Pre-release milestones (Beta, GA) |
| Security | Developer + automated scanners | OWASP ZAP, `pip-audit`/`npm audit` equivalents, manual checklist (Phase 8) | Pre-release, quarterly |
| UI | Developer | flutter_test widget tests, integration_test (device/emulator) | Every PR (CI) for critical flows |
| Acceptance | Developer against Phase 2/3 acceptance criteria | Manual + scripted scenarios | Each milestone |

## 2. Unit Testing

- **Backend (FastAPI/Python):** every service-layer function and repository method has unit tests with mocked dependencies; target ≥80% line coverage on business logic (not enforced on generated/boilerplate code).
- **Client (Flutter/Dart):** unit tests for use cases (domain layer) and repository logic (mocking data sources), independent of widget rendering.
- Unit tests must not require network, database, or filesystem — pure logic only; anything requiring those belongs in integration tests.

## 3. Integration Testing

- Backend integration tests run against a dedicated locally installed PostgreSQL test database (created/dropped per test session) and local Redis, exercising full request→DB round trips through FastAPI's test client, including RLS/tenant-isolation assertions (`fn_check_tenant_isolation`, Phase 5 §8). Object storage is exercised against a local MinIO instance or the filesystem storage fallback.
- Sync engine integration tests simulate offline queue → `POST /sync/batch` → server persistence → conflict scenarios (Phase 9 §3), asserting idempotency via `client_id` replay.
- Client integration tests exercise the SQLite ↔ mocked-API sync flow end-to-end without a real backend, using a local mock server.

## 4. Performance Testing

- Target: 95th-percentile API latency < 300ms under nominal load (NFR-1), measured via Locust/k6 scripted scenarios against a staging environment matching production topology.
- Key scenarios profiled: resource listing/download initiation, message send/fan-out, assignment submission burst (simulating a due-date rush), search queries.
- Baseline performance numbers recorded per release and compared release-over-release to catch regressions.

## 5. Load Testing

- Simulates realistic peak scenarios: (a) start-of-term resource download surge, (b) assignment-due-date submission spike, (c) concurrent virtual classroom sessions at target institution size.
- WebRTC/SFU load tested separately with synthetic participants (headless WebRTC clients) to validate concurrent session capacity before Beta and GA milestones.
- Load test results directly inform uvicorn worker counts, host sizing, and horizontal host-count planning (Phase 13).

## 6. Security Testing

- Automated: dependency vulnerability scanning (`pip-audit`, Dart/Flutter `dependency-check` equivalent) on every CI run; OWASP ZAP baseline scan against staging pre-release.
- Manual: OWASP Top 10 checklist (Phase 8 §8) walked pre-release; tenant-isolation penetration test (attempt cross-tenant access via ID manipulation, JWT tampering, direct object reference) performed before each major milestone.
- File upload security tests: malformed/oversized/malicious-MIME uploads rejected as specified (Phase 8 §6).

## 7. UI Testing

- Widget tests for all shared design-system components (Phase 7) — button states, form validation, status chips.
- `integration_test` scripted flows for the critical paths from Phase 7 §3: offline assignment submission, virtual class join, admin course provisioning, offline resource browsing — run on at least one representative device/emulator per platform family (mobile, desktop, web) in CI where feasible, manually verified otherwise given solo-dev CI budget constraints.
- Accessibility checks (contrast, semantics labels, text scaling) spot-checked per Phase 7 §10 before each milestone release.

## 8. Acceptance Testing

- Directly maps to acceptance criteria defined in Phase 2 §7 and Phase 3 §6 (e.g., AC-1 tenant isolation, AC-2 offline submission integrity, AC-3 automatic attendance, AC-4 auth/RBAC enforcement).
- Each milestone (MVP, Beta, GA per Phase 1 §10) has an acceptance checklist derived from its scoped epics (Phase 3 §7); milestone is not considered "done" until all applicable acceptance criteria pass in a staging environment matching production configuration.
- Pilot-institution acceptance (Beta stage) includes real-user UAT feedback loop, tracked as backlog items (Phase 15) rather than blocking release outright unless a P0 defect is found.

---

*Next document: Phase 13 — Deployment Guide.*
