"""LLM-powered reply classification and response drafting.

Two-step pipeline for every incoming candidate reply:

Step 1 — Intent Classification:
    Given the full conversation history + candidate profile, classify the
    intent of the latest incoming message into one of four buckets:
      - interested   : candidate wants to know more / ready to move forward
      - questions    : candidate has specific questions (salary, remote, tech stack…)
      - declined     : candidate is not interested or has already accepted elsewhere
      - other        : ambiguous / off-topic / needs human judgment

Step 2 — Draft Generation:
    For 'interested' and 'questions' intents, generate a context-aware reply
    using the job description, screening questions, and the campaign's custom
    persona/instructions. For 'declined' or 'other', generate a polite closing
    or escalation note respectively.
"""
from __future__ import annotations

import json
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.scoring.gemini import _call_openrouter_retry  # shares the same LLM plumbing

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_CLASSIFY_SYSTEM = """You are an expert recruiting assistant.
You are given a candidate's reply to an outreach message from a recruiter.
Classify the intent of the candidate's reply into EXACTLY one of these categories:

  interested  — The candidate is open to the opportunity, wants to learn more,
                asks about next steps, or agrees to a call/interview.
  questions   — The candidate asks specific factual questions (salary, remote work,
                tech stack, team size, location, timeline, etc.) but hasn't
                committed to moving forward.
  declined    — The candidate is not interested, is already employed (happy),
                asks to be removed, or explicitly declines.
  other       — Ambiguous, incomplete, off-topic, or the reply needs a human
                to decide how to respond.

Return STRICT JSON only — no markdown:
{"intent": "interested" | "questions" | "declined" | "other", "reasoning": "one sentence"}"""


_DRAFT_SYSTEM = """You are {persona}.
You are writing a follow-up message to a candidate who replied to a job outreach.
You must write a SHORT (2-4 sentences max), warm, professional message.

RULES:
- Never be pushy or salesy.
- Match the tone of the candidate's message (casual/formal).
- For 'questions' intent: answer the question concisely using the vacancy details provided.
  If the answer isn't in the vacancy details, say "I can share more details on our call" —
  never make up specifics.
- For 'interested' intent: confirm their interest warmly and propose a next step
  (e.g. "Let's schedule a 20-min intro call — what times work for you this week?").
- For 'declined' intent: respect their decision gracefully, wish them well,
  and leave the door open for future opportunities.
- For 'other' intent: acknowledge their message warmly and ask a clarifying question.
- If the campaign has screening_questions, weave in ONE of them naturally
  (only for 'interested' or 'questions' intents).
- Do NOT reveal salary/budget specifics unless they are in the vacancy_details.
- Write in the same language the candidate used (Russian if they replied in Russian, etc.).

Return STRICT JSON only — no markdown:
{{"draft": "the full message text"}}"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _call_llm(system: str, prompt: str) -> str:
    """Call the configured LLM backend (OpenRouter or Gemini)."""
    if settings.ai_provider == "openrouter":
        return _call_openrouter_retry(system, prompt, temperature=0.5)
    else:
        # Gemini path — reuse the same model factory from gemini.py
        from app.scoring.gemini import _gen_model, _json_from_text
        model = _gen_model(system_instruction=system, temperature=0.5)
        resp = model.generate_content(prompt)
        return resp.text


def _parse_json(raw: str) -> dict[str, Any]:
    """Strip code fences and parse JSON."""
    import re
    t = raw.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t)
    return json.loads(t.strip())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_intent(
    candidate_reply: str,
    conversation_history: list[dict[str, Any]],
) -> dict[str, str]:
    """Classify the intent of the candidate's latest reply.

    Args:
        candidate_reply: The text of the latest incoming message.
        conversation_history: List of {direction, text} dicts (oldest first).

    Returns:
        {"intent": str, "reasoning": str}
    """
    history_text = "\n".join(
        f"[{'Recruiter' if m.get('direction') == 'sent' else 'Candidate'}]: {m.get('text', '')}"
        for m in conversation_history[-6:]  # last 3 exchanges at most
    )
    prompt = json.dumps(
        {
            "conversation_history": history_text,
            "latest_candidate_reply": candidate_reply,
        },
        ensure_ascii=False,
    )
    try:
        raw = _call_llm(_CLASSIFY_SYSTEM, prompt)
        result = _parse_json(raw)
        intent = result.get("intent", "other")
        if intent not in ("interested", "questions", "declined", "other"):
            intent = "other"
        return {"intent": intent, "reasoning": result.get("reasoning", "")}
    except Exception:  # noqa: BLE001
        log.exception("classify_intent failed — defaulting to 'other'")
        return {"intent": "other", "reasoning": "classification error"}


def draft_reply(
    intent: str,
    candidate_reply: str,
    conversation_history: list[dict[str, Any]],
    campaign: dict[str, Any],
    job: dict[str, Any],
) -> str:
    """Generate a context-aware draft reply.

    Args:
        intent: Output of classify_intent() — one of interested/questions/declined/other.
        candidate_reply: The text of the latest incoming message.
        conversation_history: List of {direction, text} dicts (oldest first).
        campaign: Campaign dict (tg_template, li_template, screening_questions, ai_persona).
        job: Job dict (title, description, skills, geo, seniority, budget_min, budget_max).

    Returns:
        The draft message text (plain string, ready to send).
    """
    persona = campaign.get("ai_persona") or "a friendly and professional HR recruiter"

    system = _DRAFT_SYSTEM.format(persona=persona)

    history_text = "\n".join(
        f"[{'Recruiter' if m.get('direction') == 'sent' else 'Candidate'}]: {m.get('text', '')}"
        for m in conversation_history[-6:]
    )

    # Build a concise vacancy summary to ground the LLM
    vacancy_details = {
        k: job.get(k)
        for k in ("title", "description", "skills", "geo", "seniority", "budget_min", "budget_max")
        if job.get(k)
    }

    prompt = json.dumps(
        {
            "intent": intent,
            "conversation_history": history_text,
            "latest_candidate_reply": candidate_reply,
            "vacancy_details": vacancy_details,
            "screening_questions": campaign.get("screening_questions") or [],
            "qualification_note": campaign.get("qualification_note") or "",
        },
        ensure_ascii=False,
    )

    try:
        raw = _call_llm(system, prompt)
        result = _parse_json(raw)
        draft = (result.get("draft") or "").strip()
        if not draft:
            raise ValueError("LLM returned empty draft")
        return draft
    except Exception:  # noqa: BLE001
        log.exception("draft_reply failed — returning fallback")
        # Graceful fallback — at least don't leave the recruiter with nothing
        return (
            "Hi, thanks for getting back to me! "
            "I'll be in touch shortly to discuss further details. "
            "Looking forward to connecting!"
        )
