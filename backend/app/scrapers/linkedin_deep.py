"""Phase 2: deep-scrape specific LinkedIn profile URLs via Apify.

Takes the refined list of profile URLs produced in Phase 1 and fetches
the complete profile JSON including educations[], positions[], skills[].

Safe batch size: ≤25 URLs per actor run avoids LinkedIn anti-bot triggers.
The actor is configured via APIFY_PROFILE_ACTOR (default reuses the
harvestapi search actor which also accepts profileUrls input).

If the default actor does not support profileUrls, set:
  APIFY_PROFILE_ACTOR=apify/linkedin-profile-scraper
and it will use startUrls format instead.
"""
from __future__ import annotations

import re
import time
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.utils.text import detect_open_to_work, extract_contacts

log = get_logger(__name__)

APIFY_BASE = "https://api.apify.com/v2"

# Max profiles per single Apify run (LinkedIn anti-bot threshold)
_BATCH_SIZE = 25


def _actor_slug(actor: str) -> str:
    return actor.replace("/", "~")


def _run_actor_deep(profile_urls: list[str], timeout_s: int = 600) -> list[dict[str, Any]]:
    """Run the profile actor on a batch of URLs and return raw items."""
    if not settings.apify_api_key:
        log.warning("APIFY_API_KEY missing — skipping deep scrape")
        return []

    actor = _actor_slug(settings.apify_profile_actor)
    headers = {"Authorization": f"Bearer {settings.apify_api_key}"}

    # Build input — support both actor flavours
    if "harvestapi" in settings.apify_profile_actor:
        payload: dict[str, Any] = {
            "profileUrls": profile_urls,
            "profileScraperMode": "Full",
        }
    else:
        # apify/linkedin-profile-scraper style
        payload = {
            "startUrls": [{"url": u} for u in profile_urls],
        }

    with httpx.Client(timeout=60.0, headers=headers) as client:
        r = client.post(f"{APIFY_BASE}/acts/{actor}/runs", json=payload)
        r.raise_for_status()
        run = r.json().get("data", {})
        run_id = run.get("id")
        dataset_id = run.get("defaultDatasetId")
        if not run_id or not dataset_id:
            log.error("Apify deep run returned no IDs: %s", run)
            return []

        t0 = time.time()
        poll_s = 6.0
        while True:
            time.sleep(poll_s)
            s = client.get(f"{APIFY_BASE}/actor-runs/{run_id}")
            s.raise_for_status()
            status = s.json().get("data", {}).get("status")
            log.info("deep scrape run %s → %s (%d URLs)", run_id, status, len(profile_urls))
            if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                break
            if time.time() - t0 > timeout_s:
                log.warning("deep scrape timed out after %ds", timeout_s)
                break

        d = client.get(
            f"{APIFY_BASE}/datasets/{dataset_id}/items",
            params={"clean": "true", "format": "json"},
        )
        d.raise_for_status()
        return d.json() or []


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _as_str(v: Any) -> Optional[str]:
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


def _extract_educations(raw_edu: list[Any]) -> list[dict[str, str]]:
    """Normalise education array to {school, field, location, start, end}."""
    out = []
    for e in raw_edu or []:
        if not isinstance(e, dict):
            continue
        school = _as_str(e.get("schoolName") or e.get("school") or e.get("name")) or ""
        field  = _as_str(e.get("fieldOfStudy") or e.get("field") or e.get("degree")) or ""
        loc    = _as_str(e.get("location") or e.get("schoolLocation")) or ""
        start  = str(e.get("startedOn") or e.get("startYear") or e.get("start") or "")
        end    = str(e.get("finishedOn") or e.get("endYear") or e.get("end") or "")
        if school:
            out.append({"school": school, "field": field, "location": loc,
                        "start": start, "end": end})
    return out


def _extract_positions(raw_pos: list[Any]) -> list[dict[str, str]]:
    """Normalise positions/experience array to {title, company, location, start, end, desc}."""
    out = []
    for p in raw_pos or []:
        if not isinstance(p, dict):
            continue
        title   = _as_str(p.get("title")) or ""
        company = _as_str(p.get("companyName") or p.get("company")) or ""
        loc     = _as_str(p.get("locationName") or p.get("location") or p.get("geoLocationName")) or ""
        start   = str(p.get("startedOn") or p.get("startYear") or p.get("start") or "")
        end     = str(p.get("finishedOn") or p.get("endYear") or p.get("end") or "current")
        desc    = _as_str(p.get("description") or p.get("desc")) or ""
        if title or company:
            out.append({"title": title, "company": company, "location": loc,
                        "start": start, "end": end, "desc": desc[:500]})
    return out


def _normalize_deep_profile(p: dict[str, Any], original_id: Optional[str] = None) -> dict[str, Any]:
    """Convert a full Apify profile response to our enriched candidate schema."""

    def g(*keys, default=None):
        for k in keys:
            if k in p and p[k] not in (None, ""):
                return p[k]
        return default

    url   = _as_str(g("profileUrl", "linkedinUrl", "url", "publicProfileUrl", "link"))
    name  = _as_str(g("fullName", "name")) or ""
    first = _as_str(g("firstName")) or ""
    last  = _as_str(g("lastName")) or ""
    if not name:
        name = f"{first} {last}".strip() or None

    headline = _as_str(g("headline")) or ""
    bio      = _as_str(g("about", "summary", "description")) or ""
    location = _as_str(g("location", "locationName", "addressWithCountry")) or ""

    # --- Structured history ---
    raw_edu  = g("education", "educations", default=[]) or []
    raw_pos  = g("positions", "experiences", "experience", default=[]) or []
    # also check currentPositions
    current_positions = g("currentPositions", default=[]) or []
    if not raw_pos:
        raw_pos = current_positions

    educations = _extract_educations(raw_edu if isinstance(raw_edu, list) else [])
    positions  = _extract_positions(raw_pos if isinstance(raw_pos, list) else [])

    # --- Skills ---
    skills_raw = g("skills", default=[]) or []
    skills: list[str] = []
    if isinstance(skills_raw, list):
        for s in skills_raw:
            if isinstance(s, str):
                skills.append(s)
            elif isinstance(s, dict):
                sn = s.get("name") or s.get("skill") or s.get("title")
                if sn:
                    skills.append(str(sn))

    # --- Languages ---
    lang_raw = g("languages", default=[]) or []
    languages: list[str] = []
    if isinstance(lang_raw, list):
        for l in lang_raw:
            if isinstance(l, str):
                languages.append(l)
            elif isinstance(l, dict):
                ln = l.get("name") or l.get("language")
                if ln:
                    languages.append(str(ln))

    # --- Build full text blobs (used for scoring + signals) ---
    edu_text = "\n".join(
        f"{e['school']} — {e['field']} {e['location']} {e['start']}–{e['end']}".strip()
        for e in educations
    )
    pos_text = "\n".join(
        f"{pos['title']} @ {pos['company']} | {pos['location']} | {pos['start']}–{pos['end']}\n{pos['desc']}"
        for pos in positions
    )
    full_text = "\n\n".join(filter(None, [bio, pos_text, edu_text]))
    search_text = " ".join(filter(None, [name, headline, full_text, ", ".join(skills)]))

    # --- NLP signals ---
    igaming_match  = bool(_IGAMING_RE.search(search_text))
    facebook_match = bool(_FACEBOOK_RE.search(search_text))

    # --- years_experience: count of positions ---
    years_exp: Optional[float] = None
    if current_positions and isinstance(current_positions, list) and current_positions:
        cp0 = current_positions[0] if isinstance(current_positions[0], dict) else {}
        tenure = cp0.get("tenureAtCompany") or {}
        if isinstance(tenure, dict):
            y = tenure.get("numYears") or 0
            m = tenure.get("numMonths") or 0
            years_exp = round(float(y) + float(m) / 12, 1) if (y or m) else None
    if years_exp is None and positions:
        years_exp = float(len(positions))

    public_id = _as_str(g("publicIdentifier", "username"))
    if not public_id and url and "/in/" in url:
        public_id = url.rsplit("/in/", 1)[-1].rstrip("/")

    contacts = extract_contacts(full_text)
    otw_flag = bool(g("openToWork", "isOpenToWork", "openProfile", default=False))
    otw_text, otw_sig = detect_open_to_work(full_text)

    return {
        "source": "linkedin",
        "source_id": url or public_id,
        "full_name": name or None,
        "first_name": first or None,
        "last_name": last or None,
        "username": public_id,
        "headline": headline or None,
        "bio": full_text[:5000] or None,       # full enriched bio including history
        "raw_text": search_text[:6000],
        "location": location or None,
        "skills": skills,
        "languages": languages,
        "years_experience": years_exp,
        "linkedin_url": url or None,
        "email": contacts["emails"][0] if contacts["emails"] else g("email"),
        "phone": contacts["phones"][0] if contacts["phones"] else None,
        "open_to_work": otw_flag or otw_text,
        "otw_signal": "apify.openToWork" if otw_flag else otw_sig,
        "igaming_signal": igaming_match,
        "facebook_signal": facebook_match,
        "educations": educations,    # structured, used by deep geo filter
        "positions": positions,      # structured, used by deep geo filter + scoring
        "scan_depth": 2,
        "raw": p,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scrape_one_batch(profile_urls: list[str]) -> list[dict[str, Any]]:
    """
    Scrape a single batch of ≤25 profile URLs.
    Returns normalised candidates. Raises on network errors so the caller can log.
    """
    raw = _run_actor_deep(profile_urls)
    results = []
    for item in raw:
        try:
            results.append(_normalize_deep_profile(item))
        except Exception:
            log.exception("normalize_deep_profile failed; keys=%s", list(item.keys())[:10])
    log.info("  scrape_one_batch: %d/%d profiles normalised", len(results), len(raw))
    return results


def scrape_profiles_deep(
    profile_urls: list[str],
    batch_size: int = _BATCH_SIZE,
) -> list[dict[str, Any]]:
    """
    Deep-scrape up to `batch_size` LinkedIn profiles per Apify run.

    Returns normalised candidates with educations[], positions[], full bio.
    Profiles that fail to scrape are silently skipped (Apify returned nothing
    for that URL).

    Safe limit: 25 per run. For 50 profiles → 2 runs, ~10-15 min total.
    """
    if not profile_urls:
        return []

    # Deduplicate and normalise URLs
    clean_urls: list[str] = []
    seen: set[str] = set()
    for u in profile_urls:
        u = u.strip().rstrip("/")
        if not u:
            continue
        key = u.lower()
        if key not in seen:
            seen.add(key)
            clean_urls.append(u)

    log.info("deep scrape: %d unique URLs in %d batch(es)",
             len(clean_urls), -(-len(clean_urls) // batch_size))

    all_results: list[dict[str, Any]] = []

    for i in range(0, len(clean_urls), batch_size):
        batch = clean_urls[i : i + batch_size]
        log.info("deep scrape batch %d/%d (%d URLs)…",
                 i // batch_size + 1, -(-len(clean_urls) // batch_size), len(batch))
        try:
            raw = _run_actor_deep(batch)
        except Exception:
            log.exception("deep scrape batch failed")
            continue

        for item in raw:
            try:
                c = _normalize_deep_profile(item)
                all_results.append(c)
            except Exception:
                log.exception("normalize_deep_profile failed; keys=%s", list(item.keys())[:10])

        log.info("  → %d profiles returned for this batch", len(raw))

        # Polite delay between batches
        if i + batch_size < len(clean_urls):
            log.info("  waiting 30s before next batch…")
            time.sleep(30)

    log.info("deep scrape complete: %d/%d profiles retrieved", len(all_results), len(clean_urls))
    return all_results
