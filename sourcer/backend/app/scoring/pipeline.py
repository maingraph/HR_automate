"""Two-stage scoring orchestration: embed+filter, then LLM score.

Stage 1 has two implementations:
  - Gemini provider  : 768-dim embeddings via Gemini text-embedding-004 + cosine similarity
  - OpenRouter provider : local TF-IDF (sklearn) + cosine similarity — no API calls
"""
from __future__ import annotations

import math
import time
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity as sk_cosine

from app.core.config import settings
from app.core.logging import get_logger
from app.scoring.gemini import embed_query, embed_texts, score_candidate, score_candidates_batch

log = get_logger(__name__)

# Gemini free-tier: ~5 generate_content req/min → throttle to be safe.
# Override via env SCORE_RATE_LIMIT_SEC (seconds between calls).
import os

SCORE_RATE_LIMIT_SEC = float(os.getenv("SCORE_RATE_LIMIT_SEC", "13"))


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    va, vb = np.array(a), np.array(b)
    denom = (np.linalg.norm(va) * np.linalg.norm(vb)) or 1.0
    return float(np.dot(va, vb) / denom)


def _candidate_blob(c: dict[str, Any]) -> str:
    parts = [
        c.get("full_name"),
        c.get("headline"),
        c.get("location"),
        ", ".join(c.get("skills") or []),
        c.get("bio") or c.get("raw_text"),
    ]
    return "\n".join(str(p) for p in parts if p)


def _job_blob(job: dict[str, Any]) -> str:
    return "\n".join(
        str(p)
        for p in [
            job.get("title"),
            job.get("description"),
            ", ".join(job.get("skills") or []),
            f"geo: {job.get('geo')}",
            f"seniority: {job.get('seniority')}",
        ]
        if p
    )


def _stage1_tfidf(
    job: dict[str, Any],
    candidates: list[dict[str, Any]],
    drop: float,
) -> list[dict[str, Any]]:
    """Local TF-IDF similarity — no API calls. Used when AI_PROVIDER=openrouter."""
    job_blob = _job_blob(job)
    blobs = [_candidate_blob(c) for c in candidates]

    vectorizer = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        min_df=1,
        sublinear_tf=True,
    )
    corpus = [job_blob] + blobs
    tfidf = vectorizer.fit_transform(corpus)
    job_vec = tfidf[0]
    cand_vecs = tfidf[1:]

    sims = sk_cosine(job_vec, cand_vecs)[0]

    for c, sim in zip(candidates, sims):
        c["embedding"] = None  # no dense vector to store
        c["embed_similarity"] = float(sim)

    candidates.sort(key=lambda x: x.get("embed_similarity") or 0.0, reverse=True)

    if drop <= 0:
        return candidates
    keep = max(1, math.ceil(len(candidates) * (1 - drop)))
    survivors = candidates[:keep]
    log.info("stage1 (tfidf): kept %d/%d (drop bottom %.0f%%)", len(survivors), len(candidates), drop * 100)
    return survivors


def _stage1_gemini(
    job: dict[str, Any],
    candidates: list[dict[str, Any]],
    drop: float,
) -> list[dict[str, Any]]:
    """Dense embedding similarity via Gemini text-embedding-004."""
    job_emb = embed_query(_job_blob(job))
    blobs = [_candidate_blob(c) for c in candidates]
    embs = embed_texts(blobs)

    for c, emb in zip(candidates, embs):
        c["embedding"] = emb
        c["embed_similarity"] = _cosine(job_emb, emb)

    candidates.sort(key=lambda x: x.get("embed_similarity") or 0.0, reverse=True)

    if drop <= 0:
        return candidates
    keep = max(1, math.ceil(len(candidates) * (1 - drop)))
    survivors = candidates[:keep]
    log.info("stage1 (gemini): kept %d/%d (drop bottom %.0f%%)", len(survivors), len(candidates), drop * 100)
    return survivors


def stage1_embed_filter(
    job: dict[str, Any],
    candidates: list[dict[str, Any]],
    drop_bottom_pct: float | None = None,
) -> list[dict[str, Any]]:
    """Filter candidates by semantic similarity to the job description.

    Uses TF-IDF (local, no API) when AI_PROVIDER=openrouter,
    or Gemini dense embeddings when AI_PROVIDER=gemini.
    """
    if not candidates:
        return []
    drop = settings.embedding_filter_percentile if drop_bottom_pct is None else drop_bottom_pct

    if settings.ai_provider == "openrouter":
        return _stage1_tfidf(job, candidates, drop)
    else:
        return _stage1_gemini(job, candidates, drop)


def stage2_gemini_score(
    job: dict[str, Any],
    rubric: dict[str, Any],
    candidates: list[dict[str, Any]],
    batch_size: int = 5,
    checkpoint_callback: callable = None,
) -> list[dict[str, Any]]:
    """Score each candidate via the configured LLM provider.

    Uses batch scoring for 5-10x speedup when batch_size > 1.
    Throttled to SCORE_RATE_LIMIT_SEC between calls on Gemini (free-tier RPM).
    No throttle on OpenRouter (paid, much higher limits).
    
    Args:
        job: Job dictionary with requirements
        rubric: Scoring rubric
        candidates: List of candidates to score
        batch_size: Number of candidates per API call (5-10 recommended, 1 = individual scoring)
        checkpoint_callback: Optional callback to save progress (called every batch)
    """
    # OpenRouter: no artificial throttle needed
    effective_rate_limit = 0.0 if settings.ai_provider == "openrouter" else SCORE_RATE_LIMIT_SEC

    last_call = 0.0
    total = len(candidates)
    scored_count = 0
    
    # Process in batches
    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch = candidates[batch_start:batch_end]
        
        # Rate-limit between batches
        wait = effective_rate_limit - (time.time() - last_call)
        if wait > 0 and batch_start > 0:
            time.sleep(wait)
        last_call = time.time()
        
        try:
            if len(batch) == 1 or batch_size == 1:
                # Single candidate - use individual scoring
                c = batch[0]
                s = score_candidate(job, rubric, c)
                c["gemini_score"] = s["score"]
                c["gemini_reasoning"] = s["reasoning"]
                c["gemini_dimensions"] = s["dimensions"]
                existing_flags = c.get("red_flags") or []
                c["red_flags"] = list({*existing_flags, *s["red_flags"]})
            else:
                # Batch scoring
                batch_scores = score_candidates_batch(job, rubric, batch)
                
                # Apply scores to candidates
                for c, s in zip(batch, batch_scores):
                    c["gemini_score"] = s["score"]
                    c["gemini_reasoning"] = s["reasoning"]
                    c["gemini_dimensions"] = s["dimensions"]
                    existing_flags = c.get("red_flags") or []
                    c["red_flags"] = list({*existing_flags, *s["red_flags"]})
                    
        except Exception as e:
            log.exception(f"Batch scoring failed for batch {batch_start}-{batch_end}, falling back to individual scoring")
            # Fall back to individual scoring for this batch
            for c in batch:
                try:
                    s = score_candidate(job, rubric, c)
                    c["gemini_score"] = s["score"]
                    c["gemini_reasoning"] = s["reasoning"]
                    c["gemini_dimensions"] = s["dimensions"]
                    existing_flags = c.get("red_flags") or []
                    c["red_flags"] = list({*existing_flags, *s["red_flags"]})
                except Exception:
                    log.exception("Individual scoring failed for %s", c.get("full_name") or c.get("username"))
                    c["gemini_score"] = 0
                    c["gemini_reasoning"] = "scoring failed"
                    c["gemini_dimensions"] = {}
                    c["red_flags"] = ["scoring_error"]
        
        scored_count = batch_end
        
        # Log progress and save checkpoint after each batch
        log.info(f"Scored {scored_count}/{total} candidates ({(scored_count / total * 100):.1f}%) [batch size: {len(batch)}]")
        
        # Save checkpoint if callback provided
        if checkpoint_callback:
            try:
                checkpoint_callback(scored_count, total)
            except Exception:
                log.exception("Checkpoint callback failed")
    
    candidates.sort(key=lambda x: x.get("gemini_score") or 0, reverse=True)
    return candidates
