"""Job CRUD + pipeline control."""
from __future__ import annotations

import io
import tempfile
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.core.auth import CurrentUser, get_current_user
from app.core.db import get_supabase
from app.core.logging import get_logger
from app.schemas.candidate import CandidateOut
from app.schemas.job import JobCreate, JobOut, JobRunResponse
from app.services.jobs import create_job_with_plan, get_job, list_candidates

log = get_logger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobOut)
async def post_job(
    payload: JobCreate,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a job and synchronously generate LI boolean + TG keywords + rubric via Gemini."""
    try:
        return await create_job_with_plan(payload, current.org_id)
    except Exception as e:  # surface a readable error, don't 500 silently
        log.exception("create_job failed")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{job_id}", response_model=JobOut)
async def get_job_by_id(
    job_id: str,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    job = await get_job(job_id, current.org_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/run", response_model=JobRunResponse)
async def run_job(
    job_id: str,
    current: CurrentUser = Depends(get_current_user),
) -> JobRunResponse:
    from app.tasks.pipeline import run_pipeline  # local import to avoid circulars

    job = await get_job(job_id, current.org_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    sb = get_supabase()
    sb.table("jobs").update({"status": "queued", "error": None}).eq("id", job_id).eq("org_id", current.org_id).execute()

    task = run_pipeline.delay(job_id)
    return JobRunResponse(job_id=job_id, task_id=task.id, status="queued")


@router.get("/{job_id}/candidates", response_model=list[CandidateOut])
async def get_candidates(
    job_id: str,
    min_score: int = Query(0, ge=0, le=100),
    source: Optional[str] = Query(None),
    open_to_work: Optional[bool] = Query(None),
    skills: Optional[str] = Query(None),  # comma-separated
    location: Optional[str] = Query(None),  # fuzzy match
    min_experience: Optional[int] = Query(None),
    max_experience: Optional[int] = Query(None),
    seniority: Optional[str] = Query(None),  # comma-separated
    sort_by: str = Query("score_desc"),
    limit: int = Query(500, le=2000),
    current: CurrentUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return await list_candidates(
        job_id=job_id,
        org_id=current.org_id,
        min_score=min_score,
        source=source,
        open_to_work=open_to_work,
        skills=skills,
        location=location,
        min_experience=min_experience,
        max_experience=max_experience,
        seniority=seniority,
        sort_by=sort_by,
        limit=limit,
    )


@router.post("/{job_id}/ingest-file", response_model=JobRunResponse)
async def ingest_file(
    job_id: str,
    file: UploadFile = File(...),
    current: CurrentUser = Depends(get_current_user),
) -> JobRunResponse:
    """Upload an XLSX/CSV of candidates, ingest them into the scoring pipeline for this job."""
    from app.tasks.pipeline import run_pipeline  # local import

    job = await get_job(job_id, current.org_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Validate file type
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in (".xlsx", ".xls", ".csv"):
        raise HTTPException(status_code=400, detail="Only .xlsx, .xls, .csv files are accepted")

    # Save to a temp file that persists until the task finishes
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        content = await file.read()
        tmp.write(content)
        tmp.flush()
    finally:
        tmp.close()

    sb = get_supabase()
    sb.table("jobs").update({"status": "queued", "error": None}).eq("id", job_id).eq("org_id", current.org_id).execute()

    task = run_pipeline.delay(job_id, upload_paths=[tmp.name])
    log.info("ingest_file: job=%s file=%s task=%s", job_id, filename, task.id)
    return JobRunResponse(job_id=job_id, task_id=task.id, status="queued")


@router.post("/{job_id}/deep-scan", response_model=JobRunResponse)
async def deep_scan_job(
    job_id: str,
    current: CurrentUser = Depends(get_current_user),
) -> JobRunResponse:
    """Trigger Phase 2: deep-scrape LinkedIn profiles, geo-filter history, score."""
    from app.tasks.deep_scan import run_deep_scan  # local import

    job = await get_job(job_id, current.org_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    sb = get_supabase()
    sb.table("jobs").update({"status": "running_deep", "error": None}).eq("id", job_id).eq("org_id", current.org_id).execute()

    task = run_deep_scan.delay(job_id)
    log.info("deep_scan triggered: job=%s task=%s", job_id, task.id)
    return JobRunResponse(job_id=job_id, task_id=task.id, status="running_deep")


@router.post("/{job_id}/score-now", response_model=JobRunResponse)
async def score_now_job(
    job_id: str,
    current: CurrentUser = Depends(get_current_user),
) -> JobRunResponse:
    """Score Phase 1 candidates directly using existing profile data — no Apify deep scraping.
    Use when: SalesNav export already has rich bio/title data, or Apify deep scraping fails."""
    from app.tasks.score_now import score_now  # local import

    job = await get_job(job_id, current.org_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    sb = get_supabase()
    sb.table("jobs").update({"status": "running_deep", "error": None}).eq("id", job_id).eq("org_id", current.org_id).execute()

    task = score_now.delay(job_id)
    log.info("score_now triggered: job=%s task=%s", job_id, task.id)
    return JobRunResponse(job_id=job_id, task_id=task.id, status="running_deep")


@router.post("/{job_id}/discover-channels")
async def discover_telegram_channels(
    job_id: str,
    validate: bool = Query(True),
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Discover relevant Telegram channels for a job using AI.
    
    Args:
        job_id: Job ID
        validate: Whether to validate channels exist (adds 5-10 seconds)
        
    Returns:
        {"channels": [{"handle": "@channel", "reason": "...", "confidence": "high"}, ...]}
    """
    from app.scrapers.telegram import discover_channels

    job = await get_job(job_id, current.org_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        channels = discover_channels(job, validate=validate)
        log.info(f"Discovered {len(channels)} channels for job {job_id}")
        return {"channels": channels}
    except Exception as e:
        log.exception("Channel discovery failed")
        raise HTTPException(status_code=500, detail=f"Channel discovery failed: {str(e)}")


@router.post("/discover-channels-preview")
async def discover_channels_preview(
    payload: dict[str, Any],
    validate: bool = Query(True),
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Discover relevant Telegram channels for a job (preview mode - no job_id required).
    
    Used during job creation before the job is saved.
    
    Args:
        payload: Job data (title, description, skills, geo, seniority)
        validate: Whether to validate channels exist (adds 5-10 seconds)
        
    Returns:
        {"channels": [{"handle": "@channel", "reason": "...", "confidence": "high"}, ...]}
    """
    from app.scrapers.telegram import discover_channels
    
    try:
        channels = discover_channels(payload, validate=validate)
        log.info(f"Discovered {len(channels)} channels (preview mode)")
        return {"channels": channels}
    except Exception as e:
        log.exception("Channel discovery failed")
        raise HTTPException(status_code=500, detail=f"Channel discovery failed: {str(e)}")


@router.post("/{job_id}/reset", response_model=JobOut)
async def reset_job(
    job_id: str,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Reset a stuck job back to phase1_done so deep scan can be re-triggered.
    Safe to call any time — only resets status, never deletes candidates."""
    job = await get_job(job_id, current.org_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    sb = get_supabase()
    sb.table("jobs").update({"status": "phase1_done", "error": None}).eq("id", job_id).eq("org_id", current.org_id).execute()
    return await get_job(job_id, current.org_id)


@router.post("/{job_id}/pause", response_model=JobOut)
async def pause_job_endpoint(
    job_id: str,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Pause a running job. Can be resumed later from checkpoint."""
    from app.services.job_control import pause_job

    try:
        result = pause_job(job_id, current.org_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{job_id}/resume", response_model=JobOut)
async def resume_job_endpoint(
    job_id: str,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Resume a paused job from last checkpoint."""
    from app.services.job_control import resume_job

    try:
        result = resume_job(job_id, current.org_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{job_id}/cancel")
async def cancel_job_endpoint(
    job_id: str,
    keep_results: bool = True,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Cancel a running job. Optionally keep partial results."""
    from app.services.job_control import cancel_job

    try:
        result = cancel_job(job_id, current.org_id, keep_results=keep_results)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{job_id}/export")
async def export_candidates(
    job_id: str,
    current: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    """Download all candidates as a two-sheet XLSX.

    Sheet 1 — Scored Results: final shortlist sorted by score
    Sheet 2 — Full Profiles Debug: every candidate with raw educations/positions
    """
    import pandas as pd  # lazy import — only needed for export

    job = await get_job(job_id, current.org_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    sb = get_supabase()
    rows = (
        sb.table("candidates")
        .select("*")
        .eq("job_id", job_id)
        .eq("org_id", current.org_id)
        .order("gemini_score", desc=True)
        .limit(2000)
        .execute()
        .data or []
    )

    def fmt_edu(edulist: list) -> str:
        parts = []
        for e in edulist or []:
            parts.append(f"{e.get('school','')} — {e.get('field','')} {e.get('location','')} ({e.get('start','')}–{e.get('end','')})".strip())
        return "\n".join(p for p in parts if p)

    def fmt_pos(poslist: list) -> str:
        parts = []
        for p in poslist or []:
            parts.append(f"{p.get('title','')} @ {p.get('company','')} | {p.get('location','')} | {p.get('start','')}–{p.get('end','')}".strip())
        return "\n".join(p for p in parts if p)

    # Sheet 1: scored results
    scored = [r for r in rows if r.get("gemini_score") is not None and r.get("status") != "rejected"]
    df_scored = pd.DataFrame([
        {
            "score":       r.get("gemini_score"),
            "name":        r.get("full_name") or r.get("username"),
            "headline":    r.get("headline"),
            "location":    r.get("location"),
            "open_to_work": r.get("open_to_work"),
            "linkedin":    r.get("linkedin_url"),
            "telegram":    r.get("telegram_url"),
            "email":       r.get("email"),
            "source":      r.get("source"),
            "scan_depth":  r.get("scan_depth"),
            "reasoning":   r.get("gemini_reasoning"),
            "red_flags":   "; ".join(r.get("red_flags") or []),
            "skills":      ", ".join(r.get("skills") or []),
        }
        for r in scored
    ])

    # Sheet 2: all profiles debug (full raw data)
    df_debug = pd.DataFrame([
        {
            "score":         r.get("gemini_score"),
            "status":        r.get("status"),
            "scan_depth":    r.get("scan_depth"),
            "name":          r.get("full_name") or r.get("username"),
            "headline":      r.get("headline"),
            "location":      r.get("location"),
            "linkedin":      r.get("linkedin_url"),
            "telegram":      r.get("telegram_url"),
            "email":         r.get("email"),
            "phone":         r.get("phone"),
            "source":        r.get("source"),
            "skills":        ", ".join(r.get("skills") or []),
            "languages":     ", ".join(r.get("languages") or []),
            "years_exp":     r.get("years_experience"),
            "open_to_work":  r.get("open_to_work"),
            "education":     fmt_edu(r.get("educations") or []),
            "positions":     fmt_pos(r.get("positions") or []),
            "bio":           (r.get("bio") or "")[:1000],
            "reasoning":     r.get("gemini_reasoning"),
            "red_flags":     "; ".join(r.get("red_flags") or []),
            "similarity":    r.get("embed_similarity"),
        }
        for r in rows
    ])

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_scored.to_excel(writer, sheet_name="Scored Results", index=False)
        df_debug.to_excel(writer, sheet_name="Full Profiles Debug", index=False)
    buf.seek(0)

    job_title = (job.get("title") or "candidates").replace(" ", "_")[:40]
    filename = f"{job_title}_candidates.xlsx"

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{job_id}/logs")
async def get_job_logs(
    job_id: str,
    current: CurrentUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Return all pipeline_runs for a job, sorted chronologically.
    Frontend polls this every 2s to show live stage progress."""
    sb = get_supabase()
    r = (sb.table("pipeline_runs")
         .select("*")
         .eq("job_id", job_id)
         .eq("org_id", current.org_id)
         .order("started_at")
         .limit(200)
         .execute())
    return r.data or []


@router.get("", response_model=list[JobOut])
async def list_jobs(
    current: CurrentUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    sb = get_supabase()
    r = (sb.table("jobs")
         .select("*")
         .eq("org_id", current.org_id)
         .order("created_at", desc=True)
         .limit(100)
         .execute())
    return r.data or []


@router.post("/structure-vacancy")
async def structure_vacancy(
    payload: dict,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Extract structured job data from raw vacancy text using AI.
    
    Request:
        {
            "raw_text": "Looking for Sr. React dev, 5+ yrs exp, $150k-200k, SF Bay Area"
        }
    
    Response:
        {
            "title": "Senior React Developer",
            "description": "5+ years of experience required",
            "skills": ["React"],
            "seniority": "Senior",
            "geo": "San Francisco Bay Area, USA",
            "budget_min": 150000,
            "budget_max": 200000
        }
    """
    from app.scoring.gemini import structure_vacancy as structure_vacancy_ai
    
    raw_text = payload.get("raw_text", "").strip()
    
    if not raw_text:
        raise HTTPException(status_code=400, detail="raw_text is required")
    
    if len(raw_text) > 10000:
        raise HTTPException(status_code=400, detail="raw_text too long (max 10000 characters)")
    
    try:
        result = structure_vacancy_ai(raw_text)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.exception("Failed to structure vacancy")
        raise HTTPException(status_code=500, detail=f"Failed to structure vacancy: {str(e)}")


@router.get("/{job_id}/progress")
async def get_job_progress(
    job_id: str,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Get current progress for all pipeline stages.
    
    Returns persisted progress from Redis for each stage.
    
    Response:
        {
            "progress": {
                "scrape_telegram": {
                    "current": 252,
                    "total": 252,
                    "percentage": 100.0,
                    "message": "Found 252 candidates",
                    "timestamp": 1234567890.123
                },
                "normalize": {...},
                "embed": {...},
                "deep_scan": {...},
                "score": {...}
            }
        }
    """
    from app.core.db import get_redis
    import json

    # Ownership guard: ensure this job belongs to the caller's org
    job = await get_job(job_id, current.org_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    redis = get_redis()
    stages = ["scrape_telegram", "scrape_apollo", "ingest_file", "normalize",
              "embed", "deep_scan", "score"]
    
    progress = {}
    for stage in stages:
        key = f"progress:{job_id}:{stage}"
        data = redis.get(key)
        if data:
            try:
                progress[stage] = json.loads(data)
            except:
                pass
    
    return {"progress": progress}
