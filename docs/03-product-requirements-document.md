# CampusHub — Product Requirements Document (PRD)

**Document Phase:** 3 of 18
**Status:** Draft for Approval
**Version:** 1.0
**Date:** 2026-07-15

---

## 1. Problem Statement

Students and lecturers at colleges and universities are forced to juggle 5–9 disconnected tools — an LMS for coursework, a video app for classes, a chat app for community, a drive for files, and a separate system for grades and attendance. Each tool has its own login, its own offline (or lack of offline) behavior, and no shared context. This fragmentation causes lost work, missed communication, poor engagement visibility for lecturers, and total exclusion for students with unreliable connectivity. Institutions need one coherent, offline-capable, secure platform that serves as the digital front door for academic life.

## 2. Target Users

1. **Students** — primary daily users; need reliable access to content and communication regardless of connectivity.
2. **Lecturers** — need efficient authoring, grading, and live-teaching tools with visibility into student engagement.
3. **Institution/Department Admins** — need control over users, structure, storage, and compliance.
4. **Platform Super-Admins** — operate the multi-tenant platform itself across institutions.

## 3. Personas

### Persona 1 — Amara, Undergraduate Student
- 20 years old, second-year Computer Science student, uses an Android phone as her primary device, home Wi-Fi is intermittent.
- Needs: download lecture notes before commuting, submit assignments even when offline, get instant announcements about class changes, chat with classmates on group projects.
- Frustration: currently loses submissions when Google Classroom fails to sync on flaky data; uses 4 separate apps daily.

### Persona 2 — Dr. Bello, Lecturer
- Teaches 3 courses across 2 departments, splits time between in-person and remote teaching.
- Needs: upload slides once and have them versioned, run virtual classes with screen share, grade submissions quickly with rubric templates, see which students are disengaged.
- Frustration: Zoom, Moodle, and WhatsApp groups don't talk to each other; attendance is manually reconciled.

### Persona 3 — Ngozi, Institution Admin
- IT/Registrar staff responsible for onboarding departments and enforcing data policy.
- Needs: provision courses and accounts in bulk, enforce storage limits, audit access, ensure the institution's data never mixes with another institution's on the shared platform.
- Frustration: currently no single audit trail across the tools in use.

### Persona 4 — Chidi, Platform Super-Admin
- Operates CampusHub across multiple institution deployments.
- Needs: provision new tenants safely, monitor system health, manage global configuration and integrations.

## 4. Epics

| Epic | Summary |
|---|---|
| E1 — Identity & Multi-Tenancy | Auth, roles, tenant isolation |
| E2 — Learning Resources | Upload, organize, offline download of course content |
| E3 — Communication | Discussions, DMs, announcements |
| E4 — Assignments & Grading | Creation, submission, grading, feedback |
| E5 — Virtual Classroom | Live sessions, screen share, recording, chat |
| E6 — Attendance | Automatic + manual tracking and reporting |
| E7 — Search | Cross-resource, permission-scoped search |
| E8 — Admin & Analytics | Tenant/user/storage management, engagement dashboards |
| E9 — Offline Sync Engine | Local cache, queued actions, conflict resolution |
| E10 — Academic Portfolio | Student record of work and achievements |

## 5. User Stories (Representative Sample)

### Epic E1 — Identity & Multi-Tenancy
- As a **student**, I want to log in once and stay authenticated offline, so I can use the app without constant reconnection.
- As an **institution admin**, I want my institution's data fully isolated from other institutions, so I can guarantee compliance to my leadership.
- As a **super admin**, I want to provision a new tenant in minutes, so onboarding a new institution is fast.

### Epic E2 — Learning Resources
- As a **lecturer**, I want to upload lecture notes to a specific course module, so students find them in context.
- As a **student**, I want to download resources for offline reading, so I can study without data costs.

### Epic E3 — Communication
- As a **student**, I want to post in a course discussion and see replies, so I can collaborate with classmates.
- As a **lecturer**, I want to send an announcement to all students in a course, so everyone is notified of changes.

### Epic E4 — Assignments & Grading
- As a **student**, I want to draft and submit an assignment while offline, so I don't miss deadlines due to poor connectivity.
- As a **lecturer**, I want to grade submissions with a rubric and leave feedback, so grading is fast and consistent.

### Epic E5 — Virtual Classroom
- As a **lecturer**, I want to start a live class with screen sharing, so I can teach remotely.
- As a **student**, I want to join a class and see it doesn't require a separate app, so my workflow stays unified.

### Epic E6 — Attendance
- As a **lecturer**, I want attendance automatically recorded from virtual class join/leave events, so I don't do manual roll call.

### Epic E7 — Search
- As a **student**, I want to search across all my course resources and discussions, so I can find information quickly.

### Epic E8 — Admin & Analytics
- As an **institution admin**, I want to see storage usage per department, so I can manage quotas proactively.

### Epic E9 — Offline Sync
- As a **student**, I want clear indication of what's synced vs. pending, so I trust my offline work isn't lost.

### Epic E10 — Academic Portfolio
- As a **student**, I want a portfolio view of my completed courses and grades, so I can showcase my academic record.

## 6. Acceptance Criteria (Story-Level Examples)

- **Offline submission**: Given a student is offline, when they submit an assignment, then the submission is stored locally with a "pending sync" state and is uploaded automatically (without duplication) once connectivity returns.
- **Tenant isolation**: Given two tenants exist, when an Institution Admin from Tenant A queries any list endpoint, then no record belonging to Tenant B is returned, even via direct ID lookup.
- **Virtual classroom attendance**: Given a student joins a live session for at least the configured minimum duration, when the session ends, then an attendance record is automatically created for that student.

## 7. Priorities (MVP Ranking)

| Priority | Epics |
|---|---|
| P0 (MVP-critical) | E1 Identity & Multi-Tenancy, E2 Learning Resources, E9 Offline Sync Engine |
| P1 (MVP) | E3 Communication, E4 Assignments & Grading, E8 Admin & Analytics (basic) |
| P2 (Post-MVP, pre-GA) | E5 Virtual Classroom, E6 Attendance |
| P3 (Post-GA) | E7 Search (advanced/AI), E10 Academic Portfolio, Phase 18 future expansions |

## 8. Success Metrics

| Metric | Target |
|---|---|
| Daily Active Users per pilot institution | ≥60% of enrolled students within first semester |
| Third-party app usage reduction (survey-based) | ≥80% reduction reported by pilot users |
| Offline submission success rate | ≥99% of offline-drafted submissions sync without data loss |
| Virtual classroom session completion rate | ≥95% of scheduled sessions complete without critical failure |
| Security incidents (cross-tenant leakage) | 0 |
| Time-to-onboard a new tenant | < 30 minutes (Super Admin self-service) |

## 9. Roadmap (Product View)

| Stage | Focus |
|---|---|
| MVP | Identity/multi-tenancy, resources, offline sync, basic communication, assignments |
| Beta | Virtual classroom, attendance, admin analytics, security hardening |
| GA | Full cross-platform parity, search, academic portfolio |
| Post-GA | AI module (Phase 11), Phase 18 future expansions (marketplace, payments, alumni, etc.) |

---

*Next document: Phase 4 — System Architecture Document.*
