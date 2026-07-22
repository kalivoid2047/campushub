# CampusHub — Folder Structure

**Document Phase:** 16 of 18
**Status:** Draft for Approval
**Version:** 1.0
**Date:** 2026-07-15

---

## 1. Repository Layout (Monorepo)

```
CampusHub/
├── client/                      # Flutter app (all platforms)
├── backend/                     # FastAPI application
├── infra/                       # NGINX + systemd configs for native deployment
├── docs/                        # This documentation set (Phases 1-18 + roadmap)
├── scripts/                     # Dev/ops helper scripts
├── .github/
│   └── workflows/                # CI/CD pipelines
├── Makefile
└── README.md
```

## 2. Flutter Client (`client/`) — Feature-First

```
client/
├── lib/
│   ├── main.dart
│   ├── app/                      # App shell, routing, theming (Material 3 setup)
│   │   ├── router.dart
│   │   └── theme/
│   ├── core/                     # Cross-cutting: DI, network client, error types, constants
│   │   ├── network/
│   │   ├── storage/               # SQLite setup, secure storage wrapper
│   │   ├── sync/                  # Sync engine (Phase 9)
│   │   └── error/
│   ├── features/
│   │   ├── auth/
│   │   │   ├── data/               # repositories, data sources (local + remote)
│   │   │   ├── domain/             # entities, use cases
│   │   │   └── presentation/       # widgets, state management
│   │   ├── tenancy_admin/
│   │   ├── resources/
│   │   ├── communication/
│   │   ├── assignments/
│   │   ├── virtual_classroom/
│   │   ├── attendance/
│   │   ├── search/
│   │   ├── portfolio/
│   │   └── shared/                 # Design-system widgets (Phase 7 components)
│   └── generated/                 # Codegen output (localization, etc.)
├── test/                          # Unit + widget tests, mirrors lib/ structure
├── integration_test/              # End-to-end flows (Phase 12 §7)
├── assets/
│   ├── icons/
│   ├── images/
│   └── fonts/
├── android/ ios/ windows/ macos/ linux/ web/   # Platform shells (Flutter-generated)
└── pubspec.yaml
```

Each `features/<feature>/` follows Clean Architecture (`data → domain → presentation`) and the Repository Pattern consistently, per the project's stated development philosophy.

## 3. FastAPI Backend (`backend/`) — Modular by Domain

```
backend/
├── app/
│   ├── main.py                    # FastAPI app factory
│   ├── core/                      # Config, security (JWT), DB session, Redis client, logging
│   │   ├── config.py
│   │   ├── security.py
│   │   └── db.py
│   ├── modules/
│   │   ├── iam/                    # Auth, tenancy, RBAC
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── repository.py
│   │   │   ├── models.py
│   │   │   └── schemas.py          # Pydantic request/response models
│   │   ├── resources/
│   │   ├── communication/
│   │   ├── assignments/
│   │   ├── virtual_classroom/
│   │   ├── attendance/
│   │   ├── search/
│   │   ├── admin/
│   │   ├── sync/
│   │   └── ai/                     # Post-MVP (Phase 11)
│   ├── workers/                    # Background workers (recording processing, notifications)
│   └── shared/                     # Cross-module utilities, base repository classes
├── migrations/                     # Alembic migrations (source of truth for schema, Phase 5)
├── tests/
│   ├── unit/
│   └── integration/                 # local Postgres/Redis test DB (Phase 12 §3)
└── pyproject.toml
```

Each module under `modules/` is self-contained (router/service/repository/models/schemas) to support the future microservice-extraction path defined in Phase 4 §4 without cross-module refactors.

## 4. Infrastructure (`infra/`)

> **Note (v1.1):** CampusHub does not use Docker/containers — infra holds native deployment configs only (Phase 13 v2.0).

```
infra/
├── nginx/
│   └── campushub.conf              # Production reverse proxy (TLS, /api, /ws routing)
├── systemd/
│   ├── campushub-api.service       # uvicorn API workers
│   └── campushub-worker.service    # background worker
└── terraform/ (optional, if IaC-managed VM provisioning is adopted)
```

## 5. Documentation (`docs/`)

```
docs/
├── 00-implementation-roadmap.md
├── 01-project-charter.md
├── 02-software-requirements-specification.md
├── 03-product-requirements-document.md
├── 04-system-architecture.md
├── 05-database-design.md
├── 06-api-design.md
├── 07-ui-ux.md
├── 08-security-design.md
├── 09-offline-sync.md
├── 10-virtual-classroom.md
├── 11-ai-module.md
├── 12-testing-strategy.md
├── 13-deployment-guide.md
├── 14-project-management.md
├── 15-feature-backlog.md
├── 16-folder-structure.md
├── 17-coding-standards.md
└── 18-future-expansion.md
```

## 6. Assets

Institutional/brand assets (per-tenant logos, seed colors) are **not** stored in the repository — they are runtime-configurable data (Phase 5 `tenants` table + object storage), keeping the repo tenant-agnostic. Only default/CampusHub-brand static assets live in `client/assets/`.

## 7. Testing

Test directories mirror source structure 1:1 in both `client/test/` and `backend/tests/`, so any source file's corresponding test is locatable by path convention alone — no separate test-discovery mapping needed.

## 8. Scripts (`scripts/`)

```
scripts/
├── dev/
│   ├── seed_db.py
│   └── reset_env.sh
├── ci/
│   └── run_integration_tests.sh
└── ops/
    ├── backup_verify.sh
    └── tenant_provision.py
```

## 9. CI/CD

- `.github/workflows/`: `ci.yml` (lint/test/build per Phase 13 §3), `deploy-staging.yml`, `deploy-production.yml` (manual approval gate; SSH-based native deploy per Phase 13 §3).

---

*Next document: Phase 17 — Coding Standards.*
