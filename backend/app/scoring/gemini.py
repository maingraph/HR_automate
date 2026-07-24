"""LLM-powered plan generation + structured candidate scoring.

Supports two backends controlled by AI_PROVIDER env var:
  - "gemini"     : direct Google Gemini API (google-genai SDK)
  - "openrouter" : OpenAI-compatible proxy at openrouter.ai (openai SDK)

Gemini path supports multiple API keys (GEMINI_API_KEYS, comma-separated)
with automatic rotation on HTTP 429 quota errors.
"""
from __future__ import annotations

import itertools
import json
import re
import time
from typing import Any

from google import genai
from google.genai import errors, types
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis_client import cache_result
from app.scoring.prompt_builder import build_plan_system_prompt, build_score_system_prompt

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Global rate limiter — max 10 req/min across all keys (free tier: 15 RPM/key)
# ---------------------------------------------------------------------------
import threading

_rate_lock = threading.Lock()
_rate_times: list[float] = []
_RATE_WINDOW = 60.0
_RATE_MAX = 10


def _rate_limit() -> None:
    """Block until we're below 10 calls in the last 60 s."""
    with _rate_lock:
        now = time.time()
        # drop timestamps outside the window
        _rate_times[:] = [t for t in _rate_times if now - t < _RATE_WINDOW]
        if len(_rate_times) >= _RATE_MAX:
            sleep_for = _RATE_WINDOW - (now - _rate_times[0]) + 0.1
            if sleep_for > 0:
                time.sleep(sleep_for)
            _rate_times[:] = [t for t in _rate_times if time.time() - t < _RATE_WINDOW]
        _rate_times.append(time.time())


# ---------------------------------------------------------------------------
# Key pool + rotator
# ---------------------------------------------------------------------------

def _build_key_pool() -> list[str]:
    raw = settings.gemini_api_keys or settings.gemini_api_key
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    if not keys:
        raise RuntimeError("No Gemini API key configured")
    return keys


# Track which keys are daily-exhausted so we skip them
_exhausted_keys: set[str] = set()


_key_pool: list[str] = []
_key_cycle: "itertools.cycle[str] | None" = None
_current_key: str = ""
_current_client: genai.Client | None = None


def reset_gemini_client() -> None:
    """Reset cached key state after runtime credential changes."""
    global _key_pool, _key_cycle, _current_key, _current_client, _exhausted_keys
    if _current_client is not None:
        _current_client.close()
    _key_pool = []
    _key_cycle = None
    _current_key = ""
    _current_client = None
    _exhausted_keys = set()


def _select_key(key: str) -> None:
    global _current_key, _current_client
    if _current_client is not None:
        _current_client.close()
    _current_key = key
    _current_client = genai.Client(api_key=key)


def _init_keys() -> genai.Client:
    global _key_pool, _key_cycle
    if _key_cycle is None:
        _key_pool = _build_key_pool()
        _key_cycle = itertools.cycle(_key_pool)
        _select_key(next(_key_cycle))
        log.info("Gemini key pool: %d key(s)", len(_key_pool))
    if _current_client is None:
        raise RuntimeError("Gemini client failed to initialize")
    return _current_client


def _rotate_key(mark_exhausted: bool = False) -> None:
    if _key_cycle is None:
        _init_keys()
        return
    if mark_exhausted:
        _exhausted_keys.add(_current_key)
        log.warning("Key marked daily-exhausted (%d/%d exhausted)", len(_exhausted_keys), len(_key_pool))
    # Find next non-exhausted key
    for _ in range(len(_key_pool)):
        candidate = next(_key_cycle)
        if candidate not in _exhausted_keys:
            _select_key(candidate)
            log.info("Rotated to Gemini key (pool=%d, exhausted=%d)", len(_key_pool), len(_exhausted_keys))
            return
    # All keys exhausted — still set the next one and hope quota reset
    _select_key(next(_key_cycle))
    _exhausted_keys.clear()  # reset and try again
    log.warning("All Gemini keys exhausted — resetting and retrying")


def _retry_delay_from_exc(exc: BaseException) -> float:
    msg = str(exc)
    m = re.search(r"retry[_ ]in[:\s]+(\d+(?:\.\d+)?)\s*s", msg, re.IGNORECASE)
    return float(m.group(1)) + 1.0 if m else 15.0


def _before_sleep(retry_state) -> None:
    exc = retry_state.outcome.exception()
    if exc is None:
        return
    if isinstance(exc, errors.APIError) and exc.code == 429:
        msg = str(exc)
        daily = "PerDay" in msg
        _rotate_key(mark_exhausted=daily)
        delay = _retry_delay_from_exc(exc)
        actual = min(delay, 20.0)
        log.warning("Gemini quota (daily=%s) — rotated key, sleeping %.1fs (attempt %d)",
                    daily, actual, retry_state.attempt_number)
        time.sleep(actual)
    else:
        time.sleep(2.0)


# ---------------------------------------------------------------------------
# OpenRouter backend
# ---------------------------------------------------------------------------

def _call_openrouter(
    system: str,
    prompt: str,
    temperature: float = 0.3,
    model: str | None = None,
) -> str:
    """Call any model via OpenRouter's OpenAI-compatible API and return raw text."""
    from openai import OpenAI  # lazy import — only needed when AI_PROVIDER=openrouter

    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
    )
    resp = client.chat.completions.create(
        model=model or settings.openrouter_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content or ""


@retry(stop=stop_after_attempt(5), wait=wait_exponential(min=2, max=30))
def _call_openrouter_retry(
    system: str,
    prompt: str,
    temperature: float = 0.3,
    model: str | None = None,
) -> str:
    return _call_openrouter(system, prompt, temperature, model)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s)
    return s


def _json_from_text(text: str) -> Any:
    t = _strip_code_fences(text)
    try:
        return json.loads(t)
    except Exception:
        m = re.search(r"\{[\s\S]*\}$", t)
        if m:
            return json.loads(m.group(0))
        raise


def _generate_gemini(
    system: str | None,
    prompt: str | list[str],
    temperature: float = 0.3,
    model: str | None = None,
) -> str:
    client = _init_keys()
    _rate_limit()
    response = client.models.generate_content(
        model=model or settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            temperature=temperature,
        ),
    )
    if not response.text:
        raise RuntimeError("Gemini returned an empty response")
    return response.text


# ---------------------------------------------------------------------------
# Plan generation
# ---------------------------------------------------------------------------

@retry(stop=stop_after_attempt(8 * 4), wait=wait_exponential(min=1, max=30), before_sleep=_before_sleep)
def _generate_plan_gemini(job: dict[str, Any]) -> dict[str, Any]:
    """Generate recruitment plan using Gemini API.
    
    Args:
        job: Job dictionary with vacancy details
        
    Returns:
        Plan dictionary with linkedin_queries, tg_keywords, hard_filters, rubric
    """
    prompt = json.dumps(
        {k: job.get(k) for k in ("title", "description", "skills", "geo", "seniority", "budget_min", "budget_max")},
        ensure_ascii=False,
    )
    return _json_from_text(_generate_gemini(
        build_plan_system_prompt(job),
        prompt,
        temperature=0.3,
        model=settings.get_model_for_task("job_planning"),
    ))


@cache_result(ttl=604800, key_prefix="rubric")  # Cache for 7 days
def generate_plan(job: dict[str, Any]) -> dict[str, Any]:
    """
    Given a vacancy dict, return {linkedin_queries, linkedin_boolean, tg_keywords, hard_filters, rubric}.
    
    Cached for 7 days based on job details (title, skills, seniority).
    """
    prompt = json.dumps(
        {k: job.get(k) for k in ("title", "description", "skills", "geo", "seniority", "budget_min", "budget_max")},
        ensure_ascii=False,
    )
    if settings.ai_provider == "openrouter":
        raw = _call_openrouter_retry(
            build_plan_system_prompt(job),
            prompt,
            temperature=0.3,
            model=settings.get_model_for_task("job_planning"),
        )
        data = _json_from_text(raw)
    else:
        data = _generate_plan_gemini(job)

    # Back-compat: if old single boolean returned, wrap it
    queries = data.get("linkedin_queries") or []
    if not queries and data.get("linkedin_boolean"):
        queries = [data["linkedin_boolean"]]
    if not queries:
        queries = [f'("{job.get("title", "")}")']
    data["linkedin_queries"] = queries
    data["linkedin_boolean"] = queries[0]  # keep legacy field

    data.setdefault("tg_keywords", [])
    data.setdefault("hard_filters", [])
    if not data.get("rubric"):
        # Fallback rubric derived from job fields — no iGaming/Facebook hardcoding
        _title     = job.get("title") or ""
        _seniority = job.get("seniority") or "Mid-Senior"
        _bmin      = job.get("budget_min")
        _bmax      = job.get("budget_max")
        _rubric: dict[str, Any] = {
            "skills_match":  {"weight": 40, "description": f"Candidate has the primary required skills for {_title!r}"},
            "seniority_fit": {"weight": 25, "description": f"Candidate matches {_seniority} level; penalise overqualified and underqualified"},
            "industry_fit":  {"weight": 20, "description": "Candidate has relevant industry/vertical experience"},
            "availability":  {"weight": 15, "description": "Open to work or actively searching"},
        }
        if _bmin:
            _rubric["budget_scale"] = {"weight": 10, "description": f"Works at required scale (${_bmin:,}+/mo)"}
            _rubric["availability"]["weight"] = 5
        data["rubric"] = _rubric
    return data


# ---------------------------------------------------------------------------
# Candidate scoring
# ---------------------------------------------------------------------------

def _build_score_prompt(job: dict[str, Any], rubric: dict[str, Any], candidate: dict[str, Any]) -> str:
    """Build the candidate scoring prompt.
    
    Args:
        job: Job dictionary with vacancy details
        rubric: Scoring rubric with dimensions and weights
        candidate: Candidate dictionary with profile data
        
    Returns:
        JSON-formatted prompt string
    """
    candidate_text = "\n".join(
        f"{k}: {v}"
        for k, v in {
            "name": candidate.get("full_name"),
            "headline": candidate.get("headline"),
            "location": candidate.get("location"),
            "skills": ", ".join(candidate.get("skills") or []),
            "years_experience": candidate.get("years_experience"),
            "bio": (candidate.get("bio") or candidate.get("raw_text") or "")[:3500],
            "open_to_work": candidate.get("open_to_work"),
            "source": candidate.get("source"),
        }.items()
        if v not in (None, "", [])
    )
    vacancy_dict: dict[str, Any] = {
        k: job.get(k)
        for k in ("title", "description", "skills", "geo", "seniority", "budget_min", "budget_max")
    }
    # Explicitly pass geo_exclude so the LLM can apply disqualifier #6
    if job.get("geo_exclude"):
        vacancy_dict["geo_exclude"] = job["geo_exclude"]

    return json.dumps(
        {
            "vacancy": vacancy_dict,
            "rubric": rubric,
            "candidate": candidate_text,
        },
        ensure_ascii=False,
    )


def _parse_score_response(out: dict[str, Any]) -> dict[str, Any]:
    # Handle both "score" and "overall_score" keys for compatibility
    score = out.get("score") or out.get("overall_score", 0)
    return {
        "score": int(max(0, min(100, score))),
        "dimensions": out.get("dimensions") or {},
        "reasoning": out.get("reasoning") or "",
        "red_flags": out.get("red_flags") or [],
    }


def _build_batch_score_prompt(job: dict[str, Any], rubric: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    """Build the batch candidate scoring prompt.
    
    Args:
        job: Job dictionary with vacancy details
        rubric: Scoring rubric with dimensions and weights
        candidates: List of candidate dictionaries with profile data
        
    Returns:
        JSON-formatted prompt string for batch scoring
    """
    candidates_data = []
    for idx, candidate in enumerate(candidates):
        candidate_text = "\n".join(
            f"{k}: {v}"
            for k, v in {
                "name": candidate.get("full_name"),
                "headline": candidate.get("headline"),
                "location": candidate.get("location"),
                "skills": ", ".join(candidate.get("skills") or []),
                "years_experience": candidate.get("years_experience"),
                "bio": (candidate.get("bio") or candidate.get("raw_text") or "")[:3500],
                "open_to_work": candidate.get("open_to_work"),
                "source": candidate.get("source"),
            }.items()
            if v not in (None, "", [])
        )
        candidates_data.append({
            "id": str(idx),  # Use index as ID for matching
            "candidate_id": candidate.get("id"),  # Store actual DB ID
            "data": candidate_text
        })
    
    vacancy_dict: dict[str, Any] = {
        k: job.get(k)
        for k in ("title", "description", "skills", "geo", "seniority", "budget_min", "budget_max")
    }
    if job.get("geo_exclude"):
        vacancy_dict["geo_exclude"] = job["geo_exclude"]

    return json.dumps(
        {
            "vacancy": vacancy_dict,
            "rubric": rubric,
            "candidates": candidates_data,
        },
        ensure_ascii=False,
    )


def _parse_batch_score_response(out: dict[str, Any], candidate_count: int) -> list[dict[str, Any]]:
    """Parse batch scoring response and validate all candidates are present.
    
    Args:
        out: Raw response dictionary
        candidate_count: Expected number of candidates
        
    Returns:
        List of score dictionaries, one per candidate
        
    Raises:
        ValueError: If response is missing candidates or malformed
    """
    scores = out.get("scores", [])
    
    if not isinstance(scores, list):
        raise ValueError("Response 'scores' field is not a list")
    
    if len(scores) != candidate_count:
        raise ValueError(f"Expected {candidate_count} scores, got {len(scores)}")
    
    parsed_scores = []
    for idx, score_data in enumerate(scores):
        # Validate ID matches
        if str(score_data.get("id")) != str(idx):
            log.warning(f"Score ID mismatch: expected {idx}, got {score_data.get('id')}")
        
        parsed_scores.append({
            "score": int(max(0, min(100, score_data.get("score", 0)))),
            "dimensions": score_data.get("dimensions") or {},
            "reasoning": score_data.get("reasoning") or "",
            "red_flags": score_data.get("red_flags") or [],
        })
    
    return parsed_scores


@retry(stop=stop_after_attempt(8 * 4), wait=wait_exponential(min=1, max=30), before_sleep=_before_sleep)
def _score_candidate_gemini(job: dict[str, Any], rubric: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Score candidate using Gemini API.
    
    Args:
        job: Job dictionary with vacancy details
        rubric: Scoring rubric with dimensions and weights
        candidate: Candidate dictionary with profile data
        
    Returns:
        Score dictionary with score, dimensions, reasoning, red_flags
    """
    prompt = _build_score_prompt(job, rubric, candidate)
    raw = _generate_gemini(
        build_score_system_prompt(job, rubric),
        prompt,
        temperature=0.2,
        model=settings.get_model_for_task("scoring"),
    )
    return _parse_score_response(_json_from_text(raw))


@retry(stop=stop_after_attempt(8 * 4), wait=wait_exponential(min=1, max=30), before_sleep=_before_sleep)
def _score_candidates_batch_gemini(job: dict[str, Any], rubric: dict[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Score multiple candidates in one API call using Gemini.
    
    Args:
        job: Job dictionary with vacancy details
        rubric: Scoring rubric with dimensions and weights
        candidates: List of candidate dictionaries (max 10 recommended)
        
    Returns:
        List of score dictionaries, one per candidate
    """
    from app.scoring.prompt_builder import build_batch_score_system_prompt
    
    prompt = _build_batch_score_prompt(job, rubric, candidates)
    raw = _generate_gemini(
        build_batch_score_system_prompt(job, rubric, len(candidates)),
        prompt,
        temperature=0.2,
        model=settings.get_model_for_task("scoring"),
    )
    return _parse_batch_score_response(_json_from_text(raw), len(candidates))


def _score_candidates_batch_openrouter(job: dict[str, Any], rubric: dict[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Score multiple candidates in one API call using OpenRouter.
    
    Args:
        job: Job dictionary with vacancy details
        rubric: Scoring rubric with dimensions and weights
        candidates: List of candidate dictionaries (max 10 recommended)
        
    Returns:
        List of score dictionaries, one per candidate
    """
    from app.scoring.prompt_builder import build_batch_score_system_prompt
    
    system_prompt = build_batch_score_system_prompt(job, rubric, len(candidates))
    prompt = _build_batch_score_prompt(job, rubric, candidates)
    raw = _call_openrouter_retry(
        system_prompt,
        prompt,
        temperature=0.2,
        model=settings.get_model_for_task("scoring"),
    )
    return _parse_batch_score_response(_json_from_text(raw), len(candidates))


def score_candidate(job: dict[str, Any], rubric: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Score a candidate against job requirements.
    
    Routes to appropriate AI provider (Gemini or OpenRouter).
    
    Args:
        job: Job dictionary with vacancy details
        rubric: Scoring rubric with dimensions and weights
        candidate: Candidate dictionary with profile data
        
    Returns:
        Score dictionary with score, dimensions, reasoning, red_flags
    """
    prompt = _build_score_prompt(job, rubric, candidate)
    if settings.ai_provider == "openrouter":
        raw = _call_openrouter_retry(
            build_score_system_prompt(job, rubric),
            prompt,
            temperature=0.2,
            model=settings.get_model_for_task("scoring"),
        )
        return _parse_score_response(_json_from_text(raw))
    else:
        return _score_candidate_gemini(job, rubric, candidate)


def score_candidates_batch(job: dict[str, Any], rubric: dict[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Score multiple candidates in one API call for 5-10x speedup.
    
    Routes to appropriate AI provider (Gemini or OpenRouter).
    
    Args:
        job: Job dictionary with vacancy details
        rubric: Scoring rubric with dimensions and weights
        candidates: List of candidate dictionaries (recommended: 5-10 per batch)
        
    Returns:
        List of score dictionaries, one per candidate in same order
        
    Raises:
        ValueError: If response is malformed or missing candidates
    """
    if not candidates:
        return []
    
    if len(candidates) == 1:
        # Single candidate - use regular scoring
        return [score_candidate(job, rubric, candidates[0])]
    
    log.info(f"Batch scoring {len(candidates)} candidates")
    
    if settings.ai_provider == "openrouter":
        return _score_candidates_batch_openrouter(job, rubric, candidates)
    else:
        return _score_candidates_batch_gemini(job, rubric, candidates)


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

EMBED_DIM = 768


@retry(stop=stop_after_attempt(8 * 4), wait=wait_exponential(min=1, max=30), before_sleep=_before_sleep)
def embed_texts(texts: list[str], batch_size: int = 100) -> list[list[float]]:
    """Return 768-dim embeddings (matches Supabase vector(768)).
    
    Args:
        texts: List of texts to embed
        batch_size: Number of texts to embed per API call (Gemini supports batching)
        
    Returns:
        List of embedding vectors
    """
    client = _init_keys()
    if not texts:
        return []
    
    out: list[list[float]] = []
    total = len(texts)
    
    # Process in batches to reduce API calls
    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch = texts[batch_start:batch_end]
        
        _rate_limit()
        
        # Process each text in the batch
        for i, t in enumerate(batch):
            t = (t or "")[:8000]
            if not t.strip():
                out.append([0.0] * EMBED_DIM)
                continue
            r = client.models.embed_content(
                model=settings.gemini_embed_model,
                contents=t,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=EMBED_DIM,
                ),
            )
            if not r.embeddings or not r.embeddings[0].values:
                raise RuntimeError("Gemini returned an empty embedding")
            out.append(list(r.embeddings[0].values))
        
        # Log progress
        if batch_end % 100 == 0 or batch_end == total:
            log.info(f"Embedded {batch_end}/{total} texts ({(batch_end / total * 100):.1f}%)")
    
    return out


@retry(stop=stop_after_attempt(8 * 4), wait=wait_exponential(min=1, max=30), before_sleep=_before_sleep)
def embed_query(text: str) -> list[float]:
    client = _init_keys()
    _rate_limit()
    r = client.models.embed_content(
        model=settings.gemini_embed_model,
        contents=text or "",
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=EMBED_DIM,
        ),
    )
    if not r.embeddings or not r.embeddings[0].values:
        raise RuntimeError("Gemini returned an empty embedding")
    return list(r.embeddings[0].values)


# ---------------------------------------------------------------------------
# Vacancy Structuring
# ---------------------------------------------------------------------------

def structure_vacancy(raw_text: str) -> dict[str, Any]:
    """Extract structured job data from raw vacancy text.
    
    Args:
        raw_text: Raw vacancy text (from email, job board, notes, etc.)
    
    Returns:
        Dictionary with structured fields:
        {
            "title": str,
            "description": str | None,
            "skills": list[str],
            "seniority": str | None,
            "geo": str | None,
            "budget_min": int | None,
            "budget_max": int | None
        }
    """
    from app.scoring.prompt_builder import build_vacancy_structure_prompt
    
    log.info("Structuring vacancy from raw text (%d chars)", len(raw_text))
    
    system_prompt = build_vacancy_structure_prompt(raw_text)
    user_prompt = f"Raw vacancy text:\n\n{raw_text}"
    
    # Use appropriate provider
    if settings.ai_provider == "openrouter":
        result = _structure_vacancy_openrouter(system_prompt, user_prompt)
    else:
        result = _structure_vacancy_gemini(system_prompt, user_prompt)
    
    log.info("Vacancy structured: title='%s', skills=%s", result.get("title"), result.get("skills"))
    return result


def _structure_vacancy_gemini(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """Structure vacancy using Gemini API."""
    text = _generate_gemini(
        system_prompt,
        user_prompt,
        temperature=0.3,
        model=settings.get_model_for_task("vacancy_structure"),
    )
    result = _json_from_text(text)
    
    # Validate and normalize
    if not result.get("title"):
        raise ValueError("Failed to extract job title from raw text")
    
    return {
        "title": result.get("title", ""),
        "description": result.get("description") or None,
        "skills": result.get("skills") or [],
        "seniority": result.get("seniority") or None,
        "geo": result.get("geo") or None,
        "budget_min": result.get("budget_min") or None,
        "budget_max": result.get("budget_max") or None,
    }


def _structure_vacancy_openrouter(system_prompt: str, user_prompt: str) -> dict[str, Any]:
    """Structure vacancy using OpenRouter API."""
    text = _call_openrouter_retry(
        system=system_prompt,
        prompt=user_prompt,
        temperature=0.3,
        model=settings.get_model_for_task("vacancy_structure"),
    )
    
    result = _json_from_text(text)
    
    # Validate and normalize
    if not result.get("title"):
        raise ValueError("Failed to extract job title from raw text")
    
    return {
        "title": result.get("title", ""),
        "description": result.get("description") or None,
        "skills": result.get("skills") or [],
        "seniority": result.get("seniority") or None,
        "geo": result.get("geo") or None,
        "budget_min": result.get("budget_min") or None,
        "budget_max": result.get("budget_max") or None,
    }
