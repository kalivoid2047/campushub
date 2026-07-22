# CampusHub — Deployment Guide

**Document Phase:** 13 of 18
**Status:** Approved (Revised — Docker/containers removed from project)
**Version:** 2.0
**Date:** 2026-07-15

> **Revision note (v2.0):** Per project decision, CampusHub does **not** use Docker, containers, or Kubernetes anywhere in development or production. All services run as native processes.

---

## 1. Development Environment (Native, No Containers)

Prerequisites installed directly on the developer machine:

| Component | Install |
|---|---|
| Python 3.12+ | python.org installer / package manager |
| PostgreSQL 16+ | Native installer; create `campushub` role + database |
| Redis 7+ | Native install (on Windows: Memurai or Redis via WSL-free native builds) |
| MinIO | Single native binary (`minio server ~/minio-data`) — optional early on; storage layer falls back to local filesystem when unset |
| Flutter SDK | Stable channel |
| NGINX (optional in dev) | Only needed when testing production routing rules locally |

Bootstrap:

```bash
cp .env.example .env
make install     # venv + backend deps
make migrate     # alembic upgrade head
make seed        # dev fixtures
make run         # uvicorn app.main:app --reload
```

The Flutter client targets `http://localhost:8000` via `--dart-define=API_BASE_URL=...` per-flavor configuration (dev/staging/prod flavors, Phase 16).

`.env.example` documents all required environment variables; secrets are never committed (Phase 8 §8 A05).

## 2. Process Model

Each backend workload is an OS process, managed by systemd (Linux production) or run directly in a terminal (development):

| Process | Command | Unit file |
|---|---|---|
| API | `uvicorn app.main:app --workers 4` | `infra/systemd/campushub-api.service` |
| Background worker | `python -m app.workers.main` | `infra/systemd/campushub-worker.service` |
| SFU (WebRTC) | LiveKit server (native binary) | `infra/systemd/campushub-livekit.service` |

Health check endpoints (`/healthz`, `/readyz`) are exposed by the API for systemd watchdog integration and NGINX upstream checks.

## 3. CI/CD (GitHub Actions)

Pipeline stages, triggered on PR and on merge to `main`:

1. **Lint & Format** — backend (ruff/black), client (dart format/flutter analyze).
2. **Unit + Integration Tests** — per Phase 12 §2–3; CI provisions PostgreSQL/Redis via GitHub Actions **service runners or native installs on the runner** (not containers on developer machines — GitHub-hosted runner internals are outside the project's no-Docker policy, but pipelines are written to use natively installed services where practical).
3. **Security Scan** — dependency audit (`pip-audit`, Dart equivalent).
4. **Build** — Flutter build artifacts per target platform (matrix build: Android APK/AAB, iOS IPA via macOS runner, Windows/Linux/macOS desktop bundles, Web build); backend packaged as a versioned source artifact (wheel/sdist).
5. **Publish** — upload platform artifacts and backend wheel to release storage.
6. **Deploy (main branch only, manual approval gate for production)** — SSH-based deploy: push the new wheel to the server, install into the venv, run `alembic upgrade head`, restart systemd units.

Deployment to production requires a manual approval step (GitHub Environments protection rule) — no fully automatic prod deploys.

## 4. Production Deployment (Native)

- **Host:** One or more Linux VMs (or bare metal). Baseline single-server layout: NGINX + API (uvicorn workers) + worker + PostgreSQL + Redis + MinIO on one adequately-sized host; split PostgreSQL/Redis/MinIO onto separate hosts as load grows.
- **Ingress:** Native NGINX install handles TLS termination (certbot/Let's Encrypt for renewal) and routes `/api/*`, `/ws/*` to uvicorn on localhost — config at `infra/nginx/campushub.conf`.
- **Process management:** systemd units (`infra/systemd/`) with `Restart=on-failure`; `sudo systemctl restart campushub-api` is the deploy-time restart.
- **Scaling:** vertical first (more uvicorn workers, bigger host), then horizontal — additional API hosts behind NGINX upstream load balancing; WebSocket fan-out remains scale-safe via Redis pub/sub (Phase 4 §8) so any host can serve any client.
- **Secrets:** environment file (`/opt/campushub/.env`, mode 600, owned by the service user) or a secret manager agent — never committed to source control.
- **Database/Redis:** managed cloud services remain the preferred option for solo-developer operability; native self-hosted installs with automated backup are the documented fallback.

## 5. Monitoring

- Metrics: Prometheus-compatible `/metrics` endpoint on the API and worker; Prometheus + Grafana installed natively (or a hosted metrics service). Standard dashboards: request rate/latency/error rate, sync queue depth, active WebRTC sessions, storage quota utilization.
- Alerting: threshold-based alerts (error rate spike, service restarts, storage near-exhaustion, backup job failure) routed to the developer via email/Slack webhook, tuned for a single on-call operator.

## 6. Logging

- Structured JSON logs (`request_id`, `tenant_id`, `user_id` where applicable) written to journald via systemd and optionally shipped to a centralized aggregator (hosted logging service or native Loki install) for correlation with the `request_id` returned in API error responses (Phase 6 §4).
- Audit logs (Phase 8 §9) are a distinct, append-only application-level record in PostgreSQL — never solely reliant on infrastructure log retention.

## 7. Scaling

- Stateless API processes scale horizontally across hosts behind NGINX; session-affinity is unnecessary for REST and WebSockets are made scale-safe via Redis pub/sub.
- Database scaling path: read replicas for reporting/analytics queries before considering sharding; sharding by `tenant_id` is the documented long-term path (not required at initial scale per Phase 1 §9).
- SFU (Virtual Classroom) runs on dedicated host(s) with UDP exposed, sized from Phase 12 §5 load-test results; a given class session's participants land on the same SFU host.

## 8. Backups

- Implements the strategy defined in Phase 8 §10: automated daily PostgreSQL dumps + WAL archiving (`pgBackRest` or `wal-g` running natively), versioned object storage, tested quarterly restores.
- Backup jobs run as systemd timers (`OnCalendar=daily`), with failure alerts wired into the monitoring stack (§5) — a silent backup failure is treated as a high-severity incident.

---

*Related: Phase 14 — Project Management; scripts/ops/backup_verify.sh.*
