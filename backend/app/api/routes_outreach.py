"""Outreach campaigns, leads, and conversation routes."""
from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, get_current_user
from app.core.db import get_supabase, response_data
from app.core.logging import get_logger
from app.scoring.gemini import _call_openrouter_retry

log = get_logger(__name__)
router = APIRouter(prefix="/outreach", tags=["outreach"])


# --------------------------------------------------------------------------- #
# Pydantic schemas
# --------------------------------------------------------------------------- #


class CampaignCreate(BaseModel):
    name: str
    job_id: Optional[str] = None
    tg_template: Optional[str] = None
    li_template: Optional[str] = None
    screening_questions: list[str] = Field(default_factory=list)
    tg_account: Optional[str] = None          # e.g. @maksimm2108
    qualification_note: Optional[str] = None  # where/how to forward qualified leads


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None  # draft | active | paused | done


class CampaignOut(BaseModel):
    id: str
    name: str
    job_id: Optional[str] = None
    tg_template: Optional[str] = None
    li_template: Optional[str] = None
    screening_questions: list[str] = Field(default_factory=list)
    tg_account: Optional[str] = None
    qualification_note: Optional[str] = None
    status: str
    created_at: str
    updated_at: str


class LeadStatusUpdate(BaseModel):
    status: str  # pending | sent | replied | qualified | rejected | skipped
    preferred_channel: Optional[str] = None
    notes: Optional[str] = None


class ManualReply(BaseModel):
    text: str
    channel: str  # telegram | linkedin


class SendOnePayload(BaseModel):
    channel: Optional[str] = None  # override preferred_channel


class OutreachModeUpdate(BaseModel):
    outreach_mode: str  # copilot | autopilot


class DraftEdit(BaseModel):
    text: Optional[str] = None  # if provided, override the AI draft before sending
    channel: Optional[str] = None  # override preferred_channel


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

_COLUMN_MAP_SYSTEM = (
    "You are a data engineer. Given column names and sample rows from a spreadsheet, "
    "identify which column maps to each of these fields: "
    "full_name, linkedin_url, telegram_url, headline, score, email. "
    "Return STRICT JSON only, no markdown: "
    '{"full_name": "col_name_or_null", "linkedin_url": "...", "telegram_url": "...", '
    '"headline": "...", "score": "...", "email": "..."}. '
    "Use null if no matching column exists."
)


def _detect_columns(columns: list[str], sample_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Use OpenRouter to identify column mappings from headers + sample data."""
    prompt = json.dumps(
        {"columns": columns, "sample_rows": sample_rows[:5]}, ensure_ascii=False
    )
    try:
        raw = _call_openrouter_retry(_COLUMN_MAP_SYSTEM, prompt, temperature=0.0)
        # strip code fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            import re
            raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        return json.loads(raw)
    except Exception:
        log.exception("Column detection failed")
        return {f: None for f in ("full_name", "linkedin_url", "telegram_url", "headline", "score", "email")}


def _parse_xlsx_bytes(data: bytes, filename: str = "") -> tuple[list[str], list[dict[str, Any]]]:
    """Parse XLSX or CSV bytes → (columns, rows_as_dicts)."""
    import csv

    # Detect CSV by extension hint or by trying to sniff the content
    is_csv = filename.lower().endswith(".csv")
    if not is_csv:
        # Sniff: XLSX is a zip file (starts with PK\x03\x04); CSV is plain text
        is_csv = not data[:4].startswith(b"PK\x03\x04")

    if is_csv:
        # Try UTF-8 first, fall back to latin-1 (common in SalesNav/PB exports)
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise HTTPException(status_code=400, detail="Could not decode CSV file")

        # Detect delimiter (comma or semicolon)
        sample = text[:4096]
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        rows_raw = list(reader)
        if not rows_raw:
            return [], []
        headers = list(rows_raw[0].keys())
        result = [{k: (v if v != "" else None) for k, v in row.items()} for row in rows_raw]
        return headers, result

    # XLSX path
    try:
        import openpyxl
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl is required for XLSX parsing")

    wb = openpyxl.load_workbook(filename=io.BytesIO(data), read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows:
        return [], []

    headers = [str(c) if c is not None else f"col_{i}" for i, c in enumerate(rows[0])]
    result = [{headers[i]: (row[i] if i < len(row) else None) for i in range(len(headers))} for row in rows[1:]]
    return headers, result


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Campaigns
# --------------------------------------------------------------------------- #


@router.post("/campaigns", response_model=CampaignOut)
async def create_campaign(
    payload: CampaignCreate,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    sb = get_supabase()
    # If linked to a job, verify the job belongs to this org
    if payload.job_id:
        job_check = sb.table("jobs").select("id").eq("id", payload.job_id).eq("org_id", current.org_id).execute()
        if not job_check.data:
            raise HTTPException(status_code=404, detail="Job not found")
    row = {
        "org_id": current.org_id,
        "name": payload.name,
        "job_id": payload.job_id,
        "tg_template": payload.tg_template,
        "li_template": payload.li_template,
        "screening_questions": payload.screening_questions,
        "tg_account": payload.tg_account,
        "qualification_note": payload.qualification_note,
        "status": "draft",
    }
    try:
        r = sb.table("outreach_campaigns").insert(row).execute()
        return r.data[0]
    except Exception as e:
        log.exception("create_campaign failed")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/campaigns", response_model=list[dict])
async def list_campaigns(
    current: CurrentUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    from collections import defaultdict, Counter
    sb = get_supabase()
    campaigns_r = sb.table("outreach_campaigns").select("*").eq("org_id", current.org_id).order("created_at", desc=True).limit(200).execute()
    campaigns = list(campaigns_r.data or [])
    if not campaigns:
        return []
    campaign_ids = [c["id"] for c in campaigns]
    leads_r = sb.table("outreach_leads").select("campaign_id,status").eq("org_id", current.org_id).in_("campaign_id", campaign_ids).execute()
    by_campaign: dict[str, list[str]] = defaultdict(list)
    for lead in (leads_r.data or []):
        by_campaign[lead["campaign_id"]].append(lead["status"])
    for c in campaigns:
        statuses = by_campaign.get(c["id"], [])
        counts = Counter(statuses)
        c["total_leads"] = len(statuses)
        c["sent_count"] = sum(counts.get(s, 0) for s in ("sent", "replied", "qualified"))
        c["replied_count"] = counts.get("replied", 0) + counts.get("qualified", 0)
    return campaigns


@router.get("/campaigns/{campaign_id}", response_model=dict)
async def get_campaign(
    campaign_id: str,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    sb = get_supabase()
    r = sb.table("outreach_campaigns").select("*").eq("id", campaign_id).eq("org_id", current.org_id).maybe_single().execute()
    campaign_data = response_data(r)
    if not campaign_data:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign = dict(campaign_data)

    # attach stats
    stats_r = (
        sb.table("outreach_leads")
        .select("status")
        .eq("campaign_id", campaign_id)
        .eq("org_id", current.org_id)
        .execute()
    )
    leads = stats_r.data or []
    from collections import Counter
    counts = Counter(l["status"] for l in leads)
    campaign["stats"] = {
        "total": len(leads),
        "pending": counts.get("pending", 0),
        "sent": counts.get("sent", 0),
        "replied": counts.get("replied", 0),
        "qualified": counts.get("qualified", 0),
        "rejected": counts.get("rejected", 0),
        "skipped": counts.get("skipped", 0),
    }
    return campaign


@router.patch("/campaigns/{campaign_id}")
async def update_campaign(
    campaign_id: str,
    payload: CampaignUpdate,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Update campaign name or status (e.g. pause/resume)."""
    sb = get_supabase()
    updates: dict[str, Any] = {"updated_at": _now_iso()}
    if payload.name is not None:
        updates["name"] = payload.name
    if payload.status is not None:
        if payload.status not in ("draft", "active", "paused", "done"):
            raise HTTPException(status_code=400, detail="status must be draft|active|paused|done")
        updates["status"] = payload.status
    check = sb.table("outreach_campaigns").select("id").eq("id", campaign_id).eq("org_id", current.org_id).limit(1).execute()
    if not (check.data):
        raise HTTPException(status_code=404, detail="Campaign not found")
    r = sb.table("outreach_campaigns").update(updates).eq("id", campaign_id).eq("org_id", current.org_id).execute()
    return r.data[0] if r.data else {"id": campaign_id, **updates}


@router.delete("/campaigns/{campaign_id}")
async def delete_campaign(
    campaign_id: str,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Delete a campaign and all its leads + messages."""
    sb = get_supabase()
    check = sb.table("outreach_campaigns").select("id").eq("id", campaign_id).eq("org_id", current.org_id).limit(1).execute()
    if not (check.data):
        raise HTTPException(status_code=404, detail="Campaign not found")
    leads_r = sb.table("outreach_leads").select("id").eq("campaign_id", campaign_id).eq("org_id", current.org_id).execute()
    lead_ids = [l["id"] for l in (leads_r.data or [])]
    for lid in lead_ids:
        sb.table("outreach_messages").delete().eq("lead_id", lid).eq("org_id", current.org_id).execute()
    sb.table("outreach_leads").delete().eq("campaign_id", campaign_id).eq("org_id", current.org_id).execute()
    sb.table("outreach_campaigns").delete().eq("id", campaign_id).eq("org_id", current.org_id).execute()
    return {"deleted": campaign_id}


@router.post("/campaigns/{campaign_id}/start")
async def start_campaign(
    campaign_id: str,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    from app.tasks.outreach import send_campaign_batch  # local import to avoid circulars

    sb = get_supabase()
    r = sb.table("outreach_campaigns").select("id, status").eq("id", campaign_id).eq("org_id", current.org_id).maybe_single().execute()
    if not response_data(r):
        raise HTTPException(status_code=404, detail="Campaign not found")

    sb.table("outreach_campaigns").update({"status": "active", "updated_at": _now_iso()}).eq(
        "id", campaign_id
    ).eq("org_id", current.org_id).execute()

    task = send_campaign_batch.delay(campaign_id)
    return {"campaign_id": campaign_id, "task_id": task.id, "status": "queued"}


# --------------------------------------------------------------------------- #
# XLSX import / preview
# --------------------------------------------------------------------------- #


@router.post("/leads/preview-xlsx")
async def preview_xlsx(
    file: UploadFile = File(...),
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    data = await file.read()
    try:
        columns, rows = _parse_xlsx_bytes(data, file.filename or "")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse XLSX: {e}")

    sample_rows = rows[:5]
    mapped_fields = _detect_columns(columns, sample_rows)

    return {"columns": columns, "sample_rows": sample_rows, "mapped_fields": mapped_fields}


@router.post("/campaigns/{campaign_id}/import-xlsx")
async def import_xlsx(
    campaign_id: str,
    file: UploadFile = File(...),
    column_map: Optional[str] = Query(None, description="JSON string overriding auto-detected column mapping"),
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    sb = get_supabase()
    r = sb.table("outreach_campaigns").select("id").eq("id", campaign_id).eq("org_id", current.org_id).maybe_single().execute()
    if not response_data(r):
        raise HTTPException(status_code=404, detail="Campaign not found")

    data = await file.read()
    try:
        columns, rows = _parse_xlsx_bytes(data, file.filename or "")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse XLSX: {e}")

    if column_map:
        try:
            mapping: dict[str, Any] = json.loads(column_map)
        except Exception:
            raise HTTPException(status_code=400, detail="column_map is not valid JSON")
    else:
        mapping = _detect_columns(columns, rows)

        # Heuristic fallback for common column names if LLM failed
        if not mapping.get("linkedin_url"):
            for c in columns:
                if "linkedin" in c.lower():
                    mapping["linkedin_url"] = c
                    break
        if not mapping.get("telegram_url"):
            for c in columns:
                if "telegram" in c.lower() or "tg" in c.lower():
                    mapping["telegram_url"] = c
                    break

    def _get(row: dict[str, Any], field: str) -> Any:
        col = mapping.get(field)
        return row.get(col) if col else None

    leads_to_insert = []
    for row in rows:
        score_raw = _get(row, "score")
        try:
            score_int: Optional[int] = int(float(str(score_raw))) if score_raw not in (None, "") else None
        except (ValueError, TypeError):
            score_int = None

        tg_url = _get(row, "telegram_url")
        li_url = _get(row, "linkedin_url")
        # Prefer telegram when both are present; fall back to linkedin; default telegram
        preferred_channel = (
            "telegram" if tg_url
            else "linkedin" if li_url
            else "telegram"
        )
        
        full_name = _get(row, "full_name")
        if not full_name:
            # Fallback for split First/Last name
            fname = row.get("First Name") or row.get("first_name") or row.get("FirstName") or row.get("first name") or ""
            lname = row.get("Last Name") or row.get("last_name") or row.get("LastName") or row.get("last name") or ""
            if fname or lname:
                full_name = f"{fname} {lname}".strip()

        leads_to_insert.append(
            {
                "org_id": current.org_id,
                "campaign_id": campaign_id,
                "full_name": full_name,
                "linkedin_url": li_url,
                "telegram_url": tg_url,
                "headline": _get(row, "headline"),
                "email": _get(row, "email"),
                "score": score_int,
                "source": "file",
                "status": "pending",
                "preferred_channel": preferred_channel,
            }
        )

    inserted = 0
    for i in range(0, len(leads_to_insert), 250):
        chunk = leads_to_insert[i : i + 250]
        res = sb.table("outreach_leads").insert(chunk).execute()
        inserted += len(res.data or [])

    return {"imported": inserted, "total_rows": len(rows)}


# --------------------------------------------------------------------------- #
# Leads
# --------------------------------------------------------------------------- #


@router.get("/campaigns/{campaign_id}/leads")
async def list_leads(
    campaign_id: str,
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(500, le=2000),
    current: CurrentUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    sb = get_supabase()
    q = sb.table("outreach_leads").select("*").eq("campaign_id", campaign_id).eq("org_id", current.org_id)
    if status:
        q = q.eq("status", status)
    if source:
        q = q.eq("source", source)
    if search:
        q = q.ilike("full_name", f"%{search}%")
    r = q.order("created_at", desc=True).limit(limit).execute()
    return r.data or []


@router.patch("/leads/{lead_id}")
async def update_lead(
    lead_id: str,
    payload: LeadStatusUpdate,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    sb = get_supabase()
    updates: dict[str, Any] = {"updated_at": _now_iso()}
    if payload.status:
        updates["status"] = payload.status
    if payload.preferred_channel:
        updates["preferred_channel"] = payload.preferred_channel
    r = sb.table("outreach_leads").update(updates).eq("id", lead_id).eq("org_id", current.org_id).execute()
    if not r.data:
        raise HTTPException(status_code=404, detail="Lead not found")
    return r.data[0]


@router.post("/leads/{lead_id}/send")
async def send_to_lead(
    lead_id: str,
    payload: Optional[SendOnePayload] = None,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Compose + send a message to one lead right now."""
    sb = get_supabase()

    lead_r = sb.table("outreach_leads").select("*").eq("id", lead_id).eq("org_id", current.org_id).maybe_single().execute()
    lead = response_data(lead_r)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    campaign_r = (
        sb.table("outreach_campaigns")
        .select("*")
        .eq("id", lead["campaign_id"])
        .eq("org_id", current.org_id)
        .maybe_single()
        .execute()
    )
    campaign = response_data(campaign_r)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    channel = (payload.channel if payload else None) or lead.get("preferred_channel") or "telegram"

    # Fetch job for context (optional — may be null)
    job: dict[str, Any] = {}
    if campaign.get("job_id"):
        job_r = (
            sb.table("jobs")
            .select("title, description, skills, geo, seniority")
            .eq("id", campaign["job_id"])
            .eq("org_id", current.org_id)
            .maybe_single()
            .execute()
        )
        if job_r.data:
            job = job_r.data

    template = campaign.get("tg_template") if channel == "telegram" else campaign.get("li_template")
    if not template:
        raise HTTPException(status_code=400, detail=f"No {channel} template set on campaign")

    from app.outreach.composer import compose_message
    from app.outreach.sender import send_linkedin_playwright, send_telegram

    message = compose_message(template=template, candidate=lead, job=job, channel=channel)

    if channel == "telegram":
        tg_url = lead.get("telegram_url")
        if not tg_url:
            raise HTTPException(status_code=400, detail="Lead has no telegram_url")
        result = send_telegram(tg_url, message)
    else:
        li_url = lead.get("linkedin_url")
        if not li_url:
            raise HTTPException(status_code=400, detail="Lead has no linkedin_url")
        result = send_linkedin_playwright(li_url, message)

    now = _now_iso()
    if result["success"]:
        sb.table("outreach_leads").update(
            {"status": "sent", "last_message": message, "last_message_at": now, "updated_at": now}
        ).eq("id", lead_id).eq("org_id", current.org_id).execute()
        sb.table("outreach_messages").insert(
            {
                "org_id": current.org_id,
                "lead_id": lead_id,
                "direction": "sent",
                "channel": channel,
                "text": message,
                "is_auto": True,
            }
        ).execute()

    return {**result, "message": message, "channel": channel}


# --------------------------------------------------------------------------- #
# Conversations / inbox
# --------------------------------------------------------------------------- #


@router.delete("/leads/{lead_id}")
async def delete_lead(
    lead_id: str,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Delete a lead and all its messages."""
    sb = get_supabase()
    check = sb.table("outreach_leads").select("id").eq("id", lead_id).eq("org_id", current.org_id).limit(1).execute()
    if not (check.data):
        raise HTTPException(status_code=404, detail="Lead not found")
    sb.table("outreach_messages").delete().eq("lead_id", lead_id).eq("org_id", current.org_id).execute()
    sb.table("outreach_leads").delete().eq("id", lead_id).eq("org_id", current.org_id).execute()
    return {"deleted": lead_id}


@router.get("/inbox")
async def list_inbox(
    limit: int = Query(100, le=500),
    current: CurrentUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Alias for /conversations — all leads with at least one message."""
    sb = get_supabase()
    r = (
        sb.table("outreach_leads")
        .select("*")
        .eq("org_id", current.org_id)
        .not_.is_("last_message_at", "null")
        .not_.like("last_message", "[ERROR]%")
        .order("last_message_at", desc=True)
        .limit(limit)
        .execute()
    )
    return r.data or []


@router.get("/conversations")
async def list_conversations(
    limit: int = Query(100, le=500),
    current: CurrentUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """All leads that have at least one message, sorted by latest message descending."""
    sb = get_supabase()
    r = (
        sb.table("outreach_leads")
        .select("*")
        .eq("org_id", current.org_id)
        .not_.is_("last_message_at", "null")
        .order("last_message_at", desc=True)
        .limit(limit)
        .execute()
    )
    return r.data or []


@router.get("/conversations/{lead_id}/messages")
async def get_conversation(
    lead_id: str,
    current: CurrentUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    sb = get_supabase()
    r = (
        sb.table("outreach_messages")
        .select("*")
        .eq("lead_id", lead_id)
        .eq("org_id", current.org_id)
        .order("created_at", desc=False)
        .execute()
    )
    return r.data or []


@router.post("/conversations/{lead_id}/reply")
async def send_reply(
    lead_id: str,
    payload: ManualReply,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Send a manual reply to a lead and record it."""
    sb = get_supabase()
    lead_r = sb.table("outreach_leads").select("*").eq("id", lead_id).eq("org_id", current.org_id).maybe_single().execute()
    lead = response_data(lead_r)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    from app.outreach.sender import send_linkedin_playwright, send_telegram

    if payload.channel == "telegram":
        tg_url = lead.get("telegram_url")
        if not tg_url:
            raise HTTPException(status_code=400, detail="Lead has no telegram_url")
        result = send_telegram(tg_url, payload.text)
    elif payload.channel == "linkedin":
        li_url = lead.get("linkedin_url")
        if not li_url:
            raise HTTPException(status_code=400, detail="Lead has no linkedin_url")
        result = send_linkedin_playwright(li_url, payload.text)
    else:
        raise HTTPException(status_code=400, detail="channel must be telegram or linkedin")

    now = _now_iso()
    if result["success"]:
        sb.table("outreach_leads").update(
            {"last_message": payload.text, "last_message_at": now, "updated_at": now}
        ).eq("id", lead_id).eq("org_id", current.org_id).execute()
        sb.table("outreach_messages").insert(
            {
                "org_id": current.org_id,
                "lead_id": lead_id,
                "direction": "sent",
                "channel": payload.channel,
                "text": payload.text,
                "is_auto": False,
            }
        ).execute()

    return {**result, "channel": payload.channel}


# --------------------------------------------------------------------------- #
# Phase 3: Copilot / Autopilot — mode toggle, draft review, needs-review queue
# --------------------------------------------------------------------------- #


@router.patch("/campaigns/{campaign_id}/mode")
async def set_campaign_mode(
    campaign_id: str,
    payload: OutreachModeUpdate,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Toggle the outreach mode for a campaign between 'copilot' and 'autopilot'."""
    if payload.outreach_mode not in ("copilot", "autopilot"):
        raise HTTPException(status_code=400, detail="outreach_mode must be 'copilot' or 'autopilot'")
    sb = get_supabase()
    r = (
        sb.table("outreach_campaigns")
        .update({"outreach_mode": payload.outreach_mode, "updated_at": _now_iso()})
        .eq("id", campaign_id)
        .eq("org_id", current.org_id)
        .execute()
    )
    if not r.data:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return {"campaign_id": campaign_id, "outreach_mode": payload.outreach_mode}


@router.get("/campaigns/{campaign_id}/needs-review")
async def list_needs_review(
    campaign_id: str,
    limit: int = Query(100, le=500),
    current: CurrentUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Return all leads in this campaign that have a Copilot draft awaiting approval."""
    sb = get_supabase()
    r = (
        sb.table("outreach_leads")
        .select("*")
        .eq("campaign_id", campaign_id)
        .eq("org_id", current.org_id)
        .eq("needs_review", True)
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return r.data or []


@router.post("/leads/{lead_id}/approve-draft")
async def approve_draft(
    lead_id: str,
    payload: DraftEdit,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Approve a Copilot AI draft (optionally edit it) and send it."""
    sb = get_supabase()
    lead_r = sb.table("outreach_leads").select("*").eq("id", lead_id).eq("org_id", current.org_id).maybe_single().execute()
    lead = response_data(lead_r)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if not lead.get("needs_review"):
        raise HTTPException(status_code=400, detail="This lead has no pending draft to approve")

    # Use edited text if provided, otherwise use the stored AI draft
    text_to_send = (payload.text or "").strip() or lead.get("ai_draft") or ""
    if not text_to_send:
        raise HTTPException(status_code=400, detail="No draft text available to send")

    channel = payload.channel or lead.get("preferred_channel") or "telegram"

    from app.outreach.sender import send_linkedin_playwright, send_telegram

    if channel == "telegram":
        tg_url = lead.get("telegram_url")
        if not tg_url:
            raise HTTPException(status_code=400, detail="Lead has no telegram_url")
        result = send_telegram(tg_url, text_to_send)
    else:
        li_url = lead.get("linkedin_url")
        if not li_url:
            raise HTTPException(status_code=400, detail="Lead has no linkedin_url")
        result = send_linkedin_playwright(li_url, text_to_send)

    now = _now_iso()
    if result["success"]:
        sb.table("outreach_messages").insert(
            {
                "org_id": current.org_id,
                "lead_id": lead_id,
                "direction": "sent",
                "channel": channel,
                "text": text_to_send,
                "is_auto": True,
            }
        ).execute()
        new_status = "rejected" if lead.get("ai_intent") == "declined" else "replied"
        sb.table("outreach_leads").update(
            {
                "needs_review": False,
                "ai_draft": text_to_send,  # store the final (possibly edited) version
                "status": new_status,
                "last_message": text_to_send,
                "last_message_at": now,
                "updated_at": now,
            }
        ).eq("id", lead_id).eq("org_id", current.org_id).execute()
    return {**result, "channel": channel, "text": text_to_send}


@router.post("/leads/{lead_id}/reject-draft")
async def reject_draft(
    lead_id: str,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Discard the AI draft without sending. Clears needs_review so the lead
    goes back to a clean state for manual follow-up."""
    sb = get_supabase()
    r = (
        sb.table("outreach_leads")
        .update({"needs_review": False, "ai_draft": None, "updated_at": _now_iso()})
        .eq("id", lead_id)
        .eq("org_id", current.org_id)
        .execute()
    )
    if not r.data:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"lead_id": lead_id, "draft_rejected": True}
