"""Celery pipeline that runs scraping → dedup → two-stage scoring → persist."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.celery_app import celery_app
from app.core.db import get_supabase
from app.core.error_handling import with_fallback, log_errors
from app.core.logging import get_logger
from app.core.monitoring import track_performance, log_performance_summary
from app.scoring.pipeline import stage1_embed_filter, stage2_gemini_score
from app.scrapers.apollo import scrape_apollo
from app.scrapers.file_ingest import parse_file
from app.scrapers.telegram import scrape_channels
from app.services.dedup import dedup
from app.utils.geo_filter import is_geo_excluded

log = get_logger(__name__)

# Cache job_id → org_id so we stamp org_id on inserts without re-querying per call.
# Celery workers are long-lived; this stays warm across a task run.
_ORG_CACHE: dict[str, str] = {}


def _org_for_job(job_id: str) -> str | None:
    """Resolve the org_id that owns a job (cached). Used to stamp org_id on inserts."""
    if job_id in _ORG_CACHE:
        return _ORG_CACHE[job_id]
    try:
        sb = get_supabase()
        r = sb.table("jobs").select("org_id").eq("id", job_id).single().execute()
        org = (r.data or {}).get("org_id")
        if org:
            _ORG_CACHE[job_id] = org
        return org
    except Exception:
        return None


def _notify_websocket(job_id: str, update: dict):
    """Send WebSocket notification via Redis pub/sub (non-blocking)."""
    try:
        from app.core.db import get_redis
        import json
        
        redis = get_redis()
        channel = f"ws:job:{job_id}"
        message = json.dumps(update)
        redis.publish(channel, message)
    except Exception as e:
        log.warning(f"Failed to publish WebSocket notification: {e}")


def emit_progress(job_id: str, stage: str, current: int, total: int, message: str = ""):
    """Emit progress update via Redis pub/sub and store for persistence.
    
    Args:
        job_id: Job identifier
        stage: Pipeline stage name (e.g., 'scrape_telegram', 'embed')
        current: Current progress count
        total: Total items to process
        message: Optional progress message
    """
    try:
        from app.core.db import get_redis
        import json
        import time
        
        redis = get_redis()
        
        percentage = round((current / total * 100), 1) if total > 0 else 0
        
        progress_data = {
            "type": "progress_update",
            "stage": stage,
            "current": current,
            "total": total,
            "percentage": percentage,
            "message": message,
            "timestamp": time.time()
        }
        
        # Publish to WebSocket subscribers
        channel = f"ws:job:{job_id}"
        redis.publish(channel, json.dumps(progress_data))
        
        # Store for persistence (TTL 24 hours)
        redis.setex(
            f"progress:{job_id}:{stage}",
            86400,  # 24 hours
            json.dumps(progress_data)
        )
        
        log.debug(f"Progress emitted for job {job_id}, stage {stage}: {current}/{total} ({percentage}%)")
    except Exception as e:
        log.warning(f"Failed to emit progress: {e}")


@log_errors(log_message="pipeline_runs insert failed", reraise=False)
def _log_run(job_id: str, stage: str, status: str, count: int = 0, message: str = "") -> None:
    """Log pipeline run stage to database.
    
    Args:
        job_id: Job identifier
        stage: Pipeline stage name (e.g., 'scrape_telegram', 'embed')
        status: Stage status ('started', 'ok', 'error')
        count: Number of items processed
        message: Optional error message or details
    """
    sb = get_supabase()
    sb.table("pipeline_runs").insert(
        {
            "org_id": _org_for_job(job_id),
            "job_id": job_id,
            "stage": stage,
            "status": status,
            "count": count,
            "message": message[:500] if message else None,
            "ended_at": datetime.utcnow().isoformat() if status in ("ok", "error") else None,
        }
    ).execute()
    
    # Notify WebSocket clients about pipeline progress
    _notify_websocket(job_id, {
        "stage": stage,
        "status": status,
        "count": count,
        "message": message[:500] if message else None,
    })


def _update_job_status(job_id: str, **fields: Any) -> None:
    sb = get_supabase()
    sb.table("jobs").update(fields).eq("id", job_id).execute()
    
    # Notify WebSocket clients about job status change
    if "status" in fields:
        _notify_websocket(job_id, {
            "job_status": fields["status"],
            "updated_fields": list(fields.keys()),
        })


def _persist_candidates(
    job_id: str,
    candidates: list[dict[str, Any]],
    scan_depth: int = 1,
) -> int:
    if not candidates:
        return 0
    sb = get_supabase()
    org_id = _org_for_job(job_id)
    rows = []
    for c in candidates:
        scored = c.get("gemini_score") is not None
        row = {
            "org_id": org_id,
            "job_id": job_id,
            "source": c.get("source"),
            "source_id": c.get("source_id"),
            "full_name": c.get("full_name"),
            "first_name": c.get("first_name"),
            "last_name": c.get("last_name"),
            "username": c.get("username"),
            "headline": c.get("headline"),
            "bio": c.get("bio"),
            "raw_text": c.get("raw_text"),
            "location": c.get("location"),
            "seniority": c.get("seniority"),
            "years_experience": c.get("years_experience"),
            "skills": c.get("skills") or [],
            "languages": c.get("languages") or [],
            "linkedin_url": c.get("linkedin_url"),
            "telegram_url": c.get("telegram_url"),
            "email": c.get("email"),
            "phone": c.get("phone"),
            "other_links": c.get("other_links") or [],
            "embedding": c.get("embedding"),
            "embed_similarity": c.get("embed_similarity"),
            "gemini_score": c.get("gemini_score"),
            "gemini_reasoning": c.get("gemini_reasoning"),
            "gemini_dimensions": c.get("gemini_dimensions") or {},
            "red_flags": c.get("red_flags") or [],
            "open_to_work": bool(c.get("open_to_work")),
            "otw_signal": c.get("otw_signal"),
            "raw": {k: v for k, v in (c.get("raw") or {}).items() if _json_safe(v)},
            "dedup_key": c.get("dedup_key"),
            "scan_depth": c.get("scan_depth") or scan_depth,
            "educations": c.get("educations") or [],
            "positions": c.get("positions") or [],
            "status": "scored" if scored else "new",
        }
        rows.append(row)

    # chunked insert
    inserted = 0
    for i in range(0, len(rows), 250):
        chunk = rows[i : i + 250]
        r = sb.table("candidates").insert(chunk).execute()
        inserted += len(r.data or [])
    return inserted


def _json_safe(v: Any) -> bool:
    """Check if value is JSON-serializable.
    
    Args:
        v: Value to check
        
    Returns:
        True if value can be serialized to JSON, False otherwise
    """
    try:
        import json
        json.dumps(v)
        return True
    except Exception:
        return False


# === Helper functions with unified error handling ===

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    reraise=True
)
@with_fallback(fallback_value=[], log_message="Telegram scrape failed")
def _scrape_telegram_safe(job_id: str, channels: list[str], keywords: list[str]) -> list[dict[str, Any]]:
    """Scrape Telegram channels with graceful error handling and retries.
    
    Retries up to 3 times with exponential backoff on connection errors.
    
    Args:
        job_id: Job identifier for logging
        channels: List of Telegram channel URLs
        keywords: Keywords to filter messages
        
    Returns:
        List of candidate dictionaries, empty list on failure
    """
    with track_performance("scrape_telegram"):
        result = scrape_channels(
            channels=channels,
            keywords=keywords,
            days_back=90,
            per_channel_limit=1000,
        )
    return result


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    reraise=True
)
@with_fallback(fallback_value=[], log_message="Apollo scrape failed")
def _scrape_apollo_safe(
    job_id: str, 
    keywords: str, 
    title: str | None, 
    geo: str | None
) -> list[dict[str, Any]]:
    """Scrape Apollo.io with graceful error handling and retries.
    
    Retries up to 3 times with exponential backoff on connection errors.
    
    Args:
        job_id: Job identifier for logging
        keywords: Search keywords
        title: Job title filter
        geo: Geographic location filter
        
    Returns:
        List of candidate dictionaries, empty list on failure
    """
    with track_performance("scrape_apollo"):
        result = scrape_apollo(
            keywords=keywords,
            titles=[title] if title else None,
            geo=geo,
            max_results=50,
        )
    return result


def _salesnav_to_candidate(p: dict[str, Any]) -> dict[str, Any]:
    """Map a Sales Nav profile dict to the pipeline's candidate shape.

    Sales Nav already returns full profiles (experience/education/skills), so we
    build a rich raw_text for the Stage-1 embedding filter and stamp scan_depth=2
    (full data captured — Phase-2 deep scan is optional for these).
    """
    exp = p.get("experience") or []
    edu = p.get("education") or []
    text_parts = [
        p.get("full_name", ""),
        p.get("headline", ""),
        p.get("current_company", ""),
        p.get("location", ""),
        p.get("about", ""),
    ]
    for e in exp:
        text_parts.append(
            f"{e.get('title', '')} {e.get('company', '')} {e.get('duration', '')}".strip()
        )
    text_parts.extend(p.get("skills") or [])
    raw_text = "\n".join(t for t in text_parts if t)

    url = p.get("profile_url") or ""
    return {
        "source": "linkedin_salesnav",
        "source_id": url or None,
        "full_name": p.get("full_name"),
        "headline": p.get("headline"),
        "bio": p.get("about"),
        "raw_text": raw_text,
        "location": p.get("location"),
        "skills": p.get("skills") or [],
        "languages": p.get("languages") or [],
        "linkedin_url": url or None,
        "positions": exp,
        "educations": edu,
        "raw": {"current_company": p.get("current_company") or ""},
        "scan_depth": 2,
    }


@with_fallback(fallback_value=[], log_message="Sales Nav scrape failed")
def _scrape_salesnav_safe(job_id: str, job: dict[str, Any]) -> list[dict[str, Any]]:
    """Scrape LinkedIn Sales Navigator via Playwright. Empty list on any failure.

    Returns [] (caller falls back to Apify) when the li_at cookie is unset, the
    cookie is expired/blocked, or scraping otherwise yields nothing.
    """
    from app.core.config import settings
    from app.scrapers.linkedin_salesnav import SalesNavScraper
    from app.scrapers.salesnav_url_builder import build_sales_nav_url

    cookie = settings.linkedin_li_at
    if not cookie:
        log.warning("Sales Nav requested but LINKEDIN_LI_AT not set — skipping to Apify")
        return []

    url = build_sales_nav_url(
        title=job.get("title"),
        location=job.get("geo"),
        seniority=job.get("seniority"),
        skills=(job.get("skills") or [])[:3],
    )
    scraper = SalesNavScraper(
        li_at_cookie=cookie,
        headless=settings.li_headless,
        max_profiles=200,
        max_pages=10,
    )
    with track_performance("scrape_salesnav"):
        profiles = asyncio.run(scraper.scrape(url))
    return [_salesnav_to_candidate(p) for p in profiles]


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    reraise=True,
)
@with_fallback(fallback_value=[], log_message="LinkedIn Apify scrape failed")
def _scrape_linkedin_apify_safe(job_id: str, job: dict[str, Any]) -> list[dict[str, Any]]:
    """Scrape LinkedIn via Apify Boolean search. Empty list on failure.

    Uses the 3 Gemini-generated queries (job.stats.linkedin_queries) when present,
    falling back to the legacy single linkedin_boolean field.
    """
    from app.scrapers.linkedin_apify import scrape_linkedin

    queries = ((job.get("stats") or {}).get("linkedin_queries")) or []
    boolean = job.get("linkedin_boolean") or ""
    if not queries and not boolean:
        log.warning("LinkedIn requested but no Boolean queries on job — skipping")
        return []
    with track_performance("scrape_linkedin_apify"):
        return scrape_linkedin(
            boolean,
            queries=queries or None,
            geo=job.get("geo"),
            max_results=100,
        )


@with_fallback(fallback_value=[], log_message="File ingest failed")
def _ingest_files_safe(job_id: str, upload_paths: list[str]) -> list[dict[str, Any]]:
    """Ingest uploaded files with graceful error handling.
    
    Args:
        job_id: Job identifier for logging
        upload_paths: List of file paths to ingest
        
    Returns:
        List of candidate dictionaries, empty list on failure
    """
    with track_performance("ingest_files"):
        files_rows: list[dict[str, Any]] = []
        for p in upload_paths:
            files_rows.extend(parse_file(p))
    return files_rows


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    reraise=True
)
@with_fallback(fallback_value=0, log_message="Persist candidates failed")
def _persist_candidates_safe(job_id: str, candidates: list[dict[str, Any]]) -> int:
    """Persist candidates to database with graceful error handling and retries.
    
    Retries up to 3 times with exponential backoff on database errors.
    
    Args:
        job_id: Job identifier
        candidates: List of candidates to persist
        
    Returns:
        Number of candidates inserted, 0 on failure
    """
    with track_performance("persist_candidates"):
        return _persist_candidates(job_id, candidates, scan_depth=1)


@with_fallback(fallback_value=None, log_message="Stage 1 embed filter failed")
def _stage1_filter_safe(
    job_id: str, 
    job: dict[str, Any], 
    candidates: list[dict[str, Any]], 
    file_only: bool
) -> list[dict[str, Any]]:
    """Run stage 1 embedding filter with graceful error handling.
    
    Falls back to returning all candidates if embedding fails.
    
    Args:
        job_id: Job identifier for logging
        job: Job dictionary with description and requirements
        candidates: List of candidates to filter
        file_only: If True, skip filtering (user-curated list)
        
    Returns:
        Filtered candidates, or all candidates on failure
    """
    with track_performance("stage1_embed_filter"):
        result = stage1_embed_filter(job, candidates, drop_bottom_pct=0.0 if file_only else 0.3)
    return result if result is not None else candidates


@celery_app.task(name="sourcer.run_pipeline", bind=True)
def run_pipeline(self, job_id: str, upload_paths: list[str] | None = None) -> dict[str, Any]:
    sb = get_supabase()
    job = sb.table("jobs").select("*").eq("id", job_id).single().execute().data
    if not job:
        raise RuntimeError(f"job {job_id} not found")

    _update_job_status(job_id, status="running", error=None)
    stats: dict[str, Any] = {}

    # Determine which sources are enabled for this job
    enabled_sources: list[str] = job.get("sources") or ["linkedin", "telegram"]

    all_candidates: list[dict[str, Any]] = []

    # === scrape Telegram ===
    if "telegram" in enabled_sources:
        _log_run(job_id, "scrape_telegram", "started")
        emit_progress(job_id, "scrape_telegram", 0, 1, "Starting Telegram scrape...")
        tg = _scrape_telegram_safe(job_id, job.get("tg_channels") or [], job.get("tg_keywords") or [])
        all_candidates.extend(tg)
        stats["telegram_count"] = len(tg)
        if tg:
            _log_run(job_id, "scrape_telegram", "ok", count=len(tg))
            emit_progress(job_id, "scrape_telegram", len(tg), len(tg), f"Found {len(tg)} candidates")

    # === scrape LinkedIn (Sales Nav optional, Apify default + fallback) ===
    use_salesnav = "linkedin_salesnav" in enabled_sources
    use_apify = "linkedin" in enabled_sources
    if use_salesnav or use_apify:
        li_candidates: list[dict[str, Any]] = []

        if use_salesnav:
            _log_run(job_id, "scrape_linkedin_salesnav", "started")
            emit_progress(job_id, "scrape_linkedin_salesnav", 0, 1, "Scraping LinkedIn Sales Navigator...")
            li_candidates = _scrape_salesnav_safe(job_id, job)
            if li_candidates:
                _log_run(job_id, "scrape_linkedin_salesnav", "ok", count=len(li_candidates))
                emit_progress(job_id, "scrape_linkedin_salesnav", len(li_candidates), len(li_candidates), f"Found {len(li_candidates)} profiles")
            else:
                # Sales Nav yielded nothing (cookie expired/blocked) — fall back to Apify
                _log_run(job_id, "scrape_linkedin_salesnav", "error", message="0 profiles — falling back to Apify")
                use_apify = True

        if use_apify and not li_candidates:
            _log_run(job_id, "scrape_linkedin", "started")
            emit_progress(job_id, "scrape_linkedin", 0, 1, "Scraping LinkedIn via Apify...")
            li_candidates = _scrape_linkedin_apify_safe(job_id, job)
            if li_candidates:
                _log_run(job_id, "scrape_linkedin", "ok", count=len(li_candidates))
                emit_progress(job_id, "scrape_linkedin", len(li_candidates), len(li_candidates), f"Found {len(li_candidates)} candidates")

        all_candidates.extend(li_candidates)
        stats["linkedin_count"] = len(li_candidates)

    # === scrape Apollo ===
    if "apollo" in enabled_sources:
        _log_run(job_id, "scrape_apollo", "started")
        emit_progress(job_id, "scrape_apollo", 0, 1, "Starting Apollo scrape...")
        apollo_keywords = " ".join(
            [job.get("title") or ""] + (job.get("skills") or [])[:5]
        )
        apollo_rows = _scrape_apollo_safe(job_id, apollo_keywords, job.get("title"), job.get("geo"))
        all_candidates.extend(apollo_rows)
        stats["apollo_count"] = len(apollo_rows)
        if apollo_rows:
            _log_run(job_id, "scrape_apollo", "ok", count=len(apollo_rows))
            emit_progress(job_id, "scrape_apollo", len(apollo_rows), len(apollo_rows), f"Found {len(apollo_rows)} candidates")

    # === file ingest ===
    if upload_paths:
        _log_run(job_id, "ingest_file", "started")
        emit_progress(job_id, "ingest_file", 0, 1, "Processing file...")
        files_rows = _ingest_files_safe(job_id, upload_paths)
        all_candidates.extend(files_rows)
        stats["file_count"] = len(files_rows)
        if files_rows:
            _log_run(job_id, "ingest_file", "ok", count=len(files_rows))
            emit_progress(job_id, "ingest_file", len(files_rows), len(files_rows), f"Loaded {len(files_rows)} candidates")

    # === dedup ===
    _log_run(job_id, "normalize", "started")
    total_before_dedup = len(all_candidates)
    emit_progress(job_id, "normalize", 0, total_before_dedup, "Deduplicating...")
    deduped = dedup(all_candidates)
    stats["deduped_count"] = len(deduped)
    _log_run(job_id, "normalize", "ok", count=len(deduped))
    emit_progress(job_id, "normalize", len(deduped), total_before_dedup, f"Deduplicated to {len(deduped)} candidates")

    # === geo exclusion hard filter ===
    geo_exclude = job.get("geo_exclude") or []
    if geo_exclude:
        geo_ok, geo_rejected = [], []
        for c in deduped:
            hit, reason = is_geo_excluded(c, geo_exclude)
            if hit:
                c["red_flags"] = (c.get("red_flags") or []) + [reason]
                c["status"] = "rejected"
                geo_rejected.append(c)
            else:
                geo_ok.append(c)
        stats["geo_excluded"] = len(geo_rejected)
        log.info("geo_excluded: %d / %d candidates", len(geo_rejected), len(deduped))
        deduped = geo_ok

    if not deduped:
        _update_job_status(job_id, status="done", stats=stats)
        return {"ok": True, "stats": stats}

    # === stage 1: TF-IDF similarity pre-filter (drop obvious non-matches) ===
    # For file-only imports the user already curated the list — skip TF-IDF entirely.
    file_only = bool(upload_paths) and all(
        stats.get(k, 0) == 0 for k in ("linkedin_count", "telegram_count", "apollo_count")
    )
    _log_run(job_id, "embed", "started")
    emit_progress(job_id, "embed", 0, len(deduped), "Filtering candidates...")
    survivors = _stage1_filter_safe(job_id, job, deduped, file_only)
    stats["stage1_kept"] = len(survivors)
    if survivors:
        _log_run(job_id, "embed", "ok", count=len(survivors))
        emit_progress(job_id, "embed", len(survivors), len(deduped), f"Kept {len(survivors)} candidates")

    # === persist Phase 1 candidates (unscored — Phase 2 deep scan will score) ===
    _log_run(job_id, "persist_phase1", "started")
    inserted = _persist_candidates_safe(job_id, survivors)
    stats["phase1_inserted"] = inserted
    # Count ANY candidate with a real linkedin URL — regardless of source
    stats["linkedin_with_url"] = sum(
        1 for c in survivors if c.get("linkedin_url")
    )
    if inserted > 0:
        _log_run(job_id, "persist_phase1", "ok", count=inserted)
    else:
        _log_run(job_id, "persist_phase1", "error", message="Failed to persist candidates")
        _update_job_status(job_id, status="error", error="Failed to persist candidates", stats=stats)
        return {"ok": False, "error": "Failed to persist candidates", "stats": stats}

    # phase1_done signals the frontend to show the "Run Deep Scan" button
    _update_job_status(job_id, status="phase1_done", stats=stats)
    
    # Log performance summary
    log_performance_summary()
    
    return {"ok": True, "phase": 1, "stats": stats}
