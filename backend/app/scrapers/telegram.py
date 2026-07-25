"""Telegram scraper via Telethon.

Scans provided channels for resume-like posts and extracts normalized
candidate dicts: name/username/text/contact.

NOTE on sessions: the scraper intentionally uses a SEPARATE session file
(sourcer_scraper.session) from the persistent reply listener
(sourcer_session.session).  Sharing a single SQLite session file between a
long-running listener and short-lived Celery worker tasks causes
``sqlite3.OperationalError: database is locked``.  Two different session
files = two independent auth tokens; both must be logged-in.  Run
``scripts/telegram_login.py --session scraper`` to authenticate the scraper
session (or just copy the listener session file once while the listener is
stopped).
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from telethon import TelegramClient
from telethon.tl.types import Message

from app.core.config import settings
from app.core.logging import get_logger
from app.utils.text import (
    detect_open_to_work,
    extract_contacts,
    looks_like_resume,
)

log = get_logger(__name__)

SESSION_DIR = Path(__file__).resolve().parents[2] / "sessions"
SESSION_DIR.mkdir(parents=True, exist_ok=True)

# Scraper uses its OWN session file so it never conflicts with the
# persistent telegram_listener (which holds sourcer_session open 24/7).
_SCRAPER_SESSION_NAME = "sourcer_scraper"


def _channel_slug(url_or_handle: str) -> str:
    s = url_or_handle.strip()
    s = re.sub(r"https?://t\.me/", "", s, flags=re.IGNORECASE)
    s = s.lstrip("@").rstrip("/")
    return s


def _normalize_message(msg: Message, channel: str, keywords: list[str]) -> Optional[dict[str, Any]]:
    text = (msg.message or "").strip()
    if not text:
        return None
    
    # Check if looks like resume (now more permissive)
    is_resume = looks_like_resume(text, extra_keywords=keywords)
    if not is_resume:
        log.debug("Filtered out message (not resume-like): %s...", text[:100])
        return None

    contacts = extract_contacts(text)
    otw, otw_sig = detect_open_to_work(text)

    sender = getattr(msg, "sender", None)
    first_name = getattr(sender, "first_name", None) if sender else None
    last_name = getattr(sender, "last_name", None) if sender else None
    sender_username = getattr(sender, "username", None) if sender else None

    # Prefer username in message text if present (channels often forward/ask to DM someone else)
    text_username = contacts["telegram"][0] if contacts["telegram"] else sender_username
    full_name = " ".join(p for p in [first_name, last_name] if p) or None

    tg_url = f"https://t.me/{text_username}" if text_username else None
    linkedin_url = contacts["linkedin"][0] if contacts["linkedin"] else None

    snippet_title = (text.splitlines()[0] or "")[:140] if text else None

    return {
        "source": "telegram",
        "source_id": f"{channel}:{msg.id}",
        "full_name": full_name,
        "first_name": first_name,
        "last_name": last_name,
        "username": text_username,
        "headline": snippet_title,
        "bio": text[:2000],
        "raw_text": text,
        "telegram_url": tg_url,
        "linkedin_url": linkedin_url,
        "email": contacts["emails"][0] if contacts["emails"] else None,
        "phone": contacts["phones"][0] if contacts["phones"] else None,
        "other_links": [{"url": u} for u in contacts["urls"][:10]],
        "open_to_work": otw,
        "otw_signal": otw_sig,
        "raw": {
            "channel": channel,
            "msg_id": msg.id,
            "date": msg.date.isoformat() if msg.date else None,
            "views": getattr(msg, "views", None),
        },
    }


async def _scan_channel(
    client: TelegramClient,
    channel: str,
    keywords: list[str],
    since: datetime,
    limit: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    slug = _channel_slug(channel)
    try:
        entity = await client.get_entity(slug)
    except Exception as e:  # noqa: BLE001
        log.warning("get_entity failed for %s: %s", channel, e)
        return out

    total_messages = 0
    filtered_count = 0
    count = 0
    async for msg in client.iter_messages(entity, limit=limit):
        total_messages += 1
        if msg.date and msg.date < since:
            break
        norm = _normalize_message(msg, channel=slug, keywords=keywords)
        if norm:
            out.append(norm)
            count += 1
        else:
            filtered_count += 1
    
    log.info(
        "telegram: %s → scanned %d messages, found %d candidates, filtered %d",
        slug, total_messages, count, filtered_count
    )
    return out


async def scrape_channels_async(
    channels: Iterable[str],
    keywords: list[str],
    days_back: int = 60,
    per_channel_limit: int = 1000,
) -> list[dict[str, Any]]:
    channels = [channel for channel in channels if str(channel).strip()]
    if not channels:
        raise ValueError("Telegram needs at least one channel to scan")
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        raise RuntimeError("Telegram API credentials are not configured")

    # Use the dedicated scraper session — never the listener session.
    # Falls back to the listener session if the scraper session doesn't exist
    # yet (first run before telegram_login.py --session scraper has been run).
    scraper_session = SESSION_DIR / _SCRAPER_SESSION_NAME
    listener_session = SESSION_DIR / settings.telegram_session_name
    if scraper_session.with_suffix(".session").exists():
        session_path = str(scraper_session)
        log.debug("Telegram scraper: using dedicated scraper session")
    else:
        session_path = str(listener_session)
        log.warning(
            "Telegram scraper session not found (%s.session); "
            "falling back to listener session — concurrent access may cause locks. "
            "Run: cd backend && python ../scripts/telegram_login.py --session scraper",
            scraper_session,
        )

    since = datetime.now(tz=timezone.utc) - timedelta(days=days_back)

    results: list[dict[str, Any]] = []
    client = TelegramClient(session_path, settings.telegram_api_id, settings.telegram_api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        log.error("Telegram session not authorized")
        await client.disconnect()
        raise RuntimeError("Telegram needs a one-time login confirmation before it can scan channels")
    try:
        for ch in channels:
            try:
                results.extend(
                    await _scan_channel(client, ch, keywords, since, per_channel_limit)
                )
            except Exception:  # noqa: BLE001
                log.exception("scrape channel %s failed", ch)
    finally:
        await client.disconnect()
    return results


def scrape_channels(
    channels: Iterable[str],
    keywords: list[str],
    days_back: int = 60,
    per_channel_limit: int = 1000,
) -> list[dict[str, Any]]:
    """Sync wrapper safe to call from both regular code and running event loops (Celery/FastAPI)."""
    import concurrent.futures

    coro = scrape_channels_async(
        channels=list(channels),
        keywords=keywords,
        days_back=days_back,
        per_channel_limit=per_channel_limit,
    )

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're inside an active event loop — run in a fresh thread with its own loop
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Channel Discovery
# ---------------------------------------------------------------------------

def _build_discovery_prompt(job: dict) -> str:
    """Build prompt for discovering relevant Telegram channels.
    
    Args:
        job: Job dictionary with title, description, skills, geo
        
    Returns:
        Prompt string for LLM
    """
    title = job.get("title", "")
    description = job.get("description", "")
    skills = job.get("skills", [])
    geo = job.get("geo", "")
    
    skills_str = ", ".join(skills) if skills else "N/A"
    
    prompt = f"""Given this job vacancy, suggest 10 relevant Telegram channels for sourcing candidates.

Job Details:
- Title: {title}
- Description: {description[:500]}
- Required Skills: {skills_str}
- Location/Geo: {geo}

Suggest Telegram channels that are:
1. Job boards for the specific tech stack/industry
2. Community channels for the required skills
3. Regional/geo-specific channels if applicable
4. Professional networking channels in the field

Return STRICT JSON with this format:
{{
  "channels": [
    {{"handle": "@python_jobs", "reason": "Large Python job board with daily postings", "confidence": "high"}},
    {{"handle": "@remotejobs", "reason": "Remote-first job board, matches geo requirement", "confidence": "high"}},
    ...
  ]
}}

IMPORTANT:
- Return exactly 10 channels
- Use @ prefix for handles (e.g., @python_jobs)
- Confidence: "high", "medium", or "low"
- Focus on REAL, popular channels (not made-up ones)
- Prioritize job boards and professional communities
- Include regional channels if geo is specific
"""
    
    return prompt


async def _validate_channel_exists_async(handle: str) -> bool:
    """Check if a Telegram channel exists and is accessible.
    
    Args:
        handle: Channel handle (e.g., @python_jobs)
        
    Returns:
        True if channel exists and is accessible, False otherwise
    """
    try:
        client = TelegramClient(
            str(SESSION_DIR / _SCRAPER_SESSION_NAME),
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )
        await client.connect()
        
        if not await client.is_user_authorized():
            log.warning("Telegram scraper session not authorized - cannot validate channels")
            await client.disconnect()
            return False
        
        # Try to get the channel entity
        try:
            entity = await client.get_entity(handle)
            await client.disconnect()
            return True
        except Exception as e:
            log.debug(f"Channel {handle} not found or not accessible: {e}")
            await client.disconnect()
            return False
            
    except Exception as e:
        log.exception(f"Failed to validate channel {handle}")
        return False


def validate_channel_exists(handle: str) -> bool:
    """Synchronous wrapper for channel validation.
    
    Args:
        handle: Channel handle (e.g., @python_jobs)
        
    Returns:
        True if channel exists and is accessible, False otherwise
    """
    import concurrent.futures
    
    coro = _validate_channel_exists_async(handle)
    
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    
    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


def discover_channels(job: dict, validate: bool = True) -> list[dict]:
    """Discover relevant Telegram channels using LLM.
    
    Args:
        job: Job dictionary with title, description, skills, geo
        validate: Whether to validate channels exist (adds 5-10 seconds)
        
    Returns:
        List of channel dictionaries:
        [{"handle": "@channel", "reason": "...", "confidence": "high"}, ...]
    """
    from app.scoring.gemini import _call_openrouter_retry, _json_from_text
    from app.core.config import settings
    
    log.info(f"Discovering Telegram channels for job: {job.get('title')}")
    
    # Build prompt
    prompt = _build_discovery_prompt(job)
    
    # Call LLM
    try:
        system_prompt = "You are an expert recruiter who knows all the major Telegram channels for tech recruitment."
        
        if settings.ai_provider == "openrouter":
            raw = _call_openrouter_retry(
                system_prompt,
                prompt,
                temperature=0.3,
                model=settings.get_model_for_task("channel_discovery"),
            )
        else:
            # Use Gemini
            from app.scoring.gemini import _generate_gemini
            raw = _generate_gemini(
                system_prompt,
                prompt,
                temperature=0.3,
                model=settings.get_model_for_task("channel_discovery"),
            )
        
        # Parse response
        data = _json_from_text(raw)
        channels = data.get("channels", [])
        
        if not channels:
            log.warning("LLM returned no channels")
            return []
        
        log.info(f"LLM suggested {len(channels)} channels")
        
        # Validate channels if requested
        if validate:
            log.info("Validating channel existence...")
            validated = []
            for ch in channels:
                handle = ch.get("handle", "")
                if not handle:
                    continue
                
                # Quick validation
                exists = validate_channel_exists(handle)
                if exists:
                    validated.append(ch)
                    log.info(f"✓ {handle} - exists")
                else:
                    log.info(f"✗ {handle} - not found or not accessible")
            
            log.info(f"Validated {len(validated)}/{len(channels)} channels")
            return validated[:10]  # Return top 10
        else:
            return channels[:10]
        
    except Exception as e:
        log.exception("Channel discovery failed")
        return []
