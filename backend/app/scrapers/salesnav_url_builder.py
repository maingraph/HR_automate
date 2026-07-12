"""Sales Navigator URL builder — generates search URLs from job parameters.

LinkedIn Sales Navigator uses a query-string format with nested JSON-like structures.
URL structure (as of 2024-2025):
  https://www.linkedin.com/sales/search/people?query=(filters:List(...))

Common filter keys (verified May 2025):
- keywords: free-text search
- geoUrn: location (format: urn:li:region:XXXXX or urn:li:country:XXXXX)
- currentTitle: job title keywords
- currentCompany: company name
- industry: industry URN
- seniority: seniority level URN
- yearsOfExperience: experience range

LinkedIn changes filter names/structure periodically. This builder uses the most
stable patterns and includes fallbacks.

To verify current structure:
1. Open https://www.linkedin.com/sales/search/people in Chrome
2. Apply filters manually
3. Copy URL from address bar
4. Compare with this builder's output
5. Update filter keys if LinkedIn changed them
"""
from __future__ import annotations

import json
import urllib.parse
from typing import Any, Optional

from app.core.logging import get_logger

log = get_logger(__name__)

# LinkedIn Sales Nav filter structure (verified 2025-05)
# These keys are relatively stable but may change
FILTER_KEYS = {
    "keywords": "keywords",
    "geoUrn": "geoUrn",
    "currentTitle": "currentTitle",
    "currentCompany": "currentCompany",
    "industry": "industry",
    "seniority": "seniority",
    "yearsOfExperience": "yearsOfExperience",
    "currentFunction": "currentFunction",
}

# Seniority level mappings (LinkedIn URNs)
# Format: urn:li:fs_salesSeniorityLevel:X
SENIORITY_URNS = {
    "entry": "1",      # Entry level
    "associate": "2",  # Associate
    "mid-senior": "3", # Mid-Senior level
    "director": "4",   # Director
    "executive": "5",  # Executive
    "senior": "3",     # Alias for mid-senior
    "lead": "3",       # Alias for mid-senior
    "manager": "3",    # Alias for mid-senior
    "vp": "4",         # Alias for director
    "c-level": "5",    # Alias for executive
    "cxo": "5",        # Alias for executive
}

# Common location URNs (partial list — full list has 1000s)
# Format: urn:li:region:XXXXX or urn:li:country:XXXXX
LOCATION_URNS = {
    # Countries
    "united states": "103644278",
    "usa": "103644278",
    "us": "103644278",
    "canada": "101174742",
    "united kingdom": "101165590",
    "uk": "101165590",
    "germany": "101282230",
    "france": "105015875",
    "spain": "105646813",
    "italy": "103350119",
    "netherlands": "102890719",
    "poland": "105072130",
    "ukraine": "102264497",
    "russia": "101728296",
    "belarus": "101705918",

    # Major cities/regions
    "san francisco bay area": "90000084",
    "new york": "90000070",
    "london": "90009496",
    "berlin": "90010383",
    "paris": "90009550",
    "amsterdam": "90009706",
    "warsaw": "90009794",
    "kyiv": "106967730",
    "moscow": "101405725",
    "minsk": "104937681",
}


def build_sales_nav_url(
    *,
    keywords: Optional[str] = None,
    title: Optional[str] = None,
    location: Optional[str] = None,
    seniority: Optional[str] = None,
    company: Optional[str] = None,
    years_experience: Optional[tuple[int, int]] = None,
    skills: Optional[list[str]] = None,
) -> str:
    """Build LinkedIn Sales Navigator search URL from job parameters.

    Args:
        keywords: Free-text search (combines with title/skills if provided)
        title: Job title (e.g., "React Developer", "Product Manager")
        location: Location string (e.g., "San Francisco", "United States", "Remote")
        seniority: Seniority level (entry/associate/mid-senior/director/executive)
        company: Current company name
        years_experience: Tuple of (min, max) years
        skills: List of skill keywords

    Returns:
        Full Sales Navigator search URL

    Example:
        >>> build_sales_nav_url(
        ...     title="React Developer",
        ...     location="San Francisco Bay Area",
        ...     seniority="mid-senior",
        ...     years_experience=(3, 7)
        ... )
        'https://www.linkedin.com/sales/search/people?query=(filters:List(...))...'
    """
    filters: list[dict[str, Any]] = []

    # Build keywords from multiple sources
    keyword_parts = []
    if keywords:
        keyword_parts.append(keywords)
    if title:
        keyword_parts.append(title)
    if skills:
        keyword_parts.extend(skills[:3])  # Top 3 skills only

    if keyword_parts:
        combined_keywords = " ".join(keyword_parts)
        filters.append({
            "type": FILTER_KEYS["keywords"],
            "values": [combined_keywords]
        })

    # Current title (separate from keywords for better targeting)
    if title:
        filters.append({
            "type": FILTER_KEYS["currentTitle"],
            "values": [title]
        })

    # Location (convert to URN if possible)
    if location:
        location_urn = _resolve_location_urn(location)
        if location_urn:
            filters.append({
                "type": FILTER_KEYS["geoUrn"],
                "values": [location_urn]
            })
        else:
            # Fallback: add to keywords
            log.warning(f"Location '{location}' not in URN map, adding to keywords")
            if filters and filters[0]["type"] == FILTER_KEYS["keywords"]:
                filters[0]["values"][0] += f" {location}"
            else:
                filters.insert(0, {
                    "type": FILTER_KEYS["keywords"],
                    "values": [location]
                })

    # Seniority
    if seniority:
        seniority_urn = _resolve_seniority_urn(seniority)
        if seniority_urn:
            filters.append({
                "type": FILTER_KEYS["seniority"],
                "values": [f"urn:li:fs_salesSeniorityLevel:{seniority_urn}"]
            })

    # Company
    if company:
        filters.append({
            "type": FILTER_KEYS["currentCompany"],
            "values": [company]
        })

    # Years of experience
    if years_experience:
        min_years, max_years = years_experience
        # LinkedIn uses ranges: 1, 2-5, 6-10, 11+
        # Map to closest range
        if max_years <= 1:
            range_key = "1"
        elif max_years <= 5:
            range_key = "2"
        elif max_years <= 10:
            range_key = "3"
        else:
            range_key = "4"

        filters.append({
            "type": FILTER_KEYS["yearsOfExperience"],
            "values": [range_key]
        })

    # Build query structure
    query = {
        "filters": filters
    }

    # Encode as URL
    query_str = json.dumps(query, separators=(',', ':'))
    encoded = urllib.parse.quote(query_str)

    url = f"https://www.linkedin.com/sales/search/people?query={encoded}"

    log.info(f"Built Sales Nav URL with {len(filters)} filters")
    log.debug(f"Filters: {[f['type'] for f in filters]}")

    return url


def _resolve_location_urn(location: str) -> Optional[str]:
    """Resolve location string to LinkedIn URN.

    Returns URN string (e.g., "103644278" for US) or None if not found.
    """
    location_lower = location.lower().strip()

    # Direct match
    if location_lower in LOCATION_URNS:
        return LOCATION_URNS[location_lower]

    # Fuzzy match (contains)
    for key, urn in LOCATION_URNS.items():
        if key in location_lower or location_lower in key:
            log.debug(f"Fuzzy matched location '{location}' → '{key}' (URN: {urn})")
            return urn

    return None


def _resolve_seniority_urn(seniority: str) -> Optional[str]:
    """Resolve seniority string to LinkedIn URN suffix.

    Returns URN suffix (e.g., "3" for mid-senior) or None if not found.
    """
    seniority_lower = seniority.lower().strip()

    # Direct match
    if seniority_lower in SENIORITY_URNS:
        return SENIORITY_URNS[seniority_lower]

    # Fuzzy match
    for key, urn in SENIORITY_URNS.items():
        if key in seniority_lower or seniority_lower in key:
            log.debug(f"Fuzzy matched seniority '{seniority}' → '{key}' (URN: {urn})")
            return urn

    return None


def parse_sales_nav_url(url: str) -> dict[str, Any]:
    """Parse Sales Navigator URL back into filter parameters.

    Useful for debugging and verifying URL structure.

    Args:
        url: Sales Navigator search URL

    Returns:
        Dict of extracted filters
    """
    try:
        parsed = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed.query)

        if "query" not in query_params:
            return {}

        query_str = query_params["query"][0]
        query_obj = json.loads(query_str)

        filters = query_obj.get("filters", [])

        result = {}
        for f in filters:
            filter_type = f.get("type")
            values = f.get("values", [])
            result[filter_type] = values

        return result
    except Exception as e:
        log.error(f"Failed to parse Sales Nav URL: {e}")
        return {}


# Test/validation helper
def validate_url_structure(url: str) -> bool:
    """Validate that a Sales Nav URL has the expected structure.

    Returns True if URL looks valid, False otherwise.
    """
    try:
        if not url.startswith("https://www.linkedin.com/sales/search/people"):
            return False

        parsed = parse_sales_nav_url(url)
        return len(parsed) > 0
    except Exception:
        return False
