"""Celery tasks for periodic LinkedIn inbox polling and cookie-expiry notifications.

Tasks:
    poll_linkedin_inbox_task  — Runs every 30 min (set up in celery beat schedule).
                                Fetches new LinkedIn replies, matches them to outreach
                                leads, and ingests them into outreach_messages.

    notify_cookie_expired     — Called when a cookie-expiry error is detected.
                                Sends a Telegram ping to the operator.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.celery_app import celery_app
from app.core.db import get_supabase
from app.core.logging import get_logger

log = get_logger(__name__)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Cookie-expiry Telegram notification
# ---------------------------------------------------------------------------

def _send_operator_ping(message: str) -> None:
    """Send an alert to the operator's own Telegram account."""
    from app.core.config import settings

    if not settings.operator_telegram_username:
        log.warning("OPERATOR_TELEGRAM_USERNAME not set — cannot send operator ping")
        return

    try:
        from app.outreach.sender import send_telegram
        result = send_telegram(settings.operator_telegram_username, message)
        if result["success"]:
            log.info("Operator Telegram ping sent successfully")
        else:
            log.warning("Operator ping failed: %s", result.get("error"))
    except Exception:  # noqa: BLE001
        log.exception("Failed to send operator Telegram ping")


def notify_cookie_expired(context: str = "LinkedIn outreach") -> None:
    """Public helper — call this whenever a COOKIE_EXPIRED error is detected.

    Sends a Telegram DM to the operator and logs the event.
    """
    msg = (
        "🚨 *Sourcer Agent Paused*\n\n"
        f"LinkedIn cookie (`li_at`) has expired during: *{context}*\n\n"
        "Please update `LINKEDIN_LI_AT` in the Credentials Manager and restart the agent."
    )
    log.error("LinkedIn cookie expired — sending operator notification")
    _send_operator_ping(msg)


# ---------------------------------------------------------------------------
# Core inbox ingestion logic
# ---------------------------------------------------------------------------

def _match_lead_by_linkedin_url(sb, linkedin_url: str) -> dict[str, Any] | None:
    """Find the most recent outreach lead matching a given LinkedIn profile URL."""
    if not linkedin_url:
        return None
    r = (
        sb.table("outreach_leads")
        .select("id, org_id, campaign_id, status, full_name")
        .eq("linkedin_url", linkedin_url)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return (r.data or [None])[0]


def _ingest_linkedin_reply(
    sb,
    lead: dict[str, Any],
    text: str,
    received_at: str,
) -> None:
    """Record an incoming LinkedIn message and update the lead status."""
    lead_id: str = lead["id"]

    # Insert into outreach_messages
    sb.table("outreach_messages").insert(
        {
            "org_id": lead.get("org_id"),
            "lead_id": lead_id,
            "direction": "received",
            "channel": "linkedin",
            "text": text,
            "is_auto": False,
            "created_at": received_at,
        }
    ).execute()

    # Advance lead status: pending/sent → replied
    current_status = lead.get("status", "")
    if current_status in ("pending", "sent"):
        sb.table("outreach_leads").update(
            {
                "status": "replied",
                "last_message": text,
                "last_message_at": received_at,
                "updated_at": _now_iso(),
            }
        ).eq("id", lead_id).execute()

    log.info("Ingested LinkedIn reply for lead %s (status: %s → replied)", lead_id, current_status)


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------

@celery_app.task(name="sourcer.poll_linkedin_inbox", bind=True)
def poll_linkedin_inbox_task(self) -> dict[str, Any]:
    """Poll the LinkedIn inbox for new incoming messages and ingest them.

    This task is designed to be run on a periodic Celery beat schedule
    (every 30 minutes). It:
    1. Fetches new messages from LinkedIn via read-only Voyager API.
    2. Matches each sender's LinkedIn URL to an outreach_lead row.
    3. Records the message and advances the lead status to "replied".
    4. Triggers cookie-expiry notification if auth fails.
    """
    from app.core.config import settings
    from app.outreach.linkedin_inbox import poll_linkedin_inbox

    log.info("poll_linkedin_inbox_task: starting")
    sb = get_supabase()

    # Determine the cutoff timestamp (last 35 min to overlap with 30-min schedule)
    from datetime import timedelta
    since_dt = datetime.now(tz=timezone.utc) - timedelta(minutes=35)
    since_ts = since_dt.isoformat()

    try:
        messages = poll_linkedin_inbox(since_timestamp=since_ts)
    except Exception as exc:  # noqa: BLE001
        err = str(exc)
        log.exception("poll_linkedin_inbox failed: %s", err)
        if "COOKIE_EXPIRED" in err or "cookie" in err.lower() or "unauthorized" in err.lower():
            notify_cookie_expired("inbox polling")
        return {"ok": False, "error": err}

    ingested = 0
    unmatched = 0

    for msg in messages:
        li_url = msg.get("from_linkedin_url")
        text = msg.get("text", "")
        received_at = msg.get("received_at", _now_iso())

        if not li_url or not text:
            unmatched += 1
            continue

        lead = _match_lead_by_linkedin_url(sb, li_url)
        if not lead:
            log.debug("No lead matched for LinkedIn URL %s — skipping", li_url)
            unmatched += 1
            continue

        try:
            _ingest_linkedin_reply(sb, lead, text, received_at)
            ingested += 1
        except Exception:  # noqa: BLE001
            log.exception("Failed to ingest reply from %s", li_url)

    log.info(
        "poll_linkedin_inbox_task done: ingested=%d, unmatched=%d",
        ingested,
        unmatched,
    )
    return {"ok": True, "ingested": ingested, "unmatched": unmatched}
