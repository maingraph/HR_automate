"""Outreach message composition — template variable substitution.

Variables supported in templates (case-insensitive):
  {name}       → full_name (first word only)
  {full_name}  → full_name
  {headline}   → headline
  {location}   → location
"""
from __future__ import annotations

import re
from typing import Any

from app.core.logging import get_logger

log = get_logger(__name__)


def compose_message(
    template: str,
    candidate: dict[str, Any],
    job: dict[str, Any],  # kept for API compat, not used in substitution
    channel: str,         # kept for API compat
) -> str:
    """Return the template with {variable} placeholders substituted.

    Uses the candidate's full_name, headline, and location.
    Falls back gracefully when values are missing.
    """
    full_name: str = candidate.get("full_name") or candidate.get("username") or ""
    # {name} → first name only (first space-separated token)
    first_name = full_name.split()[0] if full_name.strip() else ""

    substitutions: dict[str, str] = {
        "name":      first_name or full_name,
        "full_name": full_name,
        "headline":  candidate.get("headline") or "",
        "location":  candidate.get("location") or "",
    }

    def _replace(m: re.Match) -> str:
        key = m.group(1).strip().lower()
        return substitutions.get(key, m.group(0))  # leave unknown placeholders as-is

    message = re.sub(r"\{(\w+)\}", _replace, template)
    return message
