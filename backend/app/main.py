"""FastAPI entry point."""
from __future__ import annotations

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes_jobs import router as jobs_router
from app.api.routes_outreach import router as outreach_router
from app.api.routes_admin import router as admin_router
from app.api.routes_auth import router as auth_router
from app.api.websocket import router as websocket_router
from app.api.routes_workflow import router as workflow_router
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
app.include_router(workflow_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}


@app.get("/health/ready")
def readiness() -> JSONResponse:
    """Report external dependency readiness without exposing credentials."""
    from app.core.db import get_redis, get_supabase

    checks: dict[str, dict[str, object]] = {}

    try:
        checks["redis"] = {"ok": bool(get_redis().ping())}
    except Exception as exc:
        checks["redis"] = {"ok": False, "error": type(exc).__name__}

    try:
        get_supabase().table("orgs").select("id").limit(1).execute()
        checks["database"] = {"ok": True}
    except Exception as exc:
        checks["database"] = {"ok": False, "error": type(exc).__name__}

    try:
        response = httpx.get(f"{settings.browser_agent_url}/health", timeout=3)
        response.raise_for_status()
        checks["browser_agent"] = {"ok": True}
    except Exception as exc:
        checks["browser_agent"] = {"ok": False, "error": type(exc).__name__}

    has_ai_key = bool(
        settings.gemini_api_key
        or settings.gemini_api_keys
        or settings.openrouter_api_key
    )
    checks["llm"] = {
        "ok": has_ai_key,
        "provider": settings.ai_provider,
        "model": settings.get_model_for_task("scoring"),
    }

    ready = all(bool(check["ok"]) for check in checks.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "degraded", "checks": checks},
    )
