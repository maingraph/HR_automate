"""Apify-based LinkedIn scraper.

Calls the harvestapi/linkedin-profile-search actor with the Gemini-generated
Boolean string and normalizes results into our candidate schema.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Iterable, Optional

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.utils.text import detect_open_to_work, extract_contacts

log = get_logger(__name__)

APIFY_BASE = "https://api.apify.com/v2"


def _trim_boolean(q: str) -> str:
    """Queries are now OR-only by design — just strip whitespace.

    AND operators in LinkedIn queries sent via Apify over-narrow pagination
    and reliably return 0 results. Specificity is achieved via title variants
    in the OR groups instead.
    """
    return q.strip()


def _actor_slug() -> str:
    # Apify endpoints require `~` instead of `/` in actor identifiers
    return settings.apify_linkedin_actor.replace("/", "~")


def _run_actor(
    input_payload: dict[str, Any],
    timeout_s: int = 600,
    poll_s: float = 5.0,
) -> list[dict[str, Any]]:
    if not settings.apify_api_key:
        log.warning("APIFY_API_KEY missing; skipping LinkedIn scrape")
        return []

    actor = _actor_slug()
    headers = {"Authorization": f"Bearer {settings.apify_api_key}"}

    with httpx.Client(timeout=60.0, headers=headers) as client:
        # Start run
        r = client.post(
            f"{APIFY_BASE}/acts/{actor}/runs",
            json=input_payload,
        )
        r.raise_for_status()
        run = r.json().get("data", {})
        run_id = run.get("id")
        dataset_id = run.get("defaultDatasetId")
        if not run_id or not dataset_id:
            log.error("Apify run did not return ids: %s", run)
            return []

        # Poll
        t0 = time.time()
        while True:
            time.sleep(poll_s)
            s = client.get(f"{APIFY_BASE}/actor-runs/{run_id}")
            s.raise_for_status()
            status = s.json().get("data", {}).get("status")
            if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                log.info("apify run %s → %s", run_id, status)
                break
            if time.time() - t0 > timeout_s:
                log.warning("apify run %s timed out client-side", run_id)
                break

        # Fetch dataset items
        d = client.get(
            f"{APIFY_BASE}/datasets/{dataset_id}/items",
            params={"clean": "true", "format": "json"},
        )
        d.raise_for_status()
        return d.json() or []


def _as_str(v: Any) -> Optional[str]:
    """Best-effort stringify that handles the common dict shapes returned by harvestapi."""
    if v is None or v == "":
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        for k in ("linkedinText", "text", "name", "title", "label", "value"):
            if v.get(k):
                return str(v[k])
        return None
    if isinstance(v, list):
        parts = [_as_str(x) for x in v]
        return ", ".join(p for p in parts if p) or None
    return str(v)


_IGAMING_RE = re.compile(
    r"\b(igaming|i-gaming|gambling|casino|betting|sportsbook|slots|poker|affiliate|арбитраж|гемблинг|беттинг|казино)\b",
    re.IGNORECASE,
)
_FACEBOOK_RE = re.compile(
    r"\b(facebook|fb ads|fb buyer|meta ads|facebook ads|facebook media|фейсбук|фб|fb)\b",
    re.IGNORECASE,
)
_BUDGET_RE = re.compile(
    r"(\$[\d,]+[km]?\+?(?:/mo(?:nth)?)?|\d+[km]\+?\s*(?:usd|budget|spend|спенд))",
    re.IGNORECASE,
)
_OVERQUALIFIED_RE = re.compile(
    r"\b(head of|chief|cmo|ceo|cto|vp|vice president|директор|руководитель отдела)\b",
    re.IGNORECASE,
)


def _extract_experience_text(positions: list[Any]) -> str:
    """Flatten all positions into a single text blob for NLP."""
    parts = []
    for pos in positions or []:
        if not isinstance(pos, dict):
            continue
        t = _as_str(pos.get("title")) or ""
        c = _as_str(pos.get("companyName")) or ""
        desc = _as_str(pos.get("description")) or ""
        if t or c:
            parts.append(f"{t} @ {c}: {desc}".strip(" @:"))
    return "\n".join(parts)


def _normalize_profile(p: dict[str, Any]) -> dict[str, Any]:
    """Map a harvestapi-style profile record to our schema.

    Full mode keys (in addition to Short):
      about, skills[{name}], positions/experiences[{title, companyName, description,
      startedOn, finishedOn}], education, certifications
    """

    def g(*keys, default=None):
        for k in keys:
            if k in p and p[k] not in (None, ""):
                return p[k]
        return default

    url = _as_str(g("profileUrl", "linkedinUrl", "url", "publicProfileUrl", "link"))

    current_positions = g("currentPositions", default=[]) or []
    all_positions = g("positions", "experiences", "experience", default=[]) or []
    if not all_positions:
        all_positions = current_positions

    current_title: Optional[str] = None
    current_company: Optional[str] = None
    if isinstance(current_positions, list) and current_positions:
        cp = current_positions[0] if isinstance(current_positions[0], dict) else {}
        current_title = _as_str(cp.get("title"))
        current_company = _as_str(cp.get("companyName"))

    headline = _as_str(g("headline")) or (
        f"{current_title} @ {current_company}"
        if current_title and current_company
        else current_title
    )
    bio = _as_str(g("about", "summary", "description")) or ""
    name = _as_str(g("fullName", "name")) or " ".join(
        [x for x in [_as_str(g("firstName")), _as_str(g("lastName"))] if x]
    ).strip() or None
    location = _as_str(g("location", "locationName", "addressWithCountry"))

    skills_field = g("skills", default=[]) or []
    skills: list[str] = []
    if isinstance(skills_field, list):
        for s in skills_field:
            if isinstance(s, str):
                skills.append(s)
            elif isinstance(s, dict):
                sn = s.get("name") or s.get("skill") or s.get("title")
                if sn:
                    skills.append(str(sn))

    # Experience: compute years from current position tenure
    years_exp: Optional[float] = None
    if isinstance(current_positions, list) and current_positions:
        cp0 = current_positions[0] if isinstance(current_positions[0], dict) else {}
        tenure_co = cp0.get("tenureAtCompany") or {}
        if isinstance(tenure_co, dict):
            y = tenure_co.get("numYears") or 0
            m = tenure_co.get("numMonths") or 0
            years_exp = round(float(y) + float(m) / 12, 1) if (y or m) else None
    if years_exp is None and isinstance(all_positions, list) and all_positions:
        years_exp = float(len(all_positions))

    # Build rich text blob for scoring (includes experience history)
    experience_text = _extract_experience_text(all_positions)

    public_id = _as_str(g("publicIdentifier", "username"))
    if not public_id and url and "/in/" in url:
        public_id = url.rsplit("/in/", 1)[-1].rstrip("/")

    # Enrich bio with experience history for scoring context
    full_text = "\n\n".join(filter(None, [bio, experience_text]))

    # NLP enrichment signals
    search_text = full_text + " " + (headline or "") + " " + ", ".join(skills)
    igaming_match = bool(_IGAMING_RE.search(search_text))
    facebook_match = bool(_FACEBOOK_RE.search(search_text))
    budget_match = _BUDGET_RE.search(full_text)
    overqualified = bool(_OVERQUALIFIED_RE.search(current_title or ""))

    text_blob = "\n".join(
        filter(
            None,
            [
                name,
                headline,
                bio,
                current_company,
                location,
                ", ".join(skills) if skills else None,
            ],
        )
    )
    contacts = extract_contacts(text_blob)
    otw_flag_field = bool(g("openToWork", "isOpenToWork", "openProfile", default=False))
    otw_text, otw_sig = detect_open_to_work(text_blob)
    otw = otw_flag_field or otw_text

    return {
        "source": "linkedin",
        "source_id": url or public_id,
        "full_name": name,
        "first_name": _as_str(g("firstName")),
        "last_name": _as_str(g("lastName")),
        "username": public_id,
        "headline": headline,
        "bio": full_text[:4000] if full_text else None,   # includes experience history
        "raw_text": text_blob[:6000],
        "location": location,
        "skills": skills,
        "years_experience": years_exp,
        "linkedin_url": url,
        "email": contacts["emails"][0] if contacts["emails"] else None,
        "phone": contacts["phones"][0] if contacts["phones"] else None,
        "open_to_work": otw,
        "otw_signal": "apify.openToWork" if otw_flag_field else otw_sig,
        # Pre-computed NLP signals (used by scoring + hard filter)
        "igaming_signal": igaming_match,
        "facebook_signal": facebook_match,
        "budget_signal": budget_match.group(0) if budget_match else None,
        "overqualified_signal": overqualified,
        "raw": p,
    }


def _run_single_query(query: str, max_results: int, mode: str) -> list[dict[str, Any]]:
    """Run one Apify query and return normalised candidates."""
    query = _trim_boolean(query)
    if not query.strip():
        return []
    payload: dict[str, Any] = {
        "searchQuery": query[:300],
        "maxItems": max_results,
        # Full mode gives bio, experience history, skills — critical for scoring
        "profileScraperMode": mode,
    }
    try:
        raw = _run_actor(payload)
    except httpx.HTTPStatusError as e:
        log.error("Apify HTTP error %s: %s", e.response.status_code, e.response.text[:300])
        return []
    except Exception:
        log.exception("Apify run failed for query: %s", query[:80])
        return []

    out = []
    for item in raw:
        try:
            out.append(_normalize_profile(item))
        except Exception:
            log.exception("normalize_profile failed; keys=%s", list(item.keys())[:10])
    return out


def scrape_linkedin(
    boolean_query: str,
    *,
    queries: Optional[list[str]] = None,
    geo: Optional[str] = None,
    max_results: int = 100,
    profile_mode: str = "Full",
    extra_inputs: Optional[dict[str, Any]] = None,
) -> list[dict[str, Any]]:
    """Run one or more Apify queries, deduplicate by LinkedIn URL, and return candidates.

    - queries: list of LI Boolean strings (from generate_plan). Falls back to boolean_query.
    - profile_mode: "Full" gets bio+experience+skills (recommended); "Short" is faster/cheaper.
    - max_results: per query. Total ≤ len(queries) × max_results before dedup.
    """
    all_queries = list(queries or [])
    if not all_queries and boolean_query:
        all_queries = [boolean_query]
    if not all_queries:
        log.warning("No LinkedIn queries provided")
        return []

    seen_urls: set[str] = set()
    all_candidates: list[dict[str, Any]] = []

    for i, q in enumerate(all_queries):
        log.info("LinkedIn query %d/%d: %s", i + 1, len(all_queries), q[:80])
        batch = _run_single_query(q, max_results=max_results, mode=profile_mode)
        new = 0
        for c in batch:
            url = (c.get("linkedin_url") or "").lower().rstrip("/")
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            all_candidates.append(c)
            new += 1
        log.info("  → %d new (total %d)", new, len(all_candidates))

    log.info("linkedin/apify total: %d unique candidates from %d queries", len(all_candidates), len(all_queries))
    return all_candidates


PB_BASE = "https://api.phantombuster.com/api/v2"


def _build_sales_nav_url(keywords: str) -> str:
    """Build a Sales Navigator people-search URL from a keyword string."""
    import urllib.parse
    # Strip Boolean operators — Sales Nav URL uses plain keywords
    plain = re.sub(r'\b(AND|OR|NOT)\b', ' ', keywords)
    plain = re.sub(r'["\(\)]', ' ', plain)
    plain = re.sub(r'\s+', ' ', plain).strip()
    encoded = urllib.parse.quote(plain)
    return f"https://www.linkedin.com/sales/search/people?query=(keywords:{encoded})"


def _pb_headers() -> dict:
    return {"X-Phantombuster-Key": settings.phantombuster_api_key}


def _pb_launch(search_url: str, max_results: int) -> str | None:
    """Launch PhantomBuster Sales Nav agent and return containerId."""
    with httpx.Client(timeout=30.0) as c:
        r = c.post(
            f"{PB_BASE}/agents/launch",
            json={
                "id": settings.phantombuster_agent_id,
                "argument": {
                    "searches": search_url,          # string, not array
                    "sessionCookie": settings.linkedin_li_at,  # required when overriding args via API
                    "numberOfResultsPerSearch": max_results,
                    "csvName": "sourcer_result",
                },
            },
            headers=_pb_headers(),
        )
        r.raise_for_status()
        return r.json().get("containerId")


def _pb_poll(timeout_s: int = 300, poll_s: float = 8.0) -> list[dict]:
    """Poll until agent finishes, return parsed results."""
    t0 = time.time()
    with httpx.Client(timeout=30.0) as c:
        while True:
            time.sleep(poll_s)
            r = c.get(
                f"{PB_BASE}/agents/fetch-output",
                params={"id": settings.phantombuster_agent_id},
                headers=_pb_headers(),
            )
            r.raise_for_status()
            data = r.json()
            status = data.get("status", "")
            log.info("phantombuster status: %s", status)

            if status in ("finished", "error", "stopped"):
                if status == "error":
                    log.error("phantombuster error: %s", data.get("output", "")[-300:])
                    return []

                # Try resultObject first (inline JSON)
                result_obj = data.get("resultObject")
                if result_obj:
                    try:
                        return json.loads(result_obj) if isinstance(result_obj, str) else result_obj
                    except Exception:
                        pass

                # Fall back to downloading the output file
                result_url = data.get("resultUrl") or data.get("csvUrl")
                if result_url:
                    resp = c.get(result_url)
                    resp.raise_for_status()
                    ct = resp.headers.get("content-type", "")
                    if "json" in ct:
                        return resp.json()
                    # CSV fallback
                    import csv, io
                    reader = csv.DictReader(io.StringIO(resp.text))
                    return list(reader)
                return []

            if time.time() - t0 > timeout_s:
                log.warning("phantombuster timed out after %ds", timeout_s)
                return []


def _normalize_pb_profile(p: dict) -> dict:
    """Map PhantomBuster Sales Nav result to our candidate schema."""
    url = p.get("linkedInProfileUrl") or p.get("profileUrl") or p.get("linkedinUrl") or ""
    name = p.get("fullName") or (
        " ".join(filter(None, [p.get("firstName"), p.get("lastName")])) or None
    )
    headline = p.get("title") or p.get("headline") or p.get("currentPosition") or ""
    location = p.get("location") or p.get("geoRegion") or ""
    company = p.get("currentCompany") or p.get("company") or ""
    summary = p.get("summary") or p.get("description") or ""
    full_text = "\n".join(filter(None, [headline, company, summary]))

    igaming_match = bool(_IGAMING_RE.search(full_text))
    facebook_match = bool(_FACEBOOK_RE.search(full_text))
    overqualified = bool(_OVERQUALIFIED_RE.search(headline))
    otw = bool(p.get("openLink") or p.get("openToWork"))

    public_id = url.rsplit("/in/", 1)[-1].rstrip("/") if "/in/" in url else None

    return {
        "source": "linkedin",
        "source_id": url or name,
        "full_name": name,
        "username": public_id,
        "headline": headline,
        "bio": full_text[:4000],
        "raw_text": full_text[:6000],
        "location": location,
        "skills": [],
        "years_experience": None,
        "linkedin_url": url or None,
        "email": p.get("email") or None,
        "phone": p.get("phone") or None,
        "open_to_work": otw,
        "otw_signal": "pb.openLink" if otw else None,
        "igaming_signal": igaming_match,
        "facebook_signal": facebook_match,
        "budget_signal": None,
        "overqualified_signal": overqualified,
        "raw": p,
    }


def scrape_sales_navigator(
    queries: list[str],
    max_results: int = 100,
) -> list[dict[str, Any]]:
    """Scrape LinkedIn Sales Navigator via PhantomBuster.

    Runs one phantom launch per query, deduplicates by LinkedIn URL.
    Falls back silently to [] if PhantomBuster is not configured.
    """
    if not settings.phantombuster_api_key or not settings.phantombuster_agent_id:
        log.info("PhantomBuster not configured — skipping Sales Navigator scrape")
        return []

    seen_urls: set[str] = set()
    all_candidates: list[dict[str, Any]] = []

    for i, q in enumerate(queries):
        search_url = _build_sales_nav_url(q)
        log.info("PhantomBuster Sales Nav query %d/%d: %s", i + 1, len(queries), search_url)
        try:
            container_id = _pb_launch(search_url, max_results)
            if not container_id:
                log.warning("PhantomBuster launch returned no containerId")
                continue
            log.info("PhantomBuster container: %s — polling…", container_id)
            raw = _pb_poll(timeout_s=300)
        except Exception:
            log.exception("PhantomBuster query %d failed", i + 1)
            continue

        new = 0
        for item in raw:
            try:
                c = _normalize_pb_profile(item)
            except Exception:
                log.exception("normalize_pb_profile failed")
                continue
            url = (c.get("linkedin_url") or "").lower().rstrip("/")
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            all_candidates.append(c)
            new += 1
        log.info("  → %d new profiles (total %d)", new, len(all_candidates))

    log.info("Sales Navigator total: %d unique candidates from %d queries", len(all_candidates), len(queries))
    return all_candidates
