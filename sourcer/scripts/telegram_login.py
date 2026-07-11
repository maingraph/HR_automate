"""One-time Telegram login: creates a Telethon session file.

Usage:
    cd backend

    # Authenticate the LISTENER session (used by the persistent reply listener):
    python ../scripts/telegram_login.py

    # Authenticate the SCRAPER session (used by Celery pipeline scrapes):
    python ../scripts/telegram_login.py --session scraper

Both sessions authenticate as the same Telegram account (same phone number).
They are stored in separate .session files so concurrent access never causes
"database is locked" errors.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from telethon import TelegramClient  # noqa: E402

from app.core.config import settings  # noqa: E402

SESSION_DIR = Path(__file__).resolve().parents[1] / "backend" / "sessions"
SESSION_DIR.mkdir(parents=True, exist_ok=True)

_SESSION_MAP = {
    "listener": settings.telegram_session_name,   # default: sourcer_session
    "scraper":  "sourcer_scraper",
}


async def main(session_key: str) -> None:
    session_name = _SESSION_MAP[session_key]
    session_path = str(SESSION_DIR / session_name)

    phone = settings.telegram_phone or input("Phone (+country code, e.g. +12125551234): ").strip()
    print(f"\n→ Authenticating session: {session_name!r}  ({session_path}.session)")

    client = TelegramClient(session_path, settings.telegram_api_id, settings.telegram_api_hash)
    await client.start(phone=phone)
    me = await client.get_me()
    print(f"✅ Logged in as: {me.username or me.first_name} (id={me.id})")
    await client.disconnect()
    print(f"   Session saved → {session_path}.session\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Authenticate a Telethon session")
    parser.add_argument(
        "--session",
        choices=["listener", "scraper"],
        default="listener",
        help="Which session to create (default: listener)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.session))
