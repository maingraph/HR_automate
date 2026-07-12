"""Parse uploaded Excel/CSV files of candidates into our schema.

Supports column names from:
  - PhantomBuster Sales Nav Export  (linkedInProfileUrl, fullName, geoRegion, …)
  - Apify LinkedIn actor output     (profileUrl, headline, about, …)
  - Sales Navigator CSV export      (Name, Title, Company, LinkedIn URL, …)
  - Manual/generic XLSX             (any reasonable column names)

Falls back to VALUE-BASED detection when column names don't match —
if a column contains linkedin.com/in/ URLs it's treated as linkedin_url
even if it's called "profile_link" or "contact".
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from app.core.logging import get_logger
from app.utils.text import detect_open_to_work, extract_contacts

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Column alias table — lowercase → canonical field name
# Covers PhantomBuster, Apify, SalesNav CSV, and common manual formats
# ---------------------------------------------------------------------------
COLUMN_ALIASES: dict[str, str] = {
    # ── full_name ──────────────────────────────────────────
    "full name":            "full_name",
    "full_name":            "full_name",
    "fullname":             "full_name",
    "fullname_":            "full_name",
    "name":                 "full_name",
    "candidate":            "full_name",
    "фио":                  "full_name",
    "имя и фамилия":        "full_name",

    # ── first_name ─────────────────────────────────────────
    "first name":           "first_name",
    "first_name":           "first_name",
    "firstname":            "first_name",
    "имя":                  "first_name",

    # ── last_name ──────────────────────────────────────────
    "last name":            "last_name",
    "last_name":            "last_name",
    "lastname":             "last_name",
    "фамилия":              "last_name",

    # ── email ──────────────────────────────────────────────
    "email":                "email",
    "e-mail":               "email",
    "email address":        "email",
    "почта":                "email",
    "mail":                 "email",

    # ── phone ──────────────────────────────────────────────
    "phone":                "phone",
    "phone number":         "phone",
    "phonenumber":          "phone",
    "tel":                  "phone",
    "telephone":            "phone",
    "телефон":              "phone",
    "mobile":               "phone",

    # ── linkedin_url — PhantomBuster & SalesNav variations ─
    "linkedin":             "linkedin_url",
    "linkedin_url":         "linkedin_url",
    "linkedinurl":          "linkedin_url",
    "linkedin url":         "linkedin_url",
    "linkedin profile":     "linkedin_url",
    "linkedin profile url": "linkedin_url",
    "linked in profile url":"linkedin_url",   # PhantomBuster SalesNav export (spaces)
    "linkedinprofileurl":   "linkedin_url",   # PhantomBuster exact key
    "profileurl":           "linkedin_url",   # PhantomBuster alt key
    "profile link":         "linkedin_url",
    "li":                   "linkedin_url",
    "li_url":               "linkedin_url",
    "public profile url":   "linkedin_url",
    "publicprofileurl":     "linkedin_url",
    # NOTE: "profile url" intentionally omitted — it matches Sales Nav
    # lead URLs (linkedin.com/sales/lead/…) which are NOT profile URLs.
    # Value-based detection will find the real linkedin.com/in/ column instead.

    # ── telegram_url ───────────────────────────────────────
    "telegram":             "telegram_url",
    "telegram_url":         "telegram_url",
    "tg":                   "telegram_url",
    "tg_url":               "telegram_url",
    "telegram url":         "telegram_url",
    "telegram handle":      "telegram_url",

    # ── headline / title ───────────────────────────────────
    "title":                "headline",
    "headline":             "headline",
    "job title":            "headline",
    "jobtitle":             "headline",
    "position":             "headline",
    "current position":     "headline",
    "currentposition":      "headline",        # PhantomBuster
    "job":                  "headline",
    "role":                 "headline",
    "должность":            "headline",

    # ── bio / summary ──────────────────────────────────────
    "bio":                  "bio",
    "about":                "bio",
    "summary":              "bio",             # PhantomBuster / SalesNav
    "description":          "bio",
    "title description":    "bio",             # SalesNav export: current-role description
    "опыт":                 "bio",
    "описание":             "bio",
    "о себе":               "bio",

    # ── location ───────────────────────────────────────────
    "location":             "location",
    "city":                 "location",
    "country":              "location",
    "geolocation":          "location",
    "гео":                  "location",
    "город":                "location",
    "georegion":            "location",        # PhantomBuster
    "geo region":           "location",
    "region":               "location",
    "area":                 "location",
    "address":              "location",

    # ── username / handle ──────────────────────────────────
    "username":             "username",
    "handle":               "username",
    "ник":                  "username",
    "publicidentifier":     "username",        # Apify

    # ── skills ─────────────────────────────────────────────
    "skills":               "skills",
    "tech":                 "skills",
    "technologies":         "skills",
    "навыки":               "skills",
    "keywords":             "skills",

    # ── company (used in bio blob) ─────────────────────────
    "company":              "company",
    "company name":         "company",
    "companyname":          "company",         # PhantomBuster
    "current company":      "company",
    "currentcompany":       "company",
    "employer":             "company",
    "компания":             "company",
}

# Regex patterns for value-based detection
_LI_URL_RE   = re.compile(r"linkedin\.com/in/", re.IGNORECASE)
_TG_URL_RE   = re.compile(r"(t\.me/|telegram\.me/|^@)", re.IGNORECASE)
_EMAIL_RE    = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_PHONE_RE    = re.compile(r"^\+?[\d\s\-\(\)]{7,15}$")


def _normalise_col(name: str) -> str:
    return name.strip().lower().replace("_", " ").replace("-", " ")


def _detect_columns(df: pd.DataFrame) -> dict[str, str]:
    """
    Build a mapping {df_column → canonical_field}.
    Step 1: name-based lookup in COLUMN_ALIASES, with value validation for URL fields.
    Step 2: value-based regex scan for any unmapped column.

    Value validation for URL targets prevents a "Profile Url" column that contains
    Sales Navigator URLs (linkedin.com/sales/lead/…) from blocking the real
    "Linked In Profile Url" column (linkedin.com/in/…).
    """
    mapping: dict[str, str] = {}
    used_targets: set[str] = set()

    # For these targets, verify ≥30% of sample values match the expected pattern
    # before claiming the target in the name-based pass.
    _URL_VALIDATORS: dict[str, re.Pattern] = {
        "linkedin_url": _LI_URL_RE,   # must contain linkedin.com/in/
        "telegram_url": _TG_URL_RE,   # must contain t.me/ or start with @
    }

    # Step 1 — name matching
    for col in df.columns:
        key = _normalise_col(str(col))
        target = COLUMN_ALIASES.get(key)
        if not target or target in used_targets:
            continue
        # For URL-typed targets, validate the actual values look right.
        # This stops "Profile Url" (Sales Nav format) from blocking
        # "Linked In Profile Url" (real linkedin.com/in/ URLs).
        if target in _URL_VALIDATORS:
            pattern = _URL_VALIDATORS[target]
            samples = [str(v) for v in df[col].dropna().head(10)
                       if str(v).strip() not in ("", "nan", "None")]
            if samples and sum(1 for v in samples if pattern.search(v)) < max(1, len(samples) * 0.3):
                log.debug("file_ingest: name-matched '%s' → %s but values don't match pattern — skipping", col, target)
                continue
        mapping[col] = target
        used_targets.add(target)

    # Step 2 — value-based for unmapped columns (first 10 non-null values)
    for col in df.columns:
        if col in mapping:
            continue
        samples = [str(v) for v in df[col].dropna().head(10) if str(v).strip()]
        if not samples:
            continue

        # Check majority vote: if ≥60% of samples match a pattern, use it
        li_hits  = sum(1 for v in samples if _LI_URL_RE.search(v))
        tg_hits  = sum(1 for v in samples if _TG_URL_RE.search(v))
        em_hits  = sum(1 for v in samples if _EMAIL_RE.match(v.strip()))

        thresh = max(1, len(samples) * 0.6)
        if li_hits >= thresh and "linkedin_url" not in used_targets:
            mapping[col] = "linkedin_url"
            used_targets.add("linkedin_url")
            log.info("file_ingest: value-detected column '%s' → linkedin_url", col)
        elif tg_hits >= thresh and "telegram_url" not in used_targets:
            mapping[col] = "telegram_url"
            used_targets.add("telegram_url")
        elif em_hits >= thresh and "email" not in used_targets:
            mapping[col] = "email"
            used_targets.add("email")

    return mapping


def _get(row: dict, field: str, col_map: dict[str, str]) -> Optional[Any]:
    """Get the value for a canonical field from a row, using the detected column mapping."""
    for col, target in col_map.items():
        if target == field:
            v = row.get(col)
            if v is not None and str(v).strip() not in ("", "nan", "None"):
                return v
    return None


def parse_file(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        log.warning("file not found: %s", path)
        return []

    suffix = p.suffix.lower()
    try:
        if suffix in (".xlsx", ".xls"):
            df = pd.read_excel(p)
        else:
            # Try UTF-8 first, then latin-1 (common for SalesNav exports)
            try:
                df = pd.read_csv(p, encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(p, encoding="latin-1")
    except Exception:
        log.exception("failed reading %s", path)
        return []

    df = df.where(pd.notnull(df), None)
    if df.empty:
        log.warning("file_ingest: file is empty: %s", path)
        return []

    col_map = _detect_columns(df)
    log.info("file_ingest: %d rows, %d columns, detected mapping: %s",
             len(df), len(df.columns),
             {col: tgt for col, tgt in col_map.items()})

    if not col_map:
        log.warning("file_ingest: no columns detected in %s — columns are: %s",
                    path, list(df.columns)[:20])

    out: list[dict[str, Any]] = []
    for _, r in df.iterrows():
        row = r.to_dict()

        full_name    = _get(row, "full_name", col_map)
        first_name   = _get(row, "first_name", col_map)
        last_name    = _get(row, "last_name", col_map)
        # Compose full_name from parts if needed
        if not full_name and (first_name or last_name):
            full_name = " ".join(x for x in [first_name, last_name] if x).strip() or None

        email        = _get(row, "email", col_map)
        phone        = _get(row, "phone", col_map)
        linkedin     = _get(row, "linkedin_url", col_map)
        tg           = _get(row, "telegram_url", col_map)
        bio          = _get(row, "bio", col_map)
        headline     = _get(row, "headline", col_map)
        location     = _get(row, "location", col_map)
        username     = _get(row, "username", col_map)
        company      = _get(row, "company", col_map)
        skills_raw   = _get(row, "skills", col_map)

        # Enrich bio with company if bio is empty
        if company and not bio:
            bio = f"at {company}"
        elif company and bio:
            bio = f"{bio}\n{company}"

        # Build text blob for contact extraction + OTW detection
        blob = " \n".join(
            str(x) for x in [full_name, headline, bio, location, skills_raw] if x
        )
        contacts     = extract_contacts(blob)
        otw, otw_sig = detect_open_to_work(blob)

        # Resolve email / phone from blob if not in dedicated columns
        if not email:
            email = contacts["emails"][0] if contacts["emails"] else None
        if not phone:
            phone = contacts["phones"][0] if contacts["phones"] else None
        if not linkedin:
            li_found = contacts.get("linkedin") or []
            linkedin = li_found[0] if li_found else None

        # Parse skills
        skills: list[str] = []
        if isinstance(skills_raw, str):
            skills = [s.strip() for s in skills_raw.replace(";", ",").split(",") if s.strip()]

        # Source ID — prefer linkedin URL, then any id column
        source_id = str(linkedin or row.get("id") or row.get("ID") or "")

        out.append({
            "source":       "file",
            "source_id":    source_id,
            "full_name":    str(full_name) if full_name else None,
            "first_name":   str(first_name) if first_name else None,
            "last_name":    str(last_name) if last_name else None,
            "username":     str(username) if username else None,
            "headline":     str(headline) if headline else None,
            "bio":          str(bio) if bio else None,
            "raw_text":     blob[:6000],
            "location":     str(location) if location else None,
            "skills":       skills,
            "email":        str(email) if email else None,
            "phone":        str(phone) if phone else None,
            "linkedin_url": str(linkedin) if linkedin else None,
            "telegram_url": str(tg) if tg else None,
            "open_to_work": otw,
            "otw_signal":   otw_sig,
            "raw":          {str(k): v for k, v in row.items()
                             if v is not None and str(v).strip() not in ("", "nan")},
        })

    log.info("file_ingest: %s → %d rows parsed, column map: %s",
             path, len(out), col_map)
    return out


def preview_file(path: str | Path, sample_rows: int = 5) -> dict[str, Any]:
    """Return column names, detected mapping, and sample rows for UI preview."""
    p = Path(path)
    suffix = p.suffix.lower()
    try:
        if suffix in (".xlsx", ".xls"):
            df = pd.read_excel(p)
        else:
            try:
                df = pd.read_csv(p, encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(p, encoding="latin-1")
    except Exception:
        return {"columns": [], "sample_rows": [], "mapped_fields": {}, "error": "Failed to read file"}

    df = df.where(pd.notnull(df), None)
    col_map = _detect_columns(df)

    sample = df.head(sample_rows).to_dict(orient="records")
    clean_sample = [
        {str(k): (str(v) if v is not None else "") for k, v in row.items()}
        for row in sample
    ]

    return {
        "columns":      [str(c) for c in df.columns],
        "sample_rows":  clean_sample,
        "mapped_fields": {str(col): tgt for col, tgt in col_map.items()},
        "total_rows":   len(df),
    }
