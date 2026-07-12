"""Job state management - pause, resume, cancel operations."""
from __future__ import annotations

from typing import Any
from datetime import datetime

from app.core.db import get_supabase, get_redis
from app.core.logging import get_logger

log = get_logger(__name__)


def pause_job(job_id: str, org_id: str) -> dict[str, Any]:
    """
    Pause a running job.

    Sets job status to 'paused' and stores current checkpoint.
    The Celery task will check for paused status and stop gracefully.

    Args:
        job_id: Job identifier
        org_id: Organization scope

    Returns:
        Updated job data
    """
    sb = get_supabase()
    redis = get_redis()

    # Get current job
    job = sb.table("jobs").select("*").eq("id", job_id).eq("org_id", org_id).single().execute().data

    if not job:
        raise ValueError(f"Job {job_id} not found")

    if job["status"] not in ("running", "queued", "running_deep"):
        raise ValueError(f"Cannot pause job in status: {job['status']}")

    # Set pause flag in Redis (checked by Celery task)
    redis.set(f"job:pause:{job_id}", "1", ex=3600)  # Expire in 1 hour

    # Update job status
    result = sb.table("jobs").update({
        "status": "paused",
        "paused_at": datetime.utcnow().isoformat(),
    }).eq("id", job_id).eq("org_id", org_id).execute()
    
    log.info(f"Job {job_id} paused")
    return result.data[0] if result.data else {}


def resume_job(job_id: str, org_id: str) -> dict[str, Any]:
    """
    Resume a paused job.

    Restarts the pipeline from the last checkpoint.

    Args:
        job_id: Job identifier
        org_id: Organization scope

    Returns:
        Updated job data
    """
    sb = get_supabase()
    redis = get_redis()

    # Get current job
    job = sb.table("jobs").select("*").eq("id", job_id).eq("org_id", org_id).single().execute().data

    if not job:
        raise ValueError(f"Job {job_id} not found")

    if job["status"] != "paused":
        raise ValueError(f"Cannot resume job in status: {job['status']}")

    # Clear pause flag
    redis.delete(f"job:pause:{job_id}")

    # Determine resume status based on checkpoint
    checkpoint = job.get("checkpoint") or {}
    last_stage = checkpoint.get("stage")

    # Resume to appropriate status
    if last_stage == "score":
        # Resume scoring - trigger score_now directly
        resume_status = "running_deep"
        result = sb.table("jobs").update({
            "status": resume_status,
            "paused_at": None,
        }).eq("id", job_id).eq("org_id", org_id).execute()

        from app.tasks.score_now import score_now
        score_now.delay(job_id)
        log.info(f"Job {job_id} resumed scoring from checkpoint")
    elif last_stage in ("scrape_telegram", "scrape_apollo", "normalize", "embed"):
        resume_status = "running"
        result = sb.table("jobs").update({
            "status": resume_status,
            "paused_at": None,
        }).eq("id", job_id).eq("org_id", org_id).execute()

        from app.tasks.pipeline import run_pipeline
        run_pipeline.delay(job_id)
        log.info(f"Job {job_id} resumed pipeline from checkpoint: {last_stage}")
    elif last_stage == "deep_scrape":
        resume_status = "running_deep"
        result = sb.table("jobs").update({
            "status": resume_status,
            "paused_at": None,
        }).eq("id", job_id).eq("org_id", org_id).execute()

        from app.tasks.deep_scan import run_deep_scan
        run_deep_scan.delay(job_id)
        log.info(f"Job {job_id} resumed deep scrape from checkpoint")
    else:
        # No checkpoint or unknown stage - start from beginning
        resume_status = "queued"
        result = sb.table("jobs").update({
            "status": resume_status,
            "paused_at": None,
        }).eq("id", job_id).eq("org_id", org_id).execute()

        from app.tasks.pipeline import run_pipeline
        run_pipeline.delay(job_id)
        log.info(f"Job {job_id} resumed from beginning (no valid checkpoint)")

    return result.data[0] if result.data else {}


def cancel_job(job_id: str, org_id: str, keep_results: bool = True) -> dict[str, Any]:
    """
    Cancel a running job.

    Stops the pipeline and optionally keeps partial results.

    Args:
        job_id: Job identifier
        org_id: Organization scope
        keep_results: If True, keep candidates found so far

    Returns:
        Updated job data
    """
    sb = get_supabase()
    redis = get_redis()

    # Get current job
    job = sb.table("jobs").select("*").eq("id", job_id).eq("org_id", org_id).single().execute().data

    if not job:
        raise ValueError(f"Job {job_id} not found")

    if job["status"] not in ("running", "queued", "running_deep", "paused"):
        raise ValueError(f"Cannot cancel job in status: {job['status']}")

    # Set cancel flag in Redis
    redis.set(f"job:cancel:{job_id}", "1", ex=3600)

    # Update job status
    new_status = "phase1_done" if keep_results else "error"
    result = sb.table("jobs").update({
        "status": new_status,
        "error": None if keep_results else "Cancelled by user",
    }).eq("id", job_id).eq("org_id", org_id).execute()
    
    log.info(f"Job {job_id} cancelled (keep_results={keep_results})")
    return result.data[0] if result.data else {}


def check_job_paused(job_id: str) -> bool:
    """
    Check if job is paused.
    
    Called by Celery tasks to check if they should stop.
    
    Args:
        job_id: Job identifier
        
    Returns:
        True if job is paused
    """
    redis = get_redis()
    return redis.exists(f"job:pause:{job_id}") > 0


def check_job_cancelled(job_id: str) -> bool:
    """
    Check if job is cancelled.
    
    Called by Celery tasks to check if they should stop.
    
    Args:
        job_id: Job identifier
        
    Returns:
        True if job is cancelled
    """
    redis = get_redis()
    return redis.exists(f"job:cancel:{job_id}") > 0


def save_checkpoint(job_id: str, stage: str, data: dict[str, Any]) -> None:
    """
    Save pipeline checkpoint for resume functionality.
    
    Args:
        job_id: Job identifier
        stage: Current pipeline stage
        data: Checkpoint data (candidates_count, etc.)
    """
    sb = get_supabase()
    
    checkpoint = {
        "stage": stage,
        "timestamp": datetime.utcnow().isoformat(),
        "can_resume": True,
        **data
    }
    
    sb.table("jobs").update({
        "checkpoint": checkpoint
    }).eq("id", job_id).execute()
    
    log.debug(f"Checkpoint saved for job {job_id}: {stage}")
