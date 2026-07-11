"""Geo exclusion utilities — generalizable hard filter for any vacancy geo restriction.

Usage:
    from app.utils.geo_filter import is_geo_excluded, build_ukraine_exclude

    job["geo_exclude"] = build_ukraine_exclude()  # convenience preset
    excluded, reason = is_geo_excluded(candidate, job.get("geo_exclude", []))
"""
from __future__ import annotations

import re
from typing import Optional


# ---------------------------------------------------------------------------
# Presets for common geo exclusions
# ---------------------------------------------------------------------------

def build_ukraine_exclude() -> list[str]:
    """Return canonical Ukraine exclusion keyword list for the geo_exclude field."""
    return [
        # Country / nationality
        "ukraine", "ukrainian", "україна", "украина", "украинец", "украинка",
        "ukrainians",
        # Cities (Ukrainian / Russian / English spellings)
        "київ", "kyiv", "киев",
        "харків", "харьков", "kharkiv", "kharkov",
        "одеса", "одесса", "odessa", "odesa",
        "дніпро", "дніпр", "dnipro", "днепр", "dnepropetrovsk", "дніпропетровськ",
        "львів", "львов", "lviv",
        "запоріжжя", "запорожье", "zaporizhzhia", "zaporozhye",
        "миколаїв", "николаев", "mykolaiv",
        "херсон", "kherson",
        "полтава", "poltava",
        "вінниця", "винница", "vinnytsia",
        "суми", "sumy",
        "чернігів", "чернигов", "chernihiv",
        "черкаси", "черкассы", "cherkasy",
        "кривий ріг", "кривой рог", "kryvyi rih",
        # Phone prefix
        "+380",
        # Flag
        "🇺🇦",
        # Ukrainian universities (common ones)
        "кпі", "кпи", "нтуу", "нтуу кпі",
        "кну ім", "кну им",
        "нау", "кнутд", "хпі", "хпи", "нту хпі",
        "дну", "харківський політех",
    ]


# ---------------------------------------------------------------------------
# Core detection
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    return text.lower().strip()


def is_geo_excluded(candidate: dict, geo_exclude: list[str]) -> tuple[bool, str]:
    """
    Check if a candidate matches any excluded geography.
    Returns (True, reason_string) if excluded, (False, "") if OK.

    Checks: location, geo_normalized, bio, raw_text, headline, phone.
    """
    if not geo_exclude:
        return False, ""

    # Build a combined text blob from all relevant candidate fields
    fields = [
        candidate.get("location") or "",
        candidate.get("geo_normalized") or "",
        candidate.get("headline") or "",
        candidate.get("bio") or "",
        # raw_text can be long — check first 2000 chars for speed
        (candidate.get("raw_text") or "")[:2000],
    ]
    blob = _normalize(" ".join(f for f in fields if f))

    # Phone check is exact prefix match, not substring (avoid false positive "+38" in "+38012345")
    phone = str(candidate.get("phone") or "").strip()

    for kw in geo_exclude:
        kw_lower = kw.lower()
        if kw_lower.startswith("+"):
            # Phone prefix — check against phone field only
            if phone.startswith(kw_lower):
                return True, f"geo_excluded: phone prefix {kw}"
        elif kw_lower == "🇺🇦":
            # Emoji — check raw blob before lowercasing
            full_blob = " ".join(f for f in fields if f)
            if "🇺🇦" in full_blob:
                return True, "geo_excluded: 🇺🇦 flag in profile"
        else:
            # Word-boundary aware check: avoid "russia" matching in "belarussia"
            # Use simple substring for multi-word phrases, word-boundary for single words
            if " " in kw_lower:
                if kw_lower in blob:
                    return True, f"geo_excluded: '{kw}' found in profile"
            else:
                # word boundary regex
                pattern = r"\b" + re.escape(kw_lower) + r"\b"
                if re.search(pattern, blob):
                    return True, f"geo_excluded: '{kw}' found in profile"

    return False, ""


def geo_exclude_from_str(raw: str) -> list[str]:
    """Parse a comma-separated geo_exclude string from the frontend form."""
    if not raw:
        return []
    return [kw.strip() for kw in raw.split(",") if kw.strip()]


# ---------------------------------------------------------------------------
# Deep check — uses structured educations[] and positions[] from Phase 2
# ---------------------------------------------------------------------------

def _check_text_for_geo(text: str, geo_exclude: list[str]) -> tuple[bool, str]:
    """Inner check: does `text` match any geo_exclude term?"""
    text_lower = text.lower()
    for kw in geo_exclude:
        kw_lower = kw.lower()
        if kw_lower.startswith("+"):
            if kw_lower in text_lower:
                return True, f"geo_excluded: phone/number '{kw}'"
        elif kw_lower == "🇺🇦":
            if "🇺🇦" in text:
                return True, "geo_excluded: 🇺🇦 flag"
        elif " " in kw_lower:
            if kw_lower in text_lower:
                return True, f"geo_excluded: '{kw}'"
        else:
            if re.search(r"\b" + re.escape(kw_lower) + r"\b", text_lower):
                return True, f"geo_excluded: '{kw}'"
    return False, ""


def is_geo_excluded_deep(candidate: dict, geo_exclude: list[str]) -> tuple[bool, str]:
    """
    Full historical geo check using structured educations[] and positions[]
    from Phase 2 deep scraping.

    Catches:
    - Studied at a Ukrainian university (schoolName / school location)
    - Worked in a Ukrainian city at any point in career (locationName)
    - Current location matches (falls back to shallow check)

    Returns (True, reason) if ANY historical match found.
    """
    if not geo_exclude:
        return False, ""

    # --- 1. Check structured education history ---
    for edu in candidate.get("educations") or []:
        school   = edu.get("school") or ""
        field    = edu.get("field") or ""
        edu_loc  = edu.get("location") or ""
        edu_text = f"{school} {field} {edu_loc}"
        hit, reason = _check_text_for_geo(edu_text, geo_exclude)
        if hit:
            return True, f"geo_excluded (education): {school} — {reason}"

    # --- 2. Check structured position history ---
    for pos in candidate.get("positions") or []:
        pos_loc     = pos.get("location") or ""
        pos_company = pos.get("company") or ""
        pos_desc    = pos.get("desc") or ""
        pos_text    = f"{pos_loc} {pos_company} {pos_desc}"
        hit, reason = _check_text_for_geo(pos_text, geo_exclude)
        if hit:
            title = pos.get("title") or "unknown role"
            return True, f"geo_excluded (position '{title}'): {pos_loc} — {reason}"

    # --- 3. Fall back to surface check (current location, bio, headline) ---
    return is_geo_excluded(candidate, geo_exclude)
