# CampusHub — UI/UX Documentation

**Document Phase:** 7 of 18
**Status:** Draft for Approval
**Version:** 1.0
**Date:** 2026-07-15

---

## 1. Information Architecture

```
Root
├── Auth (Login, Offline unlock)
├── Home / Dashboard (role-adaptive)
├── Courses
│   ├── Course Overview
│   ├── Modules & Resources
│   ├── Discussions
│   ├── Assignments
│   │   └── Submission / Grading detail
│   └── Live Sessions
├── Messages (DMs)
├── Announcements
├── Search (global)
├── Portfolio (student)
├── Admin
│   ├── Institution Settings
│   ├── Departments & Courses
│   ├── Users & Roles
│   ├── Storage
│   └── Analytics & Audit Log
└── Profile / Settings (incl. sync status, offline storage management)
```

Navigation is role-adaptive: students never see Admin; lecturers see course authoring/grading; admins get a distinct navigation rail. Bottom navigation (mobile) / left nav rail (tablet/desktop/web) with 5 primary destinations max: **Home, Courses, Messages, Search, Profile** — everything else is reached within those sections to avoid overcrowding on mobile.

## 2. Navigation Patterns

- **Mobile (Android/iOS):** Bottom navigation bar + top app bar with contextual actions; full-screen drill-down navigation.
- **Tablet:** Navigation rail + master-detail layout (e.g., course list beside course detail).
- **Desktop (Windows/macOS/Linux) & Web (wide):** Persistent left navigation rail/drawer + multi-pane layout (e.g., channel list + message thread side by side).
- **Web (narrow/responsive):** Collapses to mobile pattern below 600dp width.

## 3. Key User Flows

### 3.1 Student — Offline Assignment Submission
1. Open Course → Assignments → select assignment (works from cache if offline).
2. Compose/attach submission → tap Submit.
3. If offline: UI shows "Saved — will submit when online" badge; submission stored locally with pending state.
4. On reconnect: background sync uploads; UI updates badge to "Submitted" with timestamp; push notification confirms.

### 3.2 Lecturer — Start a Virtual Class
1. Course → Live Sessions → "Start Now" or scheduled session → "Start".
2. Pre-join device check (camera/mic/bandwidth) screen.
3. In-session UI: video grid, screen-share toggle, chat panel, participant list, "End for All" control.
4. On end: automatic redirect to session summary (attendance, recording processing status).

### 3.3 Admin — Provision a New Course
1. Admin → Departments → select department → "New Course".
2. Form: name, code, term, enrollment method (manual/bulk CSV).
3. Confirmation → course appears in department list and is immediately available to enroll users.

### 3.4 Student — Offline-First Resource Browsing
1. Course → Modules → resource list shows a download icon per item and a "Downloaded" state for cached items.
2. Tap to download individually, or "Download all module" bulk action with storage-size preview before confirming.
3. Downloaded resources open instantly from local storage; a subtle indicator shows when a newer version exists server-side, prompting optional re-download.

## 4. Wireframe Descriptions (Text)

**Home Dashboard (Student):** Top app bar with tenant logo + search icon + notification bell. Below: a horizontally scrollable "Today" card row (upcoming live session, due-soon assignment). Then a vertical feed of recent announcements and activity across enrolled courses. Floating sync-status chip (bottom-right on desktop, in app bar on mobile) shows "All synced" / "3 pending" states.

**Course Overview:** Header with course name/code/term and a tab bar: Modules | Discussions | Assignments | Sessions | People. Each tab reuses the shared list/detail pattern for consistency.

**Assignment Detail:** Title, due date (with countdown/late badge), instructions body, attachments list, and a persistent bottom action bar with Submit/Save Draft. Lecturer view replaces the action bar with a submissions table (name, status, score) and a grading side panel.

**Live Session:** Full-bleed video grid (adaptive 1/2/4/9-up layout by participant count), collapsible right-side chat/participants drawer, bottom control bar (mic, camera, screen share, raise hand, leave).

**Admin Storage Dashboard:** Summary cards (used/total quota, largest departments), a bar chart of usage by department (see dataviz guidance for chart styling), and a searchable table of largest resources with delete/archive actions.

## 5. Design System — Material 3

- **Base:** Flutter's Material 3 (`useMaterial3: true`) with a custom `ColorScheme` generated from a CampusHub seed color via `ColorScheme.fromSeed`, supporting dynamic light/dark themes and optional per-tenant brand color override (institution admin can set a seed color at MVP+1).
- **Components used:** `NavigationBar`/`NavigationRail` (adaptive), `Card`, `FilledButton`/`OutlinedButton`/`TextButton` per action hierarchy, `Chip` (status badges: pending sync, late, graded), `SegmentedButton` (filters), `Badge` (unread counts), `SnackBar` (non-blocking feedback), `Dialog`/`BottomSheet` (confirmations, adaptive by platform).
- **State variants:** every interactive component implements Material 3's enabled/hovered/focused/pressed/disabled states via `WidgetStateProperty`, ensuring consistent affordance across mouse, touch, and keyboard input.

## 6. Typography

- Material 3 type scale (Display/Headline/Title/Body/Label, each Large/Medium/Small) mapped to a single brand font family (fallback to system font per platform to avoid bundling/licensing overhead and to respect platform-native rendering).
- Body text minimum 14sp (mobile) / 14px (web/desktop); never below WCAG-recommended minimums.

## 7. Spacing

- 4dp base grid; standard spacing tokens: 4, 8, 12, 16, 24, 32, 48.
- Card padding: 16dp mobile, 24dp desktop/web.
- List item minimum touch target: 48x48dp (mobile), 40x40 acceptable for mouse-only desktop contexts.

## 8. Colors

- Seed-generated Material 3 `ColorScheme` (light + dark) per tenant brand color, defaulting to CampusHub's primary blue seed if unset.
- Semantic status colors layered on top of the scheme (not replacing it): success (submissions/synced), warning (pending sync, due-soon), error (late, sync conflict, quota exceeded) — mapped to Material 3 `error`/custom `extension` colors to remain theme-aware in both light and dark modes.
- Full palette mechanics (contrast validation, categorical/sequential scales for analytics charts) follow the project's `dataviz` skill guidance when building admin analytics visualizations.

## 9. Icons

- Material Symbols (outlined style default, filled for selected/active navigation states) for full cross-platform consistency and offline bundling (no external icon CDN dependency, important for offline-first operation).

## 10. Accessibility

- WCAG 2.1 AA target (per NFR-7): minimum 4.5:1 contrast for body text, 3:1 for large text/icons.
- All interactive elements reachable and operable via keyboard (desktop/web) and screen reader (TalkBack/VoiceOver) with semantic labels (`Semantics` widgets) on icon-only buttons.
- Respect platform text-scaling settings up to 200% without layout breakage (test via Flutter's `MediaQuery.textScaler`).
- Video/session UI provides captions hook-point for future live-caption support (Phase 18 candidate) and never conveys status via color alone (status chips always pair color with text/icon).

## 11. Responsive Behaviour

| Breakpoint | Layout |
|---|---|
| < 600dp (mobile) | Single column, bottom nav, full-screen drill-down |
| 600–1024dp (tablet/small desktop) | Navigation rail, optional master-detail two-pane |
| > 1024dp (desktop/web wide) | Persistent nav rail/drawer, multi-pane (list + detail, or list + detail + context panel) |

Layout implemented via Flutter's `LayoutBuilder`/adaptive scaffolding utilities, shared across all six target platforms from one widget tree with breakpoint-driven composition rather than platform-specific forks, except where a platform capability genuinely differs (e.g., desktop drag-and-drop file upload vs. mobile file picker).

---

*Next document: Phase 8 — Security Design.*
