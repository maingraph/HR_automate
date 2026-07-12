"""Multi-channel outreach sender: Telegram (Telethon) and LinkedIn (Playwright DOM).

LinkedIn sending uses headless Playwright to interact with the DOM directly,
which is significantly safer against LinkedIn's bot detection than using
undocumented POST APIs (Voyager). See outreach/linkedin_playwright.py.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

# --------------------------------------------------------------------------- #
# Session / path config
# --------------------------------------------------------------------------- #

_SESSION_DIR = Path(__file__).resolve().parents[2] / "sessions"
_SESSION_PATH = str(_SESSION_DIR / "sourcer_session")  # Telethon adds .session suffix

# --------------------------------------------------------------------------- #
# Rate-limit state (module-level — shared within one process/worker)
# --------------------------------------------------------------------------- #

_TG_RATE_SECONDS = 30
_last_tg_send: float = 0.0


def _tg_rate_wait() -> None:
    """Block until at least _TG_RATE_SECONDS have passed since the last send."""
    global _last_tg_send
    elapsed = time.monotonic() - _last_tg_send
    if elapsed < _TG_RATE_SECONDS:
        wait = _TG_RATE_SECONDS - elapsed
        log.debug("Telegram rate-limit: sleeping %.1fs", wait)
        time.sleep(wait)
    _last_tg_send = time.monotonic()


# --------------------------------------------------------------------------- #
# Telegram sender
# --------------------------------------------------------------------------- #

async def _send_telegram_async(telegram_url_or_username: str, message: str) -> dict[str, Any]:
    from telethon import TelegramClient

    if not settings.telegram_api_id or not settings.telegram_api_hash:
        return {"success": False, "error": "Telegram credentials not configured", "sent_at": None}

    # Normalise: strip https://t.me/ and @
    handle = telegram_url_or_username.strip()
    handle = handle.replace("https://t.me/", "").replace("http://t.me/", "").lstrip("@").rstrip("/")

    client = TelegramClient(_SESSION_PATH, settings.telegram_api_id, settings.telegram_api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            return {
                "success": False,
                "error": "Telegram session not authorized. Run scripts/telegram_login.py first.",
                "sent_at": None,
            }
        await client.send_message(handle, message)
        sent_at = datetime.now(tz=timezone.utc).isoformat()
        log.info("Telegram message sent to %s", handle)
        return {"success": True, "error": None, "sent_at": sent_at}
    except Exception as exc:  # noqa: BLE001
        log.exception("Telegram send failed for %s", handle)
        return {"success": False, "error": str(exc), "sent_at": None}
    finally:
        try:
            await client.disconnect()
        except Exception:  # noqa: BLE001
            pass


def send_telegram(telegram_url_or_username: str, message: str) -> dict[str, Any]:
    """Send a Telegram DM; enforces 30 s inter-send rate limit.

    Returns:
        {success: bool, error: str | None, sent_at: str | None}
    """
    _tg_rate_wait()

    coro = _send_telegram_async(telegram_url_or_username, message)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


# --------------------------------------------------------------------------- #
# LinkedIn sender (Playwright DOM — replaces Phantombuster)
# --------------------------------------------------------------------------- #

def _send_linkedin_internal(linkedin_url: str, message: str) -> dict[str, Any]:
    """Internal sync implementation of LinkedIn sending."""
    from app.outreach.linkedin_playwright import (  # lazy — avoids playwright startup cost
        send_linkedin_playwright as _send,
    )
    result = _send(linkedin_url, message)

    # Surface cookie expiry as a special signal so callers can notify the operator
    if not result["success"] and result.get("error", "").startswith("COOKIE_EXPIRED"):
        from app.tasks.poll_inbox import notify_cookie_expired
        notify_cookie_expired("outreach send")

    return result


def send_linkedin_playwright(linkedin_url: str, message: str) -> dict[str, Any]:
    """Send a LinkedIn message using a stealth headless Playwright browser.

    Delegates to outreach.linkedin_playwright which handles rate limiting,
    anti-ban measures, and cookie-expiry error normalisation.
    
    Handles both sync and async callers by using a ThreadPoolExecutor if needed.

    Returns:
        {success: bool, error: str | None, sent_at: str | None}
    """
    try:
        import asyncio
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(_send_linkedin_internal, linkedin_url, message).result()
    else:
        return _send_linkedin_internal(linkedin_url, message)
