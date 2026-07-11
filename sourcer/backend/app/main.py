"""FastAPI entry point."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_jobs import router as jobs_router
from app.api.routes_outreach import router as outreach_router
from app.api.routes_admin import router as admin_router
from app.api.routes_auth import router as auth_router
from app.api.websocket import router as websocket_router
from app.core.config import settings
from app.core.logging import setup_logging

setup_logging()

app = FastAPI(title="Sourcer API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(outreach_router)
app.include_router(admin_router)
app.include_router(websocket_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}
