"""Telegram inbox monitor — checks for recent replies to the bot account."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

_SESSION_DIR = Path(__file__).resolve().parents[2] / "sessions"
_SESSION_PATH = str(_SESSION_DIR / "sourcer_session")  # Telethon adds .session suffix


async def _check_telegram_replies_async(since_hours: int) -> list[dict[str, Any]]:
    from telethon import TelegramClient
    from telethon.tl.types import User

    if not settings.telegram_api_id or not settings.telegram_api_hash:
        log.warning("Telegram credentials not configured; skipping reply check")
        return []

    since = datetime.now(tz=timezone.utc) - timedelta(hours=since_hours)
    results: list[dict[str, Any]] = []

    client = TelegramClient(_SESSION_PATH, settings.telegram_api_id, settings.telegram_api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            log.error(
                "Telegram session not authorized. Run scripts/telegram_login.py on the host first."
            )
            return []

        # iter_dialogs gives us all open conversations; we look only at private chats (User entities)
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            if not isinstance(entity, User):
                continue  # skip groups/channels

            last_msg = dialog.message
            if last_msg is None:
                continue

            msg_date = last_msg.date
            if msg_date and msg_date.tzinfo is None:
                msg_date = msg_date.replace(tzinfo=timezone.utc)

            if msg_date and msg_date < since:
                continue  # older than our window — all subsequent dialogs will be older too

            # Only collect messages that were sent TO us (incoming), not our own outgoing ones
            if last_msg.out:
                continue

            username = getattr(entity, "username", None)
            first_name = getattr(entity, "first_name", None) or ""
            last_name = getattr(entity, "last_name", None) or ""

            tg_url = f"https://t.me/{username}" if username else None

            results.append(
                {
                    "from_username": username,
                    "from_name": f"{first_name} {last_name}".strip() or None,
                    "text": last_msg.message or "",
                    "received_at": msg_date.isoformat() if msg_date else None,
                    "telegram_url": tg_url,
                }
            )

        log.info("Telegram monitor: found %d replies in last %dh", len(results), since_hours)
    except Exception:  # noqa: BLE001
        log.exception("check_telegram_replies failed")
    finally:
        try:
            await client.disconnect()
        except Exception:  # noqa: BLE001
            pass

    return results


def check_telegram_replies(since_hours: int = 24) -> list[dict[str, Any]]:
    """Return list of recent incoming messages from the bot's inbox.

    Each item: {from_username, from_name, text, received_at, telegram_url}
    """
    coro = _check_telegram_replies_async(since_hours)

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
