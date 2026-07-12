"""Persistent Telegram reply listener (long-lived asyncio process).

WHY a separate process, not a Celery task?
- Celery tasks are short-lived and synchronous by design.
- Telethon's event-based listener requires a persistent asyncio event loop that
  stays alive indefinitely — it is fundamentally incompatible with Celery.
- This process is started alongside the Celery worker (see launch.sh / docker-compose).

What this listener does:
1. Connects to Telegram using the existing sourcer_session.
2. Registers a NewMessage(incoming=True) handler on private chats (DMs only).
3. When a message arrives:
   a. Looks up the sender's Telegram username/URL in outreach_leads.
   b. If found → inserts into outreach_messages (direction='received').
   c. Advances lead status: pending/sent → replied.
   d. Queues a process_incoming_reply Celery task (Phase 3 AI pipeline).
4. Reconnects automatically on network errors (exponential back-off).
5. Pings the operator on Telegram if the session becomes unauthorised.
"""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: make sure the backend package is importable when run as a script
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).resolve().parents[2]  # backend/
sys.path.insert(0, str(_BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.core.db import get_supabase  # noqa: E402
from app.core.logging import get_logger  # noqa: E402

log = get_logger(__name__)

_SESSION_DIR = Path(__file__).resolve().parents[2] / "sessions"
_SESSION_PATH = str(_SESSION_DIR / settings.telegram_session_name)


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _find_lead(username: str) -> dict | None:
    """Return the most recent outreach_lead matching the Telegram username."""
    if not username:
        return None
    sb = get_supabase()
    tg_url_variants = [
        f"https://t.me/{username}",
        f"http://t.me/{username}",
        f"@{username}",
        username,
    ]
    for url in tg_url_variants:
        r = (
            sb.table("outreach_leads")
            .select("id, campaign_id, status, full_name, preferred_channel")
            .eq("telegram_url", url)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if r.data:
            return r.data[0]
    return None


def _ingest_reply(lead: dict, text: str, tg_message_id: int) -> None:
    """Record the incoming message and advance the lead status."""
    sb = get_supabase()
    lead_id: str = lead["id"]
    now = _now_iso()

    # Insert message record
    sb.table("outreach_messages").insert(
        {
            "lead_id": lead_id,
            "direction": "received",
            "channel": "telegram",
            "text": text,
            "is_auto": False,
            "created_at": now,
        }
    ).execute()

    # Only advance status if it hasn't already been moved forward
    current_status = lead.get("status", "")
    if current_status in ("pending", "sent"):
        sb.table("outreach_leads").update(
            {
                "status": "replied",
                "last_message": text,
                "last_message_at": now,
                "updated_at": now,
            }
        ).eq("id", lead_id).execute()
        log.info(
            "Telegram reply ingested: lead=%s (%s) status=%s→replied",
            lead_id,
            lead.get("full_name", "?"),
            current_status,
        )
    else:
        # Already replied/qualified — still record the message, just don't regress the status
        sb.table("outreach_leads").update(
            {"last_message": text, "last_message_at": now, "updated_at": now}
        ).eq("id", lead_id).execute()
        log.info(
            "Telegram reply ingested (no status change, already=%s): lead=%s",
            current_status,
            lead_id,
        )


def _queue_ai_pipeline(lead_id: str, text: str, channel: str) -> None:
    """Dispatch a Celery task to run the Copilot/Autopilot AI pipeline.

    Phase 3 will implement process_incoming_reply. If the task doesn't exist yet
    (i.e. we're still on Phase 2), this is a no-op — we import lazily and
    catch ImportError gracefully.
    """
    try:
        from app.tasks.reply_pipeline import process_incoming_reply  # Phase 3 task
        process_incoming_reply.delay(lead_id=lead_id, text=text, channel=channel)
        log.debug("Queued AI pipeline for lead %s", lead_id)
    except ImportError:
        log.debug("reply_pipeline task not yet implemented (Phase 3) — skipping AI dispatch")
    except Exception:  # noqa: BLE001
        log.exception("Failed to queue AI pipeline for lead %s", lead_id)


# ---------------------------------------------------------------------------
# Core event handler
# ---------------------------------------------------------------------------

async def _handle_new_message(event) -> None:
    """Called by Telethon for every incoming private DM."""
    try:
        sender = await event.get_sender()
        if sender is None:
            return

        username: str = getattr(sender, "username", None) or ""
        first_name: str = getattr(sender, "first_name", None) or ""
        last_name: str = getattr(sender, "last_name", None) or ""
        sender_display = f"@{username}" if username else f"{first_name} {last_name}".strip()

        text: str = event.message.message or ""
        if not text.strip():
            return

        log.info("Incoming Telegram DM from %s: %r", sender_display, text[:120])

        if not username:
            log.debug("Sender has no username — cannot match to a lead")
            return

        lead = _find_lead(username)
        if not lead:
            log.debug("No outreach lead found for Telegram @%s — ignoring", username)
            return

        _ingest_reply(lead, text, tg_message_id=event.message.id)
        _queue_ai_pipeline(lead_id=lead["id"], text=text, channel="telegram")

    except Exception:  # noqa: BLE001
        log.exception("Error in _handle_new_message handler")


# ---------------------------------------------------------------------------
# Listener lifecycle
# ---------------------------------------------------------------------------

async def run_listener() -> None:
    """Start the persistent Telethon listener with automatic reconnection."""
    from telethon import TelegramClient, events

    if not settings.telegram_api_id or not settings.telegram_api_hash:
        log.error("TELEGRAM_API_ID / TELEGRAM_API_HASH not configured — listener cannot start")
        return

    _SESSION_DIR.mkdir(parents=True, exist_ok=True)
    backoff = 5  # seconds before first retry

    while True:
        client = TelegramClient(
            _SESSION_PATH,
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )
        try:
            await client.connect()

            if not await client.is_user_authorized():
                log.error(
                    "Telegram session not authorized. "
                    "Run: cd backend && python ../scripts/telegram_login.py"
                )
                # Notify operator and exit — no point retrying without a valid session
                if settings.operator_telegram_username:
                    try:
                        from app.outreach.sender import send_telegram
                        send_telegram(
                            settings.operator_telegram_username,
                            "🚨 Sourcer Telegram listener failed to start — session not authorized.\n"
                            "Run telegram_login.py to re-authenticate.",
                        )
                    except Exception:  # noqa: BLE001
                        pass
                return

            me = await client.get_me()
            log.info(
                "Telegram listener started — logged in as @%s (id=%s)",
                getattr(me, "username", "?"),
                getattr(me, "id", "?"),
            )

            # Register handler: private chats only (not groups/channels), incoming only
            @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
            async def handler(event):
                await _handle_new_message(event)

            backoff = 5  # reset backoff on successful connect
            await client.run_until_disconnected()

        except Exception as exc:  # noqa: BLE001
            log.warning(
                "Telegram listener disconnected (%s). Reconnecting in %ds…", exc, backoff
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 300)  # cap at 5-minute retry interval

        finally:
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                pass


def main() -> None:
    """Entry point — run the listener, handle SIGTERM/SIGINT gracefully."""
    log.info("Starting Telegram reply listener…")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _shutdown(sig_name: str) -> None:
        log.info("Received %s — shutting down Telegram listener", sig_name)
        for task in asyncio.all_tasks(loop):
            task.cancel()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig.name: _shutdown(s))

    try:
        loop.run_until_complete(run_listener())
    except (KeyboardInterrupt, asyncio.CancelledError):
        log.info("Telegram listener stopped cleanly")
    finally:
        loop.close()


if __name__ == "__main__":
    # Configure basic logging when run standalone
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    main()
