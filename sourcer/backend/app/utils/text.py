"""Text parsing helpers: contacts, OTW signals, resume detection."""
from __future__ import annotations

import hashlib
import re
from typing import Optional

EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_RE = re.compile(r"(\+?\d[\d\s\-()]{7,}\d)")
TG_HANDLE_RE = re.compile(r"(?:@|t\.me/)([A-Za-z0-9_]{4,})")
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[A-Za-z0-9_\-%]+/?")
URL_RE = re.compile(r"https?://[^\s)>\]]+")

OTW_PATTERNS = [
    # NOTE: no trailing \b — Russian branches use truncated stems (работ, поиск, предложени)
    # to catch inflections; a trailing \b would reject the inflected suffix (работы, поиске).
    r"\b(open\s*to\s*work|отк(?:рыт|рыта)\s*к\s*предложени|ищу\s*работ|looking\s*for\s*(?:a\s*)?job|в\s*поиск[ае]\s*работ|seeking\s*(?:new\s*)?opportunit|available\s*for\s*hire|#opentowork|#ищуработу)",
]
OTW_RE = re.compile("|".join(OTW_PATTERNS), re.IGNORECASE)

RESUME_KEYWORDS = [
    "резюме", "ищу работу", "ищу работу", "cv", "resume", "опыт работы",
    "experience", "media buyer", "медиабайер", "байер", "закупщик трафика",
    "traffic buyer", "affiliate", "арбитраж", "open to work", "#opentowork",
]


def extract_contacts(text: str) -> dict[str, list[str]]:
    if not text:
        return {"emails": [], "phones": [], "telegram": [], "linkedin": [], "urls": []}
    return {
        "emails": list(set(EMAIL_RE.findall(text))),
        "phones": list(set(PHONE_RE.findall(text))),
        "telegram": list(set(TG_HANDLE_RE.findall(text))),
        "linkedin": list(set(LINKEDIN_RE.findall(text))),
        "urls": list(set(URL_RE.findall(text))),
    }


def detect_open_to_work(text: str) -> tuple[bool, Optional[str]]:
    if not text:
        return False, None
    m = OTW_RE.search(text)
    if m:
        return True, m.group(0)
    return False, None


def looks_like_resume(text: str, extra_keywords: Optional[list[str]] = None) -> bool:
    """
    Check if text looks like a resume/job posting.
    
    Returns True if:
    1. Text contains any RESUME_KEYWORDS (hardcoded list)
    2. Text contains any extra_keywords (job-specific from AI)
    3. Text has contact info (email, phone, telegram, linkedin) - likely a resume
    4. Text is long enough (>100 chars) and has job-related patterns
    
    This is intentionally permissive to avoid filtering out valid candidates.
    """
    if not text:
        return False
    
    low = text.lower()
    
    # Check hardcoded keywords
    if any(k.lower() in low for k in RESUME_KEYWORDS):
        return True
    
    # Check job-specific keywords from AI
    if extra_keywords and any(k.lower() in low for k in extra_keywords):
        return True
    
    # Check if has contact info (strong signal it's a resume)
    contacts = extract_contacts(text)
    has_contact = (
        len(contacts["emails"]) > 0 or
        len(contacts["phones"]) > 0 or
        len(contacts["telegram"]) > 0 or
        len(contacts["linkedin"]) > 0
    )
    if has_contact:
        return True
    
    # If text is substantial and has job-related patterns, include it
    if len(text) > 100:
        job_patterns = [
            "years", "год", "опыт", "experience", "worked", "работал",
            "skills", "навыки", "stack", "tech", "developer", "engineer",
            "manager", "designer", "analyst", "specialist", "lead"
        ]
        if any(pattern in low for pattern in job_patterns):
            return True
    
    return False


def dedup_key(
    *,
    linkedin_url: Optional[str] = None,
    telegram_username: Optional[str] = None,
    email: Optional[str] = None,
    full_name: Optional[str] = None,
) -> str:
    parts = [
        (linkedin_url or "").strip().lower().rstrip("/"),
        (telegram_username or "").strip().lower().lstrip("@"),
        (email or "").strip().lower(),
        (full_name or "").strip().lower(),
    ]
    raw = "|".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()
