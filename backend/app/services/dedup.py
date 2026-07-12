"""Cross-source deduplication."""
from __future__ import annotations

from typing import Any

from rapidfuzz import fuzz

from app.utils.text import dedup_key


def _normalize_name(n: str | None) -> str:
    return (n or "").lower().strip()


def dedup(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a list of unique candidates.

    Strategy:
    1. Strict dedup by (linkedin_url|telegram_username|email).
    2. Fuzzy name match (>=92 ratio) across remaining.
    """
    seen: dict[str, dict[str, Any]] = {}
    for c in candidates:
        key_fields = [
            c.get("linkedin_url"),
            c.get("telegram_url") or (f"@{c['username']}" if c.get("username") else None),
            c.get("email"),
        ]
        hits = [k for k in key_fields if k]
        key = hits[0] if hits else dedup_key(
            linkedin_url=c.get("linkedin_url"),
            telegram_username=c.get("username"),
            email=c.get("email"),
            full_name=c.get("full_name"),
        )
        c["dedup_key"] = key
        if key in seen:
            # merge: prefer non-empty fields from the newcomer
            existing = seen[key]
            for k, v in c.items():
                if v and not existing.get(k):
                    existing[k] = v
            # merge sources
            existing["source"] = existing.get("source") or c.get("source")
            raw = existing.setdefault("raw", {})
            raw.setdefault("merged_from", []).append(c.get("source"))
        else:
            seen[key] = c

    deduped = list(seen.values())

    # Fuzzy name pass
    final: list[dict[str, Any]] = []
    for c in deduped:
        cn = _normalize_name(c.get("full_name"))
        if not cn:
            final.append(c)
            continue
        matched = False
        for f in final:
            fn = _normalize_name(f.get("full_name"))
            if not fn:
                continue
            if fuzz.token_set_ratio(cn, fn) >= 92:
                # merge empty fields
                for k, v in c.items():
                    if v and not f.get(k):
                        f[k] = v
                matched = True
                break
        if not matched:
            final.append(c)

    return final
