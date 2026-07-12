"""Celery tasks for outreach campaign batch sending."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.celery_app import celery_app
from app.core.db import get_supabase
from app.core.logging import get_logger

log = get_logger(__name__)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@celery_app.task(name="sourcer.send_campaign_batch", bind=True)
def send_campaign_batch(self, campaign_id: str) -> dict[str, Any]:
    """Iterate all pending leads in a campaign, compose and send messages.

    Respects per-channel rate limits (Telegram sender already enforces 30 s delays).
    Updates lead status after each send attempt.
    """
    from app.outreach.composer import compose_message
    from app.outreach.sender import send_linkedin_playwright, send_telegram

    sb = get_supabase()

    # Fetch campaign
    campaign_r = (
        sb.table("outreach_campaigns")
        .select("*")
        .eq("id", campaign_id)
        .maybe_single()
        .execute()
    )
    if not campaign_r.data:
        raise RuntimeError(f"Campaign {campaign_id} not found")
    campaign: dict[str, Any] = campaign_r.data

    # Fetch job context (optional)
    job: dict[str, Any] = {}
    if campaign.get("job_id"):
        job_r = (
            sb.table("jobs")
            .select("title, description, skills, geo, seniority")
            .eq("id", campaign["job_id"])
            .maybe_single()
            .execute()
        )
        if job_r.data:
            job = job_r.data

    # Fetch pending leads
    leads_r = (
        sb.table("outreach_leads")
        .select("*")
        .eq("campaign_id", campaign_id)
        .eq("status", "pending")
        .order("created_at", desc=False)
        .execute()
    )
    leads: list[dict[str, Any]] = leads_r.data or []

    log.info("send_campaign_batch: campaign=%s, pending_leads=%d", campaign_id, len(leads))

    stats = {"sent": 0, "failed": 0, "skipped": 0}

    for lead in leads:
        lead_id: str = lead["id"]
        channel = lead.get("preferred_channel") or "telegram"

        template = (
            campaign.get("tg_template") if channel == "telegram" else campaign.get("li_template")
        )
        if not template:
            log.warning("No %s template for campaign %s; skipping lead %s", channel, campaign_id, lead_id)
            sb.table("outreach_leads").update(
                {"status": "skipped", "updated_at": _now_iso()}
            ).eq("id", lead_id).execute()
            stats["skipped"] += 1
            continue

        # Check we have a target address
        if channel == "telegram" and not lead.get("telegram_url"):
            log.warning("Lead %s has no telegram_url; skipping", lead_id)
            sb.table("outreach_leads").update(
                {"status": "skipped", "updated_at": _now_iso()}
            ).eq("id", lead_id).execute()
            stats["skipped"] += 1
            continue
        if channel == "linkedin" and not lead.get("linkedin_url"):
            log.warning("Lead %s has no linkedin_url; skipping", lead_id)
            sb.table("outreach_leads").update(
                {"status": "skipped", "updated_at": _now_iso()}
            ).eq("id", lead_id).execute()
            stats["skipped"] += 1
            continue

        # Compose message
        try:
            message = compose_message(
                template=template, candidate=lead, job=job, channel=channel
            )
        except Exception:
            log.exception("compose_message failed for lead %s", lead_id)
            stats["failed"] += 1
            continue

        # Send
        try:
            if channel == "telegram":
                result = send_telegram(lead["telegram_url"], message)
            else:
                result = send_linkedin_playwright(lead["linkedin_url"], message)
        except Exception:
            log.exception("send failed for lead %s", lead_id)
            result = {"success": False, "error": "exception during send", "sent_at": None}

        now = _now_iso()
        if result["success"]:
            sb.table("outreach_leads").update(
                {
                    "status": "sent",
                    "last_message": message,
                    "last_message_at": now,
                    "updated_at": now,
                }
            ).eq("id", lead_id).execute()
            sb.table("outreach_messages").insert(
                {
                    "org_id": lead.get("org_id") or campaign.get("org_id"),
                    "lead_id": lead_id,
                    "direction": "sent",
                    "channel": channel,
                    "text": message,
                    "is_auto": True,
                }
            ).execute()
            stats["sent"] += 1
            log.info("Sent to lead %s via %s", lead_id, channel)
        else:
            log.warning("Send failed for lead %s: %s", lead_id, result.get("error"))
            stats["failed"] += 1
            # Keep status as pending so it can be retried; record error
            sb.table("outreach_leads").update(
                {
                    "last_message": f"[ERROR] {result.get('error', 'unknown')}",
                    "last_message_at": now,
                    "updated_at": now,
                }
            ).eq("id", lead_id).execute()

    # Mark campaign done if no pending leads remain
    remaining_r = (
        sb.table("outreach_leads")
        .select("id", count="exact")
        .eq("campaign_id", campaign_id)
        .eq("status", "pending")
        .execute()
    )
    remaining = getattr(remaining_r, "count", None) or len(remaining_r.data or [])
    if remaining == 0:
        sb.table("outreach_campaigns").update(
            {"status": "done", "updated_at": _now_iso()}
        ).eq("id", campaign_id).execute()

    log.info("send_campaign_batch done: %s", stats)
    return {"campaign_id": campaign_id, "ok": True, "stats": stats}
