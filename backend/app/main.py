from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import engine
from app.modules.iam.router import admin_router as iam_admin_router
from app.modules.iam.router import router as iam_router
from app.modules.resources.router import router as resources_router
from app.modules.communication.router import router as communication_router
from app.modules.communication.ws_router import ws_router as communication_ws_router
from app.modules.assignments.router import router as assignments_router
from app.modules.virtual_classroom.router import router as virtual_classroom_router
from app.modules.attendance.router import router as attendance_router
from app.modules.search.router import router as search_router
from app.modules.portfolio.router import router as portfolio_router
from app.modules.admin.router import member_router as admin_member_router
from app.modules.admin.router import router as admin_router
from app.modules.sync.router import router as sync_router

from app.modules.assignments import sync_handler as assignments_sync_handler
from app.modules.communication import sync_handler as communication_sync_handler

settings = get_settings()

# Feature modules register their offline-sync entity handlers at startup.
assignments_sync_handler.register()
communication_sync_handler.register()

app = FastAPI(
    title="CampusHub API",
    version="0.1.0",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
)

# The Flutter client is Bearer-token-only (no cookies), so a permissive
# wildcard origin carries no CSRF/credential-theft risk (docs/08 section 2).
app.add_middleware(
    CORSMiddleware,
    allow_origins=(["*"] if settings.cors_origins == "*" else settings.cors_origins.split(",")),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(iam_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(iam_admin_router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(resources_router, prefix="/api/v1", tags=["resources"])
app.include_router(communication_router, prefix="/api/v1", tags=["communication"])
app.include_router(communication_ws_router, prefix="/api/v1", tags=["realtime"])
app.include_router(assignments_router, prefix="/api/v1", tags=["assignments"])
app.include_router(virtual_classroom_router, prefix="/api/v1", tags=["virtual-classroom"])
app.include_router(attendance_router, prefix="/api/v1", tags=["attendance"])
app.include_router(search_router, prefix="/api/v1", tags=["search"])
app.include_router(portfolio_router, prefix="/api/v1", tags=["portfolio"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(admin_member_router, prefix="/api/v1", tags=["courses"])
app.include_router(sync_router, prefix="/api/v1/sync", tags=["sync"])


@app.get("/healthz", tags=["ops"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz", tags=["ops"])
async def readyz() -> JSONResponse:
    """Reports ready only once the database and Redis are both reachable —
    the two stateful dependencies every request path relies on (docs/13
    section 1)."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503, content={"status": "not_ready", "detail": "database unavailable"}
        )

    try:
        import redis.asyncio as redis_asyncio

        client = redis_asyncio.from_url(settings.redis_url)
        try:
            await client.ping()
        finally:
            await client.aclose()
    except Exception:
        return JSONResponse(
            status_code=503, content={"status": "not_ready", "detail": "redis unavailable"}
        )

    return JSONResponse(status_code=200, content={"status": "ready"})
