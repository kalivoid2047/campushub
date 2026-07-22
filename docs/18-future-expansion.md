# CampusHub — Future Expansion

**Document Phase:** 18 of 18
**Status:** Draft for Approval
**Version:** 1.0
**Date:** 2026-07-15

---

## Purpose

This document ensures the architecture defined in Phases 4–6 does not preclude the following future capabilities. Each item below states the extension point already designed in, and what net-new work would be required — none of these are built at MVP/GA.

## 1. AI Tutor

- **Extension point:** AI Module (Phase 11) already establishes the LLM gateway, vector index, and tenant-scoped opt-in pattern.
- **Future work:** Persistent tutoring-session memory per student, curriculum-aware pacing logic. Builds directly on the AI Study Assistant (Phase 11 §2).

## 2. Marketplace

- **Extension point:** None yet in core schema — deliberately deferred since it introduces payment/commerce concerns outside current scope.
- **Future work:** New `marketplace_listings`, `orders` tables (tenant-scoped or cross-tenant, needs a scoping decision at design time); integrates with Payments (§10) and Resource module for content-based listings.

## 3. Digital Student ID

- **Extension point:** `users` table (Phase 5 §3.2) can carry a `student_id_number` field already; QR/ID card rendering is a pure client-side feature.
- **Future work:** ID card template rendering, offline-verifiable digital ID (signed payload, similar pattern to the offline auth artifact in Phase 9 §6), optional NFC/QR issuance.

## 4. Attendance via QR

- **Extension point:** `attendance_records` (Phase 5 §3.16) already supports a `source` field distinguishing `auto` (WebRTC) from `manual`; adding `qr` as a third source is additive, non-breaking.
- **Future work:** Time-boxed, session-scoped QR code generation (signed, short TTL to prevent proxy attendance/sharing) and a scan-to-mark-attendance client flow, reusing the existing attendance schema and RBAC model.

## 5. Timetable

- **Extension point:** `class_sessions` (Phase 5 §3.15) already models scheduled start/end times per course; a Timetable feature is primarily a new read-optimized view/UI over existing scheduling data.
- **Future work:** Recurring session definitions (currently sessions are modeled per-occurrence), conflict detection across a student's/lecturer's enrolled courses, calendar export (iCal).

## 6. Student Portfolio

- **Extension point:** Already scoped as Epic E10 in Phase 3/15 (P3, basic version planned for GA).
- **Future work beyond GA scope:** Rich media portfolio entries, public/shareable portfolio links (requires new access-control model distinct from tenant-internal RBAC), external verification/credentialing.

## 7. Internship Management

- **Extension point:** None yet — net-new domain.
- **Future work:** New module (`modules/internships/`) following the existing modular pattern (Phase 4 §4); entities for postings, applications, employer accounts (a new actor type outside the current Student/Lecturer/Admin role model, requiring RBAC extension per Phase 8 §7).

## 8. Research Repository

- **Extension point:** Resource module (Phase 5 §3.8–3.9) already supports versioned document storage with metadata — a research repository is largely a specialized Resource sub-type with additional metadata (citations, DOI, peer-review status) and possibly cross-institution visibility (a deliberate exception to strict tenant isolation, requiring careful design).
- **Future work:** Metadata schema extension, cross-tenant sharing model (opt-in, audited), citation/search integration.

## 9. Library Management

- **Extension point:** None directly — distinct domain from course Resources (physical/licensed digital holdings vs. course-authored content).
- **Future work:** New module for catalog, loans/holds, and fines; potential integration with external library systems (ILS) via a dedicated integration adapter, consistent with the provider-agnostic pattern already used for storage (Phase 4 §10) and LLM (Phase 11 §1).

## 10. Payments

- **Extension point:** None yet — deliberately out of scope for MVP/GA per Phase 1 §8 constraints; introducing payment handling early would expand the security/compliance surface (PCI-DSS) before the core platform is proven.
- **Future work:** Integration with a PCI-compliant payment processor (never storing card data directly, per the project's prohibited-actions security posture), tuition/fee modules, marketplace transaction support (§2).

## 11. Alumni Portal

- **Extension point:** `users.status` (Phase 5 §3.2) can add an `alumni` state; portfolio (§6) and enrollment history are already retained post-graduation given the append-only, soft-delete-first data model (Phase 5 §1).
- **Future work:** Alumni-specific access scope (reduced permissions, no active enrollment), alumni networking/directory features, donation/engagement tracking (may connect to §10 Payments).

## 12. Microsoft Entra ID Integration

- **Extension point:** Explicitly called out in Phase 1 (tech stack: "OAuth (future), Microsoft Entra ID integration (future)") and Phase 8 §2 as a designed-for-but-not-implemented auth extension.
- **Future work:** OIDC federation flow alongside existing password auth, JIT (just-in-time) user provisioning mapped to existing `users`/`roles` schema, tenant-to-Entra-tenant mapping configuration in the admin module.

## Design Discipline for Future Items

None of the above require breaking changes to the Phase 4–6 architecture as currently specified — each hooks into an existing module boundary, schema extension point, or the already-established provider-agnostic integration pattern. Where an item does introduce a genuinely new cross-cutting concern (payments' compliance surface, research repository's cross-tenant sharing exception), that is called out explicitly above so it is not underestimated when eventually scheduled.

---

*This concludes the 18-phase planning and documentation set. Next: the Implementation Roadmap ([00-implementation-roadmap.md](00-implementation-roadmap.md)), synthesizing all phases into a sequenced, dependency-aware build plan for a solo developer.*
