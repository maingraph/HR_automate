"""Job-level business logic (create, read, list candidates)."""
from __future__ import annotations

from typing import Any, Optional

from app.core.db import get_supabase
from app.core.logging import get_logger
from app.schemas.job import JobCreate
from app.scoring.gemini import generate_plan

log = get_logger(__name__)


async def create_job_with_plan(payload: JobCreate, org_id: str) -> dict[str, Any]:
    """Insert a job row and run Gemini to produce LI boolean + TG keywords + rubric."""
    sb = get_supabase()
    plan = generate_plan(payload.model_dump())

    row = {
        "org_id": org_id,
        "title": payload.title,
        "description": payload.description,
        "skills": payload.skills,
        "geo": payload.geo,
        "geo_exclude": payload.geo_exclude,
        "seniority": payload.seniority,
        "budget_min": payload.budget_min,
        "budget_max": payload.budget_max,
        "tg_channels": payload.tg_channels,
        "sources": payload.sources,
        "linkedin_boolean": plan.get("linkedin_boolean"),
        "tg_keywords": plan.get("tg_keywords", []),
        "rubric": plan.get("rubric", {}),
        "stats": {"linkedin_queries": plan.get("linkedin_queries", []), "hard_filters": plan.get("hard_filters", [])},
        "status": "draft",
    }
    r = sb.table("jobs").insert(row).execute()
    if not r.data:
        raise RuntimeError("Failed to insert job")
    return r.data[0]


async def get_job(job_id: str, org_id: str) -> Optional[dict[str, Any]]:
    sb = get_supabase()
    r = sb.table("jobs").select("*").eq("id", job_id).eq("org_id", org_id).single().execute()
    return r.data


async def list_candidates(
    job_id: str,
    org_id: str,
    min_score: int = 0,
    source: Optional[str] = None,
    open_to_work: Optional[bool] = None,
    skills: Optional[str] = None,
    location: Optional[str] = None,
    min_experience: Optional[int] = None,
    max_experience: Optional[int] = None,
    seniority: Optional[str] = None,
    sort_by: str = "score_desc",
    limit: int = 500,
) -> list[dict[str, Any]]:
    sb = get_supabase()
    q = sb.table("candidates").select("*").eq("job_id", job_id).eq("org_id", org_id)
    
    # Apply database-level filters
    if min_score:
        q = q.gte("gemini_score", min_score)
    if source:
        q = q.eq("source", source)
    if open_to_work is not None:
        q = q.eq("open_to_work", open_to_work)
    
    # Fetch all matching candidates (we'll filter and sort in Python)
    q = q.limit(2000)  # Max limit
    r = q.execute()
    candidates = r.data or []
    
    # Post-process filters (array/text matching)
    if skills:
        skill_list = [s.strip().lower() for s in skills.split(",") if s.strip()]
        candidates = [
            c for c in candidates
            if any(
                skill in [s.lower() for s in (c.get("skills") or [])]
                for skill in skill_list
            )
        ]
    
    if location:
        location_lower = location.lower()
        candidates = [
            c for c in candidates
            if location_lower in (c.get("location") or "").lower()
        ]
    
    if min_experience is not None or max_experience is not None:
        candidates = [
            c for c in candidates
            if (min_experience is None or (c.get("years_experience") or 0) >= min_experience)
            and (max_experience is None or (c.get("years_experience") or 0) <= max_experience)
        ]
    
    if seniority:
        seniority_list = [s.strip() for s in seniority.split(",") if s.strip()]
        candidates = [
            c for c in candidates
            if c.get("seniority") in seniority_list
        ]
    
    # Sort
    sort_map = {
        "score_desc": lambda c: -(c.get("gemini_score") or -1),
        "score_asc": lambda c: c.get("gemini_score") or 999,
        "name_asc": lambda c: (c.get("full_name") or "").lower(),
        "name_desc": lambda c: (c.get("full_name") or "").lower(),
        "date_asc": lambda c: c.get("created_at") or "",
        "date_desc": lambda c: c.get("created_at") or "",
        "location_asc": lambda c: (c.get("location") or "").lower(),
    }
    
    if sort_by in sort_map:
        reverse = sort_by.endswith("_desc")
        candidates.sort(key=sort_map[sort_by], reverse=reverse)
    
    return candidates[:limit]
