"""Score Phase 1 candidates directly — no Apify deep scraping required.

Use this when:
  - The SalesNav/PhantomBuster export already has rich bio/position data, OR
  - Apify deep scraping is unavailable / returns 0 profiles.

Flow:
  1. Load all unscored Phase 1 candidates (scan_depth=1, status='new')
  2. Surface geo filter (location / bio text)
  3. TF-IDF similarity filter (drop bottom 20%)
  4. LLM scoring on P1 data (bio = Summary from SalesNav, headline = Title, etc.)
  5. UPDATE candidate rows with scores + set job status = 'done'
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.db import get_supabase
from app.core.logging import get_logger
from app.scoring.pipeline import stage1_embed_filter, stage2_gemini_score
from app.utils.geo_filter import is_geo_excluded

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


@celery_app.task(
    name="sourcer.score_now",
    bind=True,
    time_limit=60 * 90,      # 90-min hard limit
    soft_time_limit=60 * 85,
)
def score_now(self, job_id: str) -> dict[str, Any]:
    """Score existing Phase 1 candidates without Apify deep scraping."""
    sb = get_supabase()
    job = sb.table("jobs").select("*").eq("id", job_id).single().execute().data
    if not job:
        raise RuntimeError(f"job {job_id} not found")

    _update_job(job_id, status="running_deep", error=None)
    stats: dict[str, Any] = dict(job.get("stats") or {})
    geo_exclude: list[str] = job.get("geo_exclude") or []
    
    # Check for checkpoint to resume from
    checkpoint = job.get("checkpoint") or {}
    resume_from_score = checkpoint.get("stage") == "score" and checkpoint.get("can_resume")

    # ── Load Phase 1 candidates ──────────────────────────────────────────────
    if resume_from_score:
        # Resume: Load only unscored candidates
        candidates = (
            sb.table("candidates")
            .select("*")
            .eq("job_id", job_id)
            .eq("scan_depth", 1)
            .is_("gemini_score", "null")
            .execute()
            .data or []
        )
        log.info("score_now: RESUMING from checkpoint - %d unscored candidates remaining", len(candidates))
    else:
        # Fresh start: Load all Phase 1 candidates
        candidates = (
            sb.table("candidates")
            .select("*")
            .eq("job_id", job_id)
            .eq("scan_depth", 1)
            .execute()
            .data or []
        )
        log.info("score_now: %d Phase 1 candidates loaded for job %s", len(candidates), job_id)

    if not candidates:
        _update_job(job_id, status="done", stats=stats, checkpoint=None)
        return {"ok": True, "stats": stats}

    # ── Surface geo filter (skip if resuming from score) ────────────────────
    if resume_from_score:
        # Already filtered, skip to scoring
        log.info("score_now: Skipping geo filter (resuming from checkpoint)")
        survivors = candidates
    else:
        # ── Surface geo filter ───────────────────────────────────────────────
        _log_run(job_id, "geo_filter_deep", "started",
                 msg=f"Surface geo filter on {len(candidates)} candidates…")
        geo_ok, geo_rejected = [], []
        for c in candidates:
            if geo_exclude:
                hit, reason = is_geo_excluded(c, geo_exclude)
                if hit:
                    c["red_flags"] = list({*(c.get("red_flags") or []), reason})
                    sb.table("candidates").update({
                        "status": "rejected",
                        "red_flags": c["red_flags"],
                        "gemini_score": 0,
                        "gemini_reasoning": reason,
                    }).eq("id", c["id"]).execute()
                    geo_rejected.append(c)
                    continue
            geo_ok.append(c)

        stats["geo_excluded_p1"] = len(geo_rejected)
        _log_run(job_id, "geo_filter_deep", "ok", count=len(geo_ok),
                 msg=f"Rejected {len(geo_rejected)} by geo filter")
        log.info("score_now: geo filter: %d ok, %d rejected", len(geo_ok), len(geo_rejected))

        if not geo_ok:
            _update_job(job_id, status="done", stats=stats, checkpoint=None)
            return {"ok": True, "stats": stats}

        # ── TF-IDF similarity filter ─────────────────────────────────────────
        _log_run(job_id, "embed", "started",
                 msg=f"TF-IDF ranking {len(geo_ok)} candidates…")
        try:
            survivors = stage1_embed_filter(job, geo_ok, drop_bottom_pct=0.15)
            stats["score_now_kept"] = len(survivors)
            _log_run(job_id, "embed", "ok", count=len(survivors))
        except Exception as e:
            log.exception("TF-IDF filter failed")
            _log_run(job_id, "embed", "error", msg=str(e))
            survivors = geo_ok

    # ── LLM scoring with checkpoint support ──────────────────────────────────
    _log_run(job_id, "score", "started",
             msg=f"LLM scoring {len(survivors)} candidates (P1 data)…")
    
    # Checkpoint callback to save progress every 10 candidates
    def save_checkpoint(scored_count: int, total_count: int):
        """Save scoring progress to job checkpoint and emit progress."""
        try:
            checkpoint = {
                "stage": "score",
                "scored_count": scored_count,
                "total_count": total_count,
                "timestamp": datetime.utcnow().isoformat(),
                "can_resume": True,
            }
            sb.table("jobs").update({"checkpoint": checkpoint}).eq("id", job_id).execute()
            log.debug(f"Checkpoint saved: {scored_count}/{total_count} scored")
            
            # Emit progress update
            from app.tasks.pipeline import emit_progress
            emit_progress(job_id, "score", scored_count, total_count, f"Scoring candidates...")
        except Exception:
            log.exception("Failed to save checkpoint")
    
    try:
        batch_size = settings.batch_scoring_size if settings.batch_scoring_enabled else 1
        scored = stage2_gemini_score(
            job, 
            job.get("rubric") or {}, 
            survivors,
            batch_size=batch_size,
            checkpoint_callback=save_checkpoint
        )
        stats["score_now_scored"] = len(scored)
        _log_run(job_id, "score", "ok", count=len(scored))
    except Exception as e:
        log.exception("LLM scoring failed")
        _log_run(job_id, "score", "error", msg=str(e))
        scored = survivors

    # ── Persist scores ───────────────────────────────────────────────────────
    updated = 0
    for c in scored:
        try:
            sb.table("candidates").update({
                "gemini_score":      c.get("gemini_score"),
                "gemini_reasoning":  c.get("gemini_reasoning"),
                "gemini_dimensions": c.get("gemini_dimensions") or {},
                "embed_similarity":  c.get("embed_similarity"),
                "red_flags":         c.get("red_flags") or [],
                "status":            "scored",
                # Keep scan_depth=1 — no deep scrape was done
            }).eq("id", c["id"]).execute()
            updated += 1
        except Exception:
            log.exception("update failed for candidate %s", c.get("id"))

    stats["score_now_updated"] = updated
    log.info("score_now: %d candidates scored and updated", updated)

    # Clear checkpoint on completion
    _update_job(job_id, status="done", stats=stats, checkpoint=None)
    return {"ok": True, "phase": "score_now", "stats": stats}
