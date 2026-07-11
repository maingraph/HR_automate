"""Admin endpoints: credentials status + update, pipeline logs."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import CurrentUser, get_current_user, require_platform_admin
from app.core.db import get_supabase
from app.core.logging import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

class CredentialsPatch(BaseModel):
    section: str  # linkedin | telegram | ai | settings
    # linkedin
    li_at: Optional[str] = None
    li_send_min_delay: Optional[int] = None
    li_send_max_delay: Optional[int] = None
    li_headless: Optional[bool] = None
    # ai
    openrouter_key: Optional[str] = None
    gemini_key: Optional[str] = None
    # settings
    operator_tg_username: Optional[str] = None


@router.get("/credentials")
async def get_credentials(
    _admin: CurrentUser = Depends(require_platform_admin),
) -> dict[str, Any]:
    """Return the current state of all credentials (values masked, statuses exposed)."""
    from app.core.config import settings

    # Check if li_at cookie is set and try to infer expiry
    li_at = os.environ.get("LI_AT_COOKIE", "")
    li_at_status: str = "unknown"
    if li_at:
        # We can't call LinkedIn to verify, so just check if the cookie looks non-empty
        li_at_status = "valid" if len(li_at) > 20 else "expired"

    # Check for Telegram session file
    _backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    session_paths = [
        os.path.join(_backend_dir, "sessions", "sourcer_session.session"),
        "sessions/sourcer_session.session",
        "backend/sessions/sourcer_session.session",
        "data/sourcer.session",
        "../data/sourcer.session",
        "sourcer.session",
    ]
    tg_session_exists = any(os.path.exists(p) for p in session_paths)

    return {
        "li_at_status": li_at_status,
        "li_at_set_at": os.environ.get("LI_AT_SET_AT"),
        "tg_session_exists": tg_session_exists,
        "openrouter_key_set": bool(os.environ.get("OPENROUTER_API_KEY")),
        "gemini_key_set": bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
        "operator_tg_username": settings.operator_telegram_username or "",
        "li_send_min_delay": settings.li_send_min_delay,
        "li_send_max_delay": settings.li_send_max_delay,
        "li_headless": settings.li_headless,
    }


@router.patch("/credentials")
async def patch_credentials(
    payload: CredentialsPatch,
    _admin: CurrentUser = Depends(require_platform_admin),
) -> dict[str, Any]:
    """Update credential/config values.

    NOTE: This writes values to the running process environment only.
    For persistence across restarts, the user must update their .env file.
    This endpoint is intentionally lightweight — no DB writes for secrets.
    """
    updated: list[str] = []

    if payload.section == "linkedin":
        if payload.li_at:
            os.environ["LI_AT_COOKIE"] = payload.li_at
            os.environ["LI_AT_SET_AT"] = datetime.utcnow().isoformat()
            updated.append("LI_AT_COOKIE")
        if payload.li_send_min_delay is not None:
            os.environ["LI_SEND_MIN_DELAY"] = str(payload.li_send_min_delay)
            updated.append("LI_SEND_MIN_DELAY")
        if payload.li_send_max_delay is not None:
            os.environ["LI_SEND_MAX_DELAY"] = str(payload.li_send_max_delay)
            updated.append("LI_SEND_MAX_DELAY")
        if payload.li_headless is not None:
            os.environ["LI_HEADLESS"] = str(payload.li_headless).lower()
            updated.append("LI_HEADLESS")

    elif payload.section == "ai":
        if payload.openrouter_key:
            os.environ["OPENROUTER_API_KEY"] = payload.openrouter_key
            updated.append("OPENROUTER_API_KEY")
        if payload.gemini_key:
            os.environ["GEMINI_API_KEY"] = payload.gemini_key
            os.environ["GOOGLE_API_KEY"] = payload.gemini_key
            updated.append("GEMINI_API_KEY")

    elif payload.section == "settings":
        if payload.operator_tg_username is not None:
            os.environ["OPERATOR_TELEGRAM_USERNAME"] = payload.operator_tg_username
            updated.append("OPERATOR_TELEGRAM_USERNAME")

    elif payload.section == "telegram":
        # Nothing to patch via API — Telegram sessions are file-based
        pass

    else:
        raise HTTPException(status_code=400, detail=f"Unknown section: {payload.section!r}")

    log.info("Credentials updated: %s", updated)
    return {"ok": True, "updated": updated}


# ---------------------------------------------------------------------------
# Pipeline run logs
# ---------------------------------------------------------------------------

@router.get("/pipeline-runs")
async def list_pipeline_runs(
    job_id: Optional[str] = None,
    limit: int = 200,
    current: CurrentUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Return recent pipeline_runs rows for the caller's org, newest first."""
    sb = get_supabase()
    q = sb.table("pipeline_runs").select("*").eq("org_id", current.org_id).order("started_at", desc=True).limit(limit)
    if job_id:
        q = q.eq("job_id", job_id)
    r = q.execute()
    return r.data or []


# ---------------------------------------------------------------------------
# AI Model Configuration
# ---------------------------------------------------------------------------

@router.get("/models")
async def get_model_config(
    _admin: CurrentUser = Depends(require_platform_admin),
) -> dict[str, Any]:
    """Get current model configuration for all tasks.
    
    Returns:
        {
            "ai_provider": "gemini" | "openrouter",
            "available_models": {
                "gemini": [...],
                "openrouter": [...]
            },
            "current_models": {
                "job_planning": "gemini-2.0-flash",
                ...
            }
        }
    """
    from app.core.config import settings
    
    return {
        "ai_provider": settings.ai_provider,
        "available_models": {
            "gemini": [
                "gemini-2.0-flash-exp",
                "gemini-exp-1206",
                "gemini-2.0-flash-thinking-exp-01-21",
                "gemini-1.5-pro",
                "gemini-1.5-flash",
            ],
            "openrouter": [
                "google/gemini-2.0-flash-exp:free",
                "google/gemini-exp-1206:free",
                "anthropic/claude-3.5-sonnet",
                "anthropic/claude-3-opus",
                "openai/gpt-4o",
                "openai/gpt-4o-mini",
                "meta-llama/llama-3.3-70b-instruct",
            ]
        },
        "current_models": {
            "job_planning": settings.get_model_for_task("job_planning"),
            "scoring": settings.get_model_for_task("scoring"),
            "vacancy_structure": settings.get_model_for_task("vacancy_structure"),
            "outreach_classify": settings.get_model_for_task("outreach_classify"),
            "outreach_draft": settings.get_model_for_task("outreach_draft"),
            "channel_discovery": settings.get_model_for_task("channel_discovery"),
        }
    }


@router.patch("/models")
async def update_model_config(
    payload: dict,
    _admin: CurrentUser = Depends(require_platform_admin),
) -> dict[str, Any]:
    """Update model configuration for specific tasks.
    
    Request:
        {
            "ai_provider": "gemini" | "openrouter",  # optional
            "models": {
                "job_planning": "gemini-2.0-flash-exp",  # optional
                "scoring": "gemini-exp-1206",  # optional
                ...
            }
        }
    
    Updates environment variables (runtime only - not persisted to .env).
    """
    from app.core.config import get_settings
    
    updated: list[str] = []
    
    # Update AI_PROVIDER if provided
    if "ai_provider" in payload:
        os.environ["AI_PROVIDER"] = payload["ai_provider"]
        updated.append("AI_PROVIDER")
    
    # Update task-specific models
    if "models" in payload:
        model_env_map = {
            "job_planning": "MODEL_JOB_PLANNING",
            "scoring": "MODEL_SCORING",
            "vacancy_structure": "MODEL_VACANCY_STRUCTURE",
            "outreach_classify": "MODEL_OUTREACH_CLASSIFY",
            "outreach_draft": "MODEL_OUTREACH_DRAFT",
            "channel_discovery": "MODEL_CHANNEL_DISCOVERY",
        }
        
        for task, model in payload["models"].items():
            if task in model_env_map:
                env_var = model_env_map[task]
                if model:  # Only set if not empty
                    os.environ[env_var] = model
                    updated.append(env_var)
                elif env_var in os.environ:
                    # Clear if empty string provided
                    del os.environ[env_var]
                    updated.append(f"{env_var} (cleared)")
    
    # Clear settings cache to reload with new values
    get_settings.cache_clear()
    
    log.info("Model configuration updated: %s", updated)
    return {"ok": True, "updated": updated}
