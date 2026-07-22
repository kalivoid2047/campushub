# CampusHub — Implementation Roadmap

**Status:** Draft for Approval
**Version:** 1.0
**Date:** 2026-07-15
**Audience:** Solo developer using AI-assisted development

This document synthesizes Phases 1–18 into a sequenced, dependency-aware build plan. It assumes all planning documents (`01`–`18`) are approved before coding starts, per the project's stated philosophy.

---

## 1. Guiding Principle: Build Order Follows Dependency, Not Feature Glamour

Every module in Phase 15's backlog depends on foundations most developers are tempted to skip past. The order below is deliberately unglamorous at the start: **tenancy and auth before anything else**, because retrofitting multi-tenant isolation later is explicitly called out as a top risk in Phase 1 §12 and a hard constraint in Phase 1 §8. **Offline sync core comes second**, before any feature module, because every subsequent feature (resources, communication, assignments) must be built sync-aware from day one — bolting sync onto an already-built feature is far more expensive than building the feature on top of an existing sync engine.

## 2. Module Build Sequence & Dependency Graph

```
1. Foundation
   ├── DB schema + migrations (Phase 5)
   ├── Tenant provisioning + RLS (Epic E1)
   ├── Auth (JWT, refresh, RBAC) (Epic E1)
   └── Offline auth artifact (Epic E1)
        │
2. Sync Core  ◄── depends on Foundation
   ├── SQLite mirror scaffolding (Epic E9)
   ├── Sync queue + batch push API (Epic E9)
   └── Delta pull sync (Epic E9)
        │
3. Resources  ◄── depends on Sync Core
   ├── Upload/versioning (Epic E2)
   ├── Browsing (Epic E2)
   └── Offline download manager (Epic E2)
        │
4. Communication  ◄── depends on Sync Core (parallel to Resources, low coupling)
   ├── Channels/messages (Epic E3)
   ├── Announcements (Epic E3)
   └── Offline message queueing (Epic E3)
        │
5. Assignments & Grading  ◄── depends on Resources (attachments) + Sync Core
   ├── Assignment creation (Epic E4)
   ├── Offline submission (Epic E4)
   └── Grading (Epic E4)
        │
6. Admin Basics  ◄── depends on Foundation + Resources
   ├── Department/course management (Epic E8)
   ├── Storage quota dashboard (Epic E8)
   └── Audit log viewer (Epic E8)
        │
   ═══════════ MVP COMPLETE — internal dogfood / early pilot possible here ═══════════
        │
7. Virtual Classroom  ◄── depends on Foundation, Communication (chat reuse)
   ├── Session scheduling + signaling (Epic E5)
   ├── Live video/audio (SFU integration) (Epic E5)
   ├── Screen sharing (Epic E5)
   └── Recording (Epic E5)
        │
8. Attendance  ◄── depends on Virtual Classroom
   ├── Automatic attendance (Epic E6)
   ├── Manual attendance (Epic E6)
   └── Reporting (Epic E6)
        │
9. Analytics Expansion  ◄── depends on all above (needs data to aggregate)
   └── Basic engagement analytics (Epic E8)
        │
   ═══════════ BETA — pilot institution onboarding ═══════════
        │
10. Search  ◄── depends on Resources, Communication
    └── Keyword search (Epic E7) [Semantic search deferred to Post-GA]
        │
11. Academic Portfolio  ◄── depends on Grading, Enrollment
    └── Portfolio view (Epic E10)
        │
   ═══════════ GA — all six platforms shipped ═══════════
        │
12. Post-GA
    ├── AI Module (Phase 11) — Study Assistant, Semantic Search, Summarization, Quiz/Flashcard generation
    └── Phase 18 Future Expansion items, prioritized by pilot-institution feedback
```

## 3. Milestone-to-Module Mapping

| Milestone (Phase 14 §2) | Modules Completed |
|---|---|
| M0 — Docs Approved | This document set |
| M1 — Auth & Tenancy Live | Foundation (§2.1) |
| M2 — Offline Resource MVP | Sync Core + Resources (§2.2–2.3) |
| M3 — Communication + Assignments | Communication + Assignments + Admin Basics (§2.4–2.6) → **MVP** |
| M4 — Virtual Classroom Live | Virtual Classroom (§2.7) |
| M5 — Security Hardening Complete | Cross-cutting pass against Phase 8 checklist across all shipped modules |
| M6 — Beta Launch | Attendance + Analytics Expansion (§2.8–2.9) |
| M7 — GA | Search + Portfolio (§2.10–2.11) |

## 4. Which Modules to Build First — Explicit Recommendation

For a solo developer starting today, build in this exact order, and do not start module *N+1* until module *N*'s automated tests (Phase 12) and acceptance criteria (Phase 2 §7 / Phase 3 §6) pass:

1. **Database schema + migrations** (Phase 5) — nothing else can start without this.
2. **Tenant + Auth + RBAC** (Epic E1) — validates AC-1 (tenant isolation) immediately; this is the single highest-risk area per Phase 1 §12 and should be proven correct before any feature code depends on it.
3. **Offline sync core** (Epic E9) — built against a trivial test entity first (e.g., a stub table) to prove the sync queue/conflict/delta-pull mechanics in isolation before any real feature uses it.
4. **Resources** — the first real feature module, and the one that exercises the offline download manager, validating AC-2 (offline capability) end-to-end for the first time.
5. **Communication, then Assignments** — both build directly on the now-proven sync core; Assignments depends on Resources for attachments, so it follows.
6. **Admin Basics** — thin CRUD layer needed to actually create the departments/courses that all prior modules assume exist; can be built in parallel with step 5 once Foundation is done, since it only depends on Foundation.
7. Everything from **Virtual Classroom onward** is materially higher complexity (WebRTC, SFU infrastructure) — deliberately sequenced after a working, testable MVP exists, so infrastructure risk doesn't block early validation of the platform's core value proposition (unified offline-capable coursework and communication).

## 5. Incremental Evolution to Production Multi-Tenant Platform

- **Single-tenant proof, multi-tenant architecture from day one:** even the first pilot institution runs on the full RLS-isolated schema — there is no "single-tenant mode" to later migrate away from, eliminating the highest-risk category of retrofit work.
- **Infrastructure scales in step with adoption:** development runs against natively installed PostgreSQL/Redis/MinIO (Phase 13 §1, no containers) throughout Foundation → MVP; the native systemd/NGINX production deployment (Phase 13 §4) is stood up no later than Beta, so the transition to production infrastructure is validated before GA, not discovered at launch.
- **Security hardening is continuous, not a single late-stage task:** Phase 8's OWASP checklist and audit logging are implemented alongside each module (each module's PR checklist per Phase 14 §8 includes a tenant-isolation check), with a dedicated M5 milestone pass to close any remaining gaps before Beta.
- **Feature flags decouple deploy from release** (Phase 14 §9) starting at the Virtual Classroom stage, where infrastructure risk is highest — allowing incremental rollout to pilot institutions without blocking `main`'s deploy cadence.
- **Post-GA growth path is additive, not disruptive:** every Phase 18 future-expansion item was verified against the Phase 4–6 architecture to require only additive schema/module changes, not breaking changes — so the platform can grow institution-by-institution and feature-by-feature without a re-architecture.

---

*This roadmap, together with docs/01 through docs/18, constitutes the complete pre-development planning and documentation set for CampusHub. Development may begin once this set is reviewed and approved.*
