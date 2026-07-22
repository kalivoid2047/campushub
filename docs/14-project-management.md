# CampusHub — Project Management

**Document Phase:** 14 of 18
**Status:** Draft for Approval
**Version:** 1.0
**Date:** 2026-07-15

---

## 1. Development Roadmap (High-Level)

Aligned to Phase 1 §10 timeline and Phase 3 §9 product roadmap:

| Stage | Duration (approx.) | Scope |
|---|---|---|
| Stage 0 — Planning | Weeks 0–2 | This document set (Phases 1–18) |
| Stage 1 — MVP Foundation | Months 1–3 | Multi-tenancy, auth/RBAC, resources, offline sync core |
| Stage 2 — Collaboration Core | Months 3–5 | Communication, assignments/grading, basic admin |
| Stage 3 — Live & Analytics | Months 5–7 | Virtual classroom, attendance, admin analytics, security hardening |
| Stage 4 — Beta | Month 7–8 | Pilot institution onboarding, UAT feedback loop |
| Stage 5 — GA | Month 9–10 | Full platform parity, search, portfolio, launch |
| Stage 6 — Post-GA | Ongoing | AI module (Phase 11), Phase 18 future expansions |

## 2. Milestones

| Milestone | Exit Criteria |
|---|---|
| M0 — Docs Approved | All 18 phase documents reviewed and accepted |
| M1 — Auth & Tenancy Live | A tenant can be provisioned, users can log in, RLS isolation verified (AC-1) |
| M2 — Offline Resource MVP | Resources uploadable/downloadable, offline read verified (AC-2 partial) |
| M3 — Communication + Assignments | Discussions, announcements, assignment submit/grade functional, offline submission verified (AC-2 full) |
| M4 — Virtual Classroom Live | Session start/join/screen-share/attendance functional (AC-3) |
| M5 — Security Hardening Complete | OWASP checklist (Phase 8 §8) passed, pen test performed |
| M6 — Beta Launch | Pilot institution onboarded, UAT feedback loop active |
| M7 — GA | All platforms shipped, success metrics (Phase 3 §8) instrumented |

## 3. Sprint Plan (Solo-Developer, 2-Week Sprints)

Given a solo developer with AI-assisted development, sprints are scoped narrower than a team cadence to keep each sprint independently shippable/demoable:

| Sprint | Focus |
|---|---|
| 1–2 | Repo scaffolding (Phase 16), CI skeleton, DB schema + migrations (Phase 5), tenant/auth module |
| 3–4 | RBAC, offline auth artifact, Flutter app shell + navigation (Phase 7) |
| 5–6 | Resource module (upload/versioning) + client offline download manager |
| 7–8 | SQLite mirror + sync engine core (Phase 9), sync API endpoints |
| 9–10 | Communication module (channels, messages, announcements) + WebSocket infra |
| 11–12 | Assignments + submissions + offline submission flow |
| 13–14 | Grading + basic admin (users, departments, courses) |
| 15–16 | Virtual classroom: signaling + SFU integration + join flow |
| 17–18 | Screen share, recording, attendance auto-capture |
| 19–20 | Admin analytics, audit log, storage quota UI |
| 21–22 | Security hardening pass, OWASP checklist, pen test fixes |
| 23–24 | Beta pilot onboarding, UAT fixes |
| 25–26 | Search, portfolio, cross-platform polish, GA prep |

Detailed task-level breakdown is maintained in Phase 15 (Feature Backlog) and the final Implementation Roadmap document.

## 4. Kanban Workflow

Columns: `Backlog → Ready → In Progress → In Review (self/AI-review) → Testing → Done`.

- **Ready** requires: acceptance criteria defined, dependent schema/API contract stable.
- **In Review**: for a solo developer, this step is AI-assisted code review (`/code-review`) plus a self-review pass against Phase 17 coding standards before merge.
- **Testing**: automated CI gates (Phase 12) must pass; manual verification for UI-affecting changes per the `verify`/`run` workflow.
- WIP limit of 2 "In Progress" items enforced to preserve focus given solo capacity.

## 5. Git Strategy

- Single repository (monorepo: `client/`, `backend/`, `infra/`, `docs/` — see Phase 16) to simplify cross-cutting changes (e.g., API contract + client consumer in one PR) for a solo developer.
- Trunk-based development with short-lived feature branches (`feat/`, `fix/`, `chore/` prefixes), merged via PR even solo, to keep CI gates and review discipline consistent.

## 6. Branching Model

```
main            — always deployable; protected, requires CI pass
feat/<slug>     — feature branches off main, short-lived (<1 week ideally)
fix/<slug>      — bug fix branches
release/<x.y>   — cut only if a stabilization window is needed before a milestone; otherwise main ships directly
```

No long-lived `develop` branch — trunk-based flow keeps the solo-developer workflow simple and avoids merge-debt accumulation.

## 7. Issue Templates

- **Bug Report:** Steps to reproduce, expected vs. actual, environment (platform/OS/version), severity, related module (per Phase 4 module list).
- **Feature Request:** User story format (per Phase 3 §5), linked epic, acceptance criteria, priority (MoSCoW per Phase 2).
- **Security Issue:** Private disclosure path (not public issue), affected component, severity (per Phase 8 threat categories), reproduction steps.

## 8. Pull Request Template

```markdown
## Summary
What changed and why (link issue/epic).

## Scope
- [ ] Backend
- [ ] Client
- [ ] Docs
- [ ] Infra

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests pass locally
- [ ] Manually verified (describe how)

## Checklist
- [ ] Follows Phase 17 coding standards
- [ ] No secrets/credentials committed
- [ ] Tenant isolation preserved for any new query (Phase 5 §1 / Phase 8 §1)
```

## 9. Release Strategy

- Continuous deployment to staging on every merge to `main` (auto).
- Production releases are tagged, manually approved (Phase 13 §3), and accompanied by release notes generated from merged PR titles/labels.
- Feature flags (simple config-driven, not a full flag platform) used to decouple deploy from release for risk-sensitive features (e.g., new AI module capabilities, Phase 11).

## 10. Versioning

- **Backend/API:** Semantic versioning for the API surface; breaking changes require a new `/api/v2` path (Phase 6 §1), not silently altering `/v1`.
- **Client apps:** Platform-native versioning (`major.minor.patch+build`), synchronized across platform stores; `minor` bumps for new features, `patch` for fixes, `major` reserved for architecture-level changes (e.g., a future breaking sync-protocol revision).
- **Database schema:** Alembic migration version chain is the source of truth; no manual schema edits outside migrations.

---

*Next document: Phase 15 — Complete Feature Backlog.*
