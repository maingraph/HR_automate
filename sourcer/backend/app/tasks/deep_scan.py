"""Phase 2: deep profile scan + geo filter on full history + LLM scoring.

Flow:
  1. Load all Phase 1 candidates (scan_depth=1) with a linkedin_url for this job
  2. Batch-scrape their full profiles via Apify (educations[], positions[], full bio)
  3. Merge deep data back into each candidate dict
  4. Run is_geo_excluded_deep() — checks ALL historical edu/position locations
  5. Run TF-IDF similarity filter on the enriched bios
  6. Score survivors with OpenRouter LLM using the richer profile data
  7. UPDATE each candidate row in DB (upsert via linkedin_url match)
  8. Also score Telegram candidates that have no LinkedIn URL (Phase 1 scores only)
  9. Mark job status = 'done'
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.core.celery_app import celery_app
from app.core.db import get_supabase
from app.core.logging import get_logger
from app.core.monitoring import track_performance, log_performance_summary
import math
import time as _time

from app.scrapers.linkedin_deep import scrape_one_batch
from app.scoring.pipeline import stage1_embed_filter, stage2_gemini_score
from app.utils.geo_filter import is_geo_excluded_deep, is_geo_excluded

log = get_logger(__name__)


def _log_run(job_id: str, stage: str, status: str, count: int = 0, msg: str = "") -> None:
    try:
        from app.tasks.pipeline import _org_for_job
        sb = get_supabase()
        sb.table("pipeline_runs").insert({
            "org_id": _org_for_job(job_id),
            "job_id": job_id, "stage": stage, "status": status, "count": count,
            "message": msg[:500] if msg else None,
            "ended_at": datetime.utcnow().isoformat() if status in ("ok", "error") else None,
        }).execute()
    except Exception:
        log.exception("pipeline_runs insert failed")


def _update_job(job_id: str, **fields: Any) -> None:
    get_supabase().table("jobs").update(fields).eq("id", job_id).execute()


def _json_safe(v: Any) -> bool:
    try:
        json.dumps(v)
        return True
    except Exception:
        return False


def _upsert_candidate(candidate_id: str, updates: dict[str, Any]) -> None:
    """Update an existing candidate row with Phase 2 enriched data."""
    sb = get_supabase()
    # Strip non-serialisable fields
    safe = {k: v for k, v in updates.items()
            if k not in ("embedding",) and _json_safe(v)}
    sb.table("candidates").update(safe).eq("id", candidate_id).execute()


def _insert_rejected(job_id: str, candidate: dict[str, Any], reason: str) -> None:
    """Persist a geo-rejected candidate for the debug export."""
    sb = get_supabase()
    try:
        sb.table("candidates").update({
            "red_flags": list({*(candidate.get("red_flags") or []), reason}),
            "status": "rejected",
            "scan_depth": 2,
            "gemini_score": 0,
            "gemini_reasoning": reason,
        }).eq("id", candidate["id"]).execute()
    except Exception:
        log.exception("_insert_rejected failed for %s", candidate.get("id"))


@celery_app.task(
    name="sourcer.run_deep_scan",
    bind=True,
    time_limit=60 * 120,      # 2 h hard limit (4 batches × ~15 min + scoring)
    soft_time_limit=60 * 110, # warn at 1h50m
)
def run_deep_scan(self, job_id: str) -> dict[str, Any]:
    """Phase 2 Celery task: deep-scrape LinkedIn profiles, geo-filter history, score."""
    sb = get_supabase()
    job = sb.table("jobs").select("*").eq("id", job_id).single().execute().data
    if not job:
        raise RuntimeError(f"job {job_id} not found")

    _update_job(job_id, status="running_deep", error=None)
    stats: dict[str, Any] = dict(job.get("stats") or {})  # preserve Phase 1 stats
    geo_exclude: list[str] = job.get("geo_exclude") or []

    # ── Load Phase 1 candidates from DB ───────────────────────────────────
    all_p1 = (sb.table("candidates")
               .select("*")
               .eq("job_id", job_id)
               .eq("scan_depth", 1)
               .execute().data or [])

    if not all_p1:
        log.warning("deep_scan: no Phase 1 candidates found for job %s", job_id)
        _update_job(job_id, status="done", stats=stats)
        return {"ok": True, "stats": stats}

    log.info("deep_scan: %d Phase 1 candidates loaded", len(all_p1))

    # Split: candidates with a LinkedIn URL (can be deep-scraped, any source)
    # vs others (Telegram-only / file rows without a URL — score directly from P1 data)
    li_candidates    = [c for c in all_p1 if c.get("linkedin_url")]
    other_candidates = [c for c in all_p1 if not c.get("linkedin_url")]
    log.info("  With LinkedIn URL: %d  |  without URL (Telegram/etc): %d",
             len(li_candidates), len(other_candidates))

    # ── Phase 2a: Deep-scrape LinkedIn profiles (per-batch logging) ───────────
    _BATCH_SIZE = 25
    profile_urls  = [c["linkedin_url"] for c in li_candidates]
    total_batches = math.ceil(len(profile_urls) / _BATCH_SIZE) if profile_urls else 0
    deep_profiles: list[dict[str, Any]] = []

    for batch_idx in range(0, len(profile_urls), _BATCH_SIZE):
        batch      = profile_urls[batch_idx : batch_idx + _BATCH_SIZE]
        batch_num  = batch_idx // _BATCH_SIZE + 1

        _log_run(
            job_id, "deep_scrape", "started",
            msg=f"Batch {batch_num}/{total_batches} — scraping {len(batch)} profiles via Apify…",
        )
        
        # Emit progress
        from app.tasks.pipeline import emit_progress
        emit_progress(job_id, "deep_scan", batch_idx, len(profile_urls),
                     f"Scraping batch {batch_num}/{total_batches}...")
        
        try:
            with track_performance(f"deep_scrape_batch_{batch_num}"):
                results = scrape_one_batch(batch)
            deep_profiles.extend(results)
            _log_run(
                job_id, "deep_scrape", "ok", count=len(results),
                msg=f"Batch {batch_num}/{total_batches} — {len(results)}/{len(batch)} profiles retrieved",
            )
            
            # Emit progress after batch
            emit_progress(job_id, "deep_scan", min(batch_idx + _BATCH_SIZE, len(profile_urls)), len(profile_urls),
                         f"Completed {min(batch_idx + _BATCH_SIZE, len(profile_urls))}/{len(profile_urls)} profiles")
        except Exception as e:
            log.exception("deep scrape batch %d failed", batch_num)
            _log_run(
                job_id, "deep_scrape", "error", count=0,
                msg=f"Batch {batch_num}/{total_batches} failed: {str(e)[:300]}",
            )

        # Polite inter-batch delay (avoids LinkedIn anti-bot triggers)
        if batch_idx + _BATCH_SIZE < len(profile_urls):
            log.info("  waiting 30s before batch %d…", batch_num + 1)
            _time.sleep(30)

    stats["deep_scraped"] = len(deep_profiles)
    log.info("deep_scan: %d full profiles retrieved across %d batch(es)",
             len(deep_profiles), total_batches)

    # Index deep profiles by LinkedIn URL for fast lookup
    deep_by_url: dict[str, dict] = {}
    for dp in deep_profiles:
        url = (dp.get("linkedin_url") or "").lower().rstrip("/")
        if url:
            deep_by_url[url] = dp

    # ── Phase 2b: Merge deep data + deep geo filter ────────────────────────
    _log_run(job_id, "geo_filter_deep", "started")
    geo_ok: list[dict[str, Any]] = []
    geo_rejected_ids: list[str] = []

    for c in li_candidates:
        url_key = (c.get("linkedin_url") or "").lower().rstrip("/")
        dp = deep_by_url.get(url_key)

        if dp:
            # Merge: overwrite shallow fields with deep equivalents
            c["bio"]              = dp.get("bio") or c.get("bio")
            c["raw_text"]         = dp.get("raw_text") or c.get("raw_text")
            c["skills"]           = dp.get("skills") or c.get("skills") or []
            c["languages"]        = dp.get("languages") or c.get("languages") or []
            c["years_experience"] = dp.get("years_experience") or c.get("years_experience")
            c["open_to_work"]     = dp.get("open_to_work") or c.get("open_to_work")
            c["educations"]       = dp.get("educations") or []
            c["positions"]        = dp.get("positions") or []
            c["igaming_signal"]   = dp.get("igaming_signal") or c.get("igaming_signal")
            c["facebook_signal"]  = dp.get("facebook_signal") or c.get("facebook_signal")
            c["raw"]              = dp.get("raw") or c.get("raw") or {}
            c["scan_depth"]       = 2

        # Deep geo filter — checks education & position history
        if geo_exclude:
            hit, reason = is_geo_excluded_deep(c, geo_exclude)
            if hit:
                log.info("geo_excluded (deep): %s — %s", c.get("full_name"), reason)
                c["red_flags"] = list({*(c.get("red_flags") or []), reason})
                _insert_rejected(job_id, c, reason)
                geo_rejected_ids.append(c["id"])
                continue

        geo_ok.append(c)

    stats["deep_geo_excluded"] = len(geo_rejected_ids)
    _log_run(job_id, "geo_filter_deep", "ok",
             count=len(geo_ok),
             msg=f"rejected {len(geo_rejected_ids)} by deep geo filter")
    log.info("deep geo filter: %d passed, %d rejected", len(geo_ok), len(geo_rejected_ids))

    # ── Phase 2c: Score all candidates with enriched data ─────────────────
    # geo_ok = LinkedIn deep-scraped (surviving geo filter)
    # other_candidates = Telegram / file (no deep data, but geo-surface-filtered)
    surface_ok: list[dict[str, Any]] = []
    for c in other_candidates:
        if geo_exclude:
            hit, reason = is_geo_excluded(c, geo_exclude)
            if hit:
                c["red_flags"] = list({*(c.get("red_flags") or []), reason})
                _insert_rejected(job_id, c, reason)
                continue
        surface_ok.append(c)

    to_score = geo_ok + surface_ok
    log.info("scoring %d candidates (LinkedIn deep=%d, other=%d)",
             len(to_score), len(geo_ok), len(surface_ok))

    if not to_score:
        _update_job(job_id, status="done", stats=stats)
        return {"ok": True, "stats": stats}

    # TF-IDF re-filter on enriched bios (drop still-weak matches)
    _log_run(job_id, "embed", "started")
    try:
        with track_performance("stage1_refilter"):
            survivors = stage1_embed_filter(job, to_score, drop_bottom_pct=0.2)
        stats["deep_stage1_kept"] = len(survivors)
        _log_run(job_id, "embed", "ok", count=len(survivors))
    except Exception as e:
        log.exception("stage1 re-filter failed")
        _log_run(job_id, "embed", "error", message=str(e))
        survivors = to_score

    # LLM scoring
    _log_run(job_id, "score", "started")
    try:
        with track_performance("stage2_scoring"):
            scored = stage2_gemini_score(job, job.get("rubric") or {}, survivors)
        stats["deep_scored"] = len(scored)
        _log_run(job_id, "score", "ok", count=len(scored))
    except Exception as e:
        log.exception("scoring failed")
        _log_run(job_id, "score", "error", message=str(e))
        scored = survivors

    # ── Persist: UPDATE existing Phase 1 rows with deep data + scores ─────
    updated = 0
    for c in scored:
        try:
            _upsert_candidate(c["id"], {
                "bio":               c.get("bio"),
                "raw_text":          c.get("raw_text"),
                "skills":            c.get("skills") or [],
                "languages":         c.get("languages") or [],
                "years_experience":  c.get("years_experience"),
                "open_to_work":      bool(c.get("open_to_work")),
                "educations":        c.get("educations") or [],
                "positions":         c.get("positions") or [],
                "embed_similarity":  c.get("embed_similarity"),
                "gemini_score":      c.get("gemini_score"),
                "gemini_reasoning":  c.get("gemini_reasoning"),
                "gemini_dimensions": c.get("gemini_dimensions") or {},
                "red_flags":         c.get("red_flags") or [],
                "scan_depth":        c.get("scan_depth") or 2,
                "raw":               {k: v for k, v in (c.get("raw") or {}).items()
                                      if _json_safe(v)},
                "status":            "scored",
            })
            updated += 1
        except Exception:
            log.exception("upsert failed for candidate %s", c.get("id"))

    stats["deep_updated"] = updated
    log.info("deep_scan complete: %d candidates updated with scores", updated)

    _update_job(job_id, status="done", stats=stats)
    
    # Log performance summary
    log_performance_summary()
    
    return {"ok": True, "phase": 2, "stats": stats}
