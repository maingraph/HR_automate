"""Celery task: process an incoming candidate reply through the Copilot/Autopilot pipeline.

Flow:
  1. Load lead, campaign, job context, and conversation history from Supabase.
  2. Call reply_classifier.classify_intent() to determine candidate intent.
  3. Call reply_classifier.draft_reply() to generate a context-aware response.
  4. Based on campaign.outreach_mode:
       - 'copilot'   → Save draft + intent to lead; set needs_review=True.
                        The frontend "Needs Review" column shows it for human approval.
       - 'autopilot' → Send draft immediately via the appropriate channel sender.
                        Mark lead status based on intent:
                          interested/questions → keep 'replied'
                          declined            → 'rejected'
  5. For 'declined' intent in EITHER mode: always flag for human review regardless of mode,
     because a graceful close should be human-verified.
  6. For 'other' intent: always fall back to copilot (needs human review).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.celery_app import celery_app
from app.core.db import get_supabase, response_data
from app.core.logging import get_logger
from app.core.redis_client import cache_result

log = get_logger(__name__)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@cache_result(ttl=300, key_prefix="campaign_context")
def _get_campaign_with_job(sb, campaign_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Load campaign and associated job (cached for 5 minutes).
    Returns (campaign, job).
    """
    campaign_r = (
        sb.table("outreach_campaigns")
        .select("*")
        .eq("id", campaign_id)
        .maybe_single()
        .execute()
    )
    campaign: dict[str, Any] = campaign_r.data or {}

    job: dict[str, Any] = {}
    if campaign.get("job_id"):
        job_r = (
            sb.table("jobs")
            .select("title, description, skills, geo, seniority, budget_min, budget_max")
            .eq("id", campaign["job_id"])
            .maybe_single()
            .execute()
        )
        job_data = response_data(job_r)
        if job_data:
            job = job_data

    return campaign, job


def _load_context(
    sb, lead_id: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Return (lead, campaign, job, conversation_history)."""
    lead_r = sb.table("outreach_leads").select("*").eq("id", lead_id).maybe_single().execute()
    lead = response_data(lead_r)
    if not lead:
        raise RuntimeError(f"Lead {lead_id} not found")

    # Use cached campaign + job context
    campaign, job = _get_campaign_with_job(sb, lead["campaign_id"])

    # Last 10 messages for context (oldest first)
    hist_r = (
        sb.table("outreach_messages")
        .select("direction, channel, text, created_at")
        .eq("lead_id", lead_id)
        .order("created_at", desc=False)
        .limit(10)
        .execute()
    )
    history: list[dict[str, Any]] = hist_r.data or []

    return lead, campaign, job, history


def _save_draft(sb, lead_id: str, intent: str, draft: str) -> None:
    """Save AI draft to the lead row and flag for human review."""
    sb.table("outreach_leads").update(
        {
            "ai_intent": intent,
            "ai_draft": draft,
            "needs_review": True,
            "updated_at": _now_iso(),
        }
    ).eq("id", lead_id).execute()
    log.info("Copilot draft saved for lead %s (intent=%s)", lead_id, intent)


def _send_draft(sb, lead: dict[str, Any], channel: str, draft: str, intent: str) -> None:
    """Send draft immediately (autopilot) and update lead status."""
    from app.outreach.sender import send_linkedin_playwright, send_telegram

    lead_id: str = lead["id"]

    if channel == "telegram":
        target = lead.get("telegram_url")
        if not target:
            log.warning("Autopilot: lead %s has no telegram_url — falling back to draft", lead_id)
            _save_draft(sb, lead_id, intent, draft)
            return
        result = send_telegram(target, draft)
    else:
        target = lead.get("linkedin_url")
        if not target:
            log.warning("Autopilot: lead %s has no linkedin_url — falling back to draft", lead_id)
            _save_draft(sb, lead_id, intent, draft)
            return
        result = send_linkedin_playwright(target, draft)

    now = _now_iso()
    if result["success"]:
        # Record sent message
        sb.table("outreach_messages").insert(
            {
                "org_id": lead.get("org_id"),
                "lead_id": lead_id,
                "direction": "sent",
                "channel": channel,
                "text": draft,
                "is_auto": True,
                "created_at": now,
            }
        ).execute()
        new_status = "rejected" if intent == "declined" else "replied"
        sb.table("outreach_leads").update(
            {
                "ai_intent": intent,
                "ai_draft": draft,
                "needs_review": False,
                "status": new_status,
                "last_message": draft,
                "last_message_at": now,
                "updated_at": now,
            }
        ).eq("id", lead_id).execute()
        log.info(
            "Autopilot sent reply to lead %s via %s (intent=%s, status→%s)",
            lead_id, channel, intent, new_status,
        )
    else:
        log.warning(
            "Autopilot send failed for lead %s (%s): %s — saving draft",
            lead_id, channel, result.get("error"),
        )
        # Fall back to copilot on send failure
        _save_draft(sb, lead_id, intent, draft)


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------

@celery_app.task(
    name="sourcer.process_incoming_reply",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    time_limit=120,
    soft_time_limit=100,
)
def process_incoming_reply(
    self,
    lead_id: str,
    text: str,
    channel: str,
) -> dict[str, Any]:
    """Classify intent and draft/send a reply for an incoming candidate message.

    Args:
        lead_id: UUID of the outreach_lead row.
        text:    The incoming message text.
        channel: 'telegram' | 'linkedin'
    """
    from app.outreach.reply_classifier import classify_intent, draft_reply

    log.info(
        "process_incoming_reply: lead=%s channel=%s text=%r",
        lead_id, channel, text[:80],
    )

    try:
        sb = get_supabase()
        lead, campaign, job, history = _load_context(sb, lead_id)
    except Exception as exc:  # noqa: BLE001
        log.exception("Failed to load context for lead %s", lead_id)
        raise self.retry(exc=exc)

    outreach_mode: str = campaign.get("outreach_mode") or "copilot"

    # Step 1 — classify intent
    try:
        classification = classify_intent(
            candidate_reply=text,
            conversation_history=history,
        )
        intent: str = classification["intent"]
        reasoning: str = classification["reasoning"]
        log.info("Intent for lead %s: %s (%s)", lead_id, intent, reasoning)
    except Exception as exc:  # noqa: BLE001
        log.exception("classify_intent failed for lead %s", lead_id)
        intent = "other"
        reasoning = "classification failed"

    # Step 2 — draft reply
    try:
        draft: str = draft_reply(
            intent=intent,
            candidate_reply=text,
            conversation_history=history,
            campaign=campaign,
            job=job,
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("draft_reply failed for lead %s", lead_id)
        draft = ""

    # Step 3 — Copilot vs Autopilot routing
    # Always force copilot for 'other' or 'declined' intents — they need human judgment
    force_copilot = intent in ("other", "declined")

    if force_copilot or outreach_mode == "copilot" or not draft:
        _save_draft(sb, lead_id, intent, draft or "[Draft generation failed — review manually]")
        return {
            "ok": True,
            "mode": "copilot",
            "lead_id": lead_id,
            "intent": intent,
            "draft_saved": bool(draft),
        }
    else:
        # Autopilot: send immediately
        _send_draft(sb, lead=lead, channel=channel, draft=draft, intent=intent)
        return {
            "ok": True,
            "mode": "autopilot",
            "lead_id": lead_id,
            "intent": intent,
        }
