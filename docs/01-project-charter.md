# CampusHub — Project Charter

**Document Phase:** 1 of 18
**Status:** Draft for Approval
**Version:** 1.0
**Date:** 2026-07-15

---

## 1. Vision

CampusHub is the unified digital ecosystem for higher-education institutions — a single, offline-first, cross-platform application that replaces the fragmented stack of SharePoint, Teams, Moodle, Discord, Google Drive, Google Classroom, Zoom, WhatsApp Communities, and Canvas LMS that colleges and universities currently stitch together. Every student, lecturer, and administrator interacts with one coherent system for learning, communication, collaboration, and institutional management.

## 2. Mission

To eliminate application fragmentation in higher education by delivering a secure, multi-tenant, offline-capable platform that lets any institution — regardless of size, budget, or connectivity — run its entire academic and administrative digital life inside CampusHub.

## 3. Objectives

| # | Objective | Measure |
|---|---|---|
| O1 | Consolidate LMS, communication, storage, and virtual classroom into one app | ≥80% reduction in third-party app usage reported by pilot institutions |
| O2 | Deliver true offline-first functionality | Core features (view notes, draft submissions, read announcements) usable with zero connectivity |
| O3 | Support multiple institutions on shared infrastructure with strict data isolation | Zero cross-tenant data leakage incidents |
| O4 | Achieve production-grade security and compliance posture | Pass independent security review before GA |
| O5 | Ship a cross-platform client from one codebase | Android, iOS, Windows, macOS, Linux, Web all functional at GA |
| O6 | Enable incremental adoption by a single developer using AI-assisted workflows | MVP shippable within the roadmap defined in Phase 14/15 |

## 4. Business Case

Institutions currently pay for and integrate 5–9 separate SaaS products (LMS, video conferencing, file storage, chat, classroom management) with no unified identity, search, or offline story. This creates:

- **Cost duplication** — overlapping subscriptions for storage, video, and chat.
- **Data fragmentation** — student records, grades, and files scattered across systems with no single source of truth.
- **Connectivity exclusion** — students in low-bandwidth regions are locked out of cloud-only tools.
- **Vendor lock-in and integration fragility** — SSO, webhooks, and data export between disparate SaaS vendors are brittle and often unsupported.

CampusHub's business case is consolidation: one platform, one identity, one offline-capable client, deployable per-institution or as a shared multi-tenant SaaS, at a fraction of the combined cost of the tools it replaces.

## 5. Success Criteria

- Multi-tenant architecture proven with ≥2 isolated institutions on one deployment.
- Offline-first behavior verified: a student can read/download resources, draft assignment submissions, and view cached announcements with no network, with changes syncing correctly on reconnect.
- Virtual classroom (WebRTC) supports live sessions with recording, chat, and screen share at acceptable quality on constrained bandwidth.
- Security design passes OWASP-based review (see Phase 8) prior to production rollout.
- A solo developer, following the roadmap in Phase 14/15, can reach a usable MVP without requiring a team.

## 6. Stakeholders

| Stakeholder | Interest |
|---|---|
| Students | Single app for learning, communication, and submissions; usable offline |
| Lecturers | Simple content/assignment/grading workflow; virtual classroom; engagement insight |
| Institution Administrators | Tenant management, user/permission control, storage and analytics oversight |
| Platform Owner / Developer | Sustainable, scalable, secure product buildable incrementally |
| IT/Security teams (institutional) | Data isolation, compliance, auditability |
| Future integration partners | Entra ID, payment processors, library systems (Phase 18) |

## 7. Scope

### In Scope (MVP → GA)
- Multi-tenant institution/department/user management
- Learning resource management with offline download
- Assignments: creation, submission, grading
- Discussions/communication (channels, DMs, announcements)
- Virtual classroom via WebRTC (live sessions, screen share, recording, chat)
- Attendance tracking
- Search across institutional resources
- Offline-first sync engine (SQLite ↔ PostgreSQL)
- Cross-platform Flutter client (mobile, desktop, web)
- FastAPI backend, JWT auth, RBAC

### Out of Scope (MVP)
- Payments, alumni portal, marketplace, AI tutor (see Phase 18 — Future Expansion)
- Microsoft Entra ID integration (future OAuth phase)
- Full analytics/BI suite (basic admin analytics only at GA)

## 8. Constraints

- Solo-developer execution model using AI-assisted development — documentation and architecture must be unambiguous enough to implement without a team.
- Offline-first requirement constrains architecture: every core feature must degrade gracefully without connectivity.
- Strict tenant data isolation required at the database and storage layer from day one — retrofitting multi-tenancy later is out of scope for risk reasons.
- Technology stack is fixed per project brief (Flutter, FastAPI, PostgreSQL, SQLite, Redis, WebSockets, WebRTC, MinIO/S3, JWT).

## 9. Assumptions

- Institutions will provide their own infrastructure or consume a hosted multi-tenant SaaS offering.
- Initial user base per institution is moderate (hundreds to low thousands), not hyperscale — architecture should be scalable but not over-engineered for the MVP.
- Network conditions for the target market (colleges, including in low-connectivity regions) are unreliable, justifying the offline-first mandate.
- Video/WebRTC infrastructure may require a TURN/SFU service; this is budgeted for in later phases.

## 10. Project Timeline (High-Level)

| Milestone | Target |
|---|---|
| Planning & Documentation Complete (Phases 1–18) | Week 0–2 |
| MVP: Auth, Multi-tenancy, Resource Management, Offline Sync core | Month 1–3 |
| Communication + Assignments + Grading | Month 3–5 |
| Virtual Classroom (WebRTC) | Month 5–6 |
| Admin Analytics + Security Hardening | Month 6–7 |
| Beta with pilot institution(s) | Month 7–8 |
| GA release (all target platforms) | Month 9–10 |

Detailed sprint-level roadmap is defined in Phase 14 (Project Management) and Phase 15 (Feature Backlog).

## 11. Estimated Cost

Given a solo-developer, AI-assisted execution model, the dominant costs are infrastructure and tooling rather than labor:

| Category | Estimate (Monthly, Dev/Beta) | Estimate (Monthly, Production, per tenant cluster) |
|---|---|---|
| Compute (Linux VM hosts, native processes) | $0–50 (local/dev) | $150–400 |
| Object Storage (S3-compatible) | $0 (MinIO local) | $20–100 (usage-dependent) |
| Managed PostgreSQL + Redis (if managed) | $0 (self-hosted dev) | $50–150 |
| WebRTC SFU/TURN service | $0 (dev, local) | $50–300 (usage-dependent) |
| CI/CD (GitHub Actions) | Free tier initially | $0–50 |
| Domain, certificates, monitoring | ~$20 | ~$40 |
| **Total (rough order of magnitude)** | **< $100/month** | **$300–1,000+/month per active deployment, scaling with usage** |

These are order-of-magnitude planning estimates, not vendor quotes; refine during Phase 13 (Deployment Guide).

## 12. Risks

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Offline sync conflicts corrupt data | High | Medium | Formal conflict-resolution design (Phase 9); versioned records, last-write-wins with audit trail where safe, manual resolution for high-stakes data (grades) |
| Multi-tenant data leakage | Critical | Low–Medium | Row-level security in PostgreSQL, tenant-scoped queries enforced at repository layer, automated isolation tests |
| WebRTC scalability/quality on low bandwidth | Medium | Medium | Adaptive bitrate, SFU architecture, bandwidth optimization design (Phase 10) |
| Solo-developer bandwidth/scope creep | High | High | Strict phased roadmap, MVP-first discipline, feature backlog prioritization (Phase 15) |
| Security vulnerabilities (auth, file upload, RBAC) | Critical | Medium | Dedicated Security Design phase (Phase 8), OWASP checklist, audit logging |
| Flutter multi-platform parity gaps (esp. Linux/Web WebRTC support) | Medium | Medium | Platform-specific spikes early in MVP; graceful feature degradation per platform |

---

*Next document: Phase 2 — Software Requirements Specification (IEEE 830).*
