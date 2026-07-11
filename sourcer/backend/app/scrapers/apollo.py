"""Apollo.io people search scraper.

Docs: https://apolloio.github.io/apollo-api-docs/?shell#mixed-people-search
Rate limit: 50 req/min on free, 200/min on paid plans.
"""
from __future__ import annotations

import time
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.utils.text import detect_open_to_work, extract_contacts

log = get_logger(__name__)

_BASE = "https://api.apollo.io/api/v1"
_SEARCH_ENDPOINT = f"{_BASE}/mixed_people/search"


def _headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": settings.apollo_api_key or "",
    }


def _normalize_person(p: dict[str, Any]) -> dict[str, Any]:
    """Map Apollo person object → our candidate schema."""
    name = p.get("name") or ""
    first = p.get("first_name") or ""
    last = p.get("last_name") or ""
    headline = p.get("title") or p.get("headline") or ""
    location = p.get("city") or ""
    if p.get("state"):
        location = f"{location}, {p['state']}" if location else p["state"]
    if p.get("country"):
        location = f"{location}, {p['country']}" if location else p["country"]

    org = p.get("organization") or {}
    org_name = org.get("name") or (p.get("employment_history") or [{}])[0].get("organization_name") or ""

    # Build bio from available fields
    bio_parts = [headline]
    if org_name:
        bio_parts.append(f"at {org_name}")
    for emp in (p.get("employment_history") or [])[:3]:
        title_part = emp.get("title") or ""
        org_part = emp.get("organization_name") or ""
        if title_part or org_part:
            bio_parts.append(f"{title_part} @ {org_part}".strip(" @"))
    bio = "\n".join(b for b in bio_parts if b)

    skills_raw = p.get("keywords") or []
    skills = skills_raw if isinstance(skills_raw, list) else [skills_raw]

    linkedin_url = p.get("linkedin_url") or ""

    # OTW detection from headline / bio
    blob = f"{name} {headline} {bio}"
    otw, otw_sig = detect_open_to_work(blob)

    return {
        "source": "apollo",
        "source_id": p.get("id") or "",
        "full_name": name or f"{first} {last}".strip() or None,
        "first_name": first or None,
        "last_name": last or None,
        "username": None,
        "headline": headline or None,
        "bio": bio or None,
        "raw_text": bio,
        "location": location or None,
        "skills": skills,
        "email": p.get("email") or None,
        "phone": (p.get("phone_numbers") or [{}])[0].get("sanitized_number") or None,
        "linkedin_url": linkedin_url or None,
        "telegram_url": None,
        "open_to_work": otw,
        "otw_signal": otw_sig,
        "facebook_signal": any(
            kw.lower() in (headline + " " + bio).lower()
            for kw in ("facebook", "fb ads", "meta ads", "facebook ads")
        ),
        "raw": p,
    }


def scrape_apollo(
    keywords: str,
    titles: Optional[list[str]] = None,
    geo: Optional[str] = None,
    max_results: int = 50,
) -> list[dict[str, Any]]:
    """
    Search Apollo.io people by keywords/title.

    Args:
        keywords: Free-text search (e.g. "Facebook Media Buyer iGaming")
        titles:   Optional list of exact job titles to filter
        geo:      Optional location filter (city / country name)
        max_results: Max candidates to return (Apollo returns 25 per page)

    Returns list of normalized candidate dicts.
    """
    if not settings.apollo_api_key:
        log.warning("APOLLO_API_KEY not set — skipping Apollo scrape")
        return []

    collected: list[dict[str, Any]] = []
    page = 1
    per_page = min(25, max_results)

    while len(collected) < max_results:
        body: dict[str, Any] = {
            "q_keywords": keywords,
            "page": page,
            "per_page": per_page,
        }
        if titles:
            body["person_titles"] = titles
        if geo:
            body["person_locations"] = [geo]

        try:
            resp = httpx.post(
                _SEARCH_ENDPOINT,
                headers=_headers(),
                json=body,
                timeout=30.0,
            )
            if resp.status_code == 429:
                log.warning("Apollo rate limit — sleeping 60s")
                time.sleep(60)
                continue
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            log.exception("Apollo request failed (page %d): %s", page, exc)
            break

        people = data.get("people") or []
        if not people:
            log.info("Apollo: no more results at page %d", page)
            break

        for p in people:
            collected.append(_normalize_person(p))

        pagination = data.get("pagination") or {}
        total_pages = pagination.get("total_pages") or 1
        log.info(
            "Apollo page %d/%d — %d people (total collected: %d)",
            page, total_pages, len(people), len(collected),
        )

        if page >= total_pages or len(collected) >= max_results:
            break

        page += 1
        time.sleep(0.5)  # polite rate limiting

    log.info("Apollo scrape done: %d candidates", len(collected))
    return collected[:max_results]
