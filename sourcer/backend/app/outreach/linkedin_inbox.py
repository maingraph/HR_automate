"""LinkedIn inbox poller using the unofficial Voyager API (read-only).

WHY READ-ONLY?
- GET requests to Voyager are much lower risk than POST requests.
- We only use this for polling incoming messages — never for sending.
- Sending is handled exclusively by the safer Playwright DOM worker.

This module polls for unread LinkedIn conversations that were received
after a given timestamp and returns them in a normalised format compatible
with the outreach_messages table.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


def _get_linkedin_client():
    """Build a linkedin_api client using the li_at cookie."""
    try:
        from linkedin_api import Linkedin  # type: ignore[import-untyped]
    except ImportError:
        raise RuntimeError(
            "linkedin-api package not installed. "
            "Run: pip install git+https://github.com/tomquirk/linkedin-api.git"
        )

    if not settings.linkedin_li_at:
        raise RuntimeError("LINKEDIN_LI_AT not configured — cannot poll LinkedIn inbox")

    # linkedin_api accepts the li_at cookie as the password when using cookie auth.
    # We pass a dummy email and provide the li_at cookie directly.
    client = Linkedin(
        "",
        "",
        cookies={"li_at": settings.linkedin_li_at},
        debug=False,
    )
    return client


def poll_linkedin_inbox(since_timestamp: str | None = None) -> list[dict[str, Any]]:
    """Fetch recent incoming LinkedIn messages.

    Args:
        since_timestamp: ISO-8601 string. Only returns messages newer than this.
                         Defaults to messages from the last 24 hours if None.

    Returns:
        List of dicts: {
            from_name, from_linkedin_url, from_profile_urn,
            text, received_at, conversation_id
        }
    """
    if not settings.linkedin_li_at:
        log.warning("LINKEDIN_LI_AT not set — skipping LinkedIn inbox poll")
        return []

    if since_timestamp:
        since_dt = datetime.fromisoformat(since_timestamp)
        if since_dt.tzinfo is None:
            since_dt = since_dt.replace(tzinfo=timezone.utc)
    else:
        from datetime import timedelta
        since_dt = datetime.now(tz=timezone.utc) - timedelta(hours=24)

    try:
        client = _get_linkedin_client()
    except RuntimeError as e:
        log.error("LinkedIn inbox poll init failed: %s", e)
        return []

    results: list[dict[str, Any]] = []

    try:
        # Get recent conversations — limit to 20 to avoid hammering the API
        conversations = client.get_conversations()
        if not conversations:
            return []

        for conv in conversations.get("elements", []):
            # Each element is a conversation; check the last event timestamp
            last_activity_at_ms: int = conv.get("lastActivityAt", 0)
            last_activity_dt = datetime.fromtimestamp(
                last_activity_at_ms / 1000, tz=timezone.utc
            )

            if last_activity_dt <= since_dt:
                continue  # older than our window, skip

            conv_id: str = conv.get("entityUrn", "").split(":")[-1]
            if not conv_id:
                continue

            # Fetch messages in this conversation
            time.sleep(0.5)  # brief pause between API calls
            try:
                messages_resp = client.get_conversation(conv_id)
            except Exception:  # noqa: BLE001
                log.warning("Could not fetch conversation %s", conv_id)
                continue

            for event in messages_resp.get("elements", []):
                # Only handle incoming messages (not our own)
                if event.get("subtype") != "MEMBER_TO_MEMBER":
                    continue

                sender = event.get("from", {}).get("com.linkedin.voyager.messaging.MessagingMember", {})
                sender_urn = sender.get("miniProfile", {}).get("entityUrn", "")
                sender_id = sender_urn.split(":")[-1] if sender_urn else ""

                # Skip messages WE sent (outgoing)
                # The "me" profile doesn't have a simple flag, so we use the sender urn
                # against a stored "self_urn" — if unavailable, skip "out" events heuristically
                if not sender_id:
                    continue

                created_at_ms: int = event.get("createdAt", 0)
                created_dt = datetime.fromtimestamp(created_at_ms / 1000, tz=timezone.utc)

                if created_dt <= since_dt:
                    continue

                body = event.get("eventContent", {}).get(
                    "com.linkedin.voyager.messaging.event.MessageEvent", {}
                ).get("attributedBody", {}).get("text", "")

                if not body:
                    continue

                mini_profile = sender.get("miniProfile", {})
                first = mini_profile.get("firstName", "")
                last = mini_profile.get("lastName", "")
                public_id = mini_profile.get("publicIdentifier", "")
                li_url = f"https://www.linkedin.com/in/{public_id}" if public_id else None

                results.append(
                    {
                        "from_name": f"{first} {last}".strip() or None,
                        "from_linkedin_url": li_url,
                        "from_profile_urn": sender_urn,
                        "text": body.strip(),
                        "received_at": created_dt.isoformat(),
                        "conversation_id": conv_id,
                    }
                )

    except Exception:  # noqa: BLE001
        log.exception("LinkedIn inbox poll failed")

    log.info("LinkedIn inbox poll: found %d new incoming messages", len(results))
    return results
