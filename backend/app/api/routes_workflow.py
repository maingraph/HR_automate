"""Modular pipeline stages, versioned datasets, and interactive browser sessions."""
from __future__ import annotations

import json
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response

from app.core.auth import CurrentUser, get_current_user
from app.core.config import settings
from app.core.db import get_supabase, response_data
from app.schemas.workflow import (
    BrowserFilterApply,
    BrowserOpenSearch,
    BrowserInput,
    BrowserSessionCreate,
    CandidateRecordPatch,
    DatasetOut,
    StageRunCreate,
    StageRunOut,
)
from app.services import datasets as dataset_service
from app.services import stages as stage_service


router = APIRouter(tags=["workflow"])
MAX_IMPORT_BYTES = 50 * 1024 * 1024


async def _read_import(file: UploadFile) -> bytes:
    content = await file.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="Import exceeds 50 MB limit")
    return content


def _job(job_id: str, user: CurrentUser) -> dict[str, Any]:
    result = (
        get_supabase().table("jobs").select("*")
        .eq("id", job_id).eq("org_id", user.org_id).maybe_single().execute()
    )
    job = response_data(result)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValueError):
        status = 409 if "transition" in str(exc).lower() or "editable" in str(exc).lower() else 400
        return HTTPException(status_code=status, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


def _dispatch(stage_id: str) -> str:
    from app.tasks.workflow import run_stage

    task = run_stage.delay(stage_id)
    get_supabase().table("stage_runs").update({"celery_task_id": task.id}).eq("id", stage_id).execute()
    return task.id


def _publish_browser(job_id: str, session_id: str, event: str, **data: Any) -> None:
    try:
        from app.core.db import get_redis
        get_redis().publish(
            f"ws:job:{job_id}",
            json.dumps({"type": event, "browser_session_id": session_id, **data}),
        )
    except Exception:
        pass


@router.post("/jobs/{job_id}/stage-runs", response_model=StageRunOut)
async def create_stage_run(
    job_id: str,
    payload: StageRunCreate,
    current: CurrentUser = Depends(get_current_user),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    job = _job(job_id, current)
    # A zero-row Telegram dataset is only useful when the configured channels
    # were actually scanned.  Do not silently create one when the source scope
    # was never supplied.
    if payload.stage_type == "telegram_extract":
        channels = payload.config.get("channels") or job.get("tg_channels") or []
        if not channels:
            raise HTTPException(
                status_code=422,
                detail="Telegram needs at least one public or joined channel. Add @channel handles before starting extraction.",
            )
    try:
        stage, created = stage_service.create_stage(
            org_id=current.org_id,
            job_id=job_id,
            stage_type=payload.stage_type,
            input_dataset_ids=payload.input_dataset_ids,
            config=payload.config,
            idempotency_key=idempotency_key,
        )
        if created and payload.start:
            _dispatch(stage["id"])
        return stage
    except Exception as exc:
        raise _http_error(exc)


@router.get("/jobs/{job_id}/stage-runs", response_model=list[StageRunOut])
async def get_stage_runs(
    job_id: str,
    current: CurrentUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    _job(job_id, current)
    return stage_service.list_stages(job_id, current.org_id)


@router.get("/jobs/{job_id}/datasets", response_model=list[DatasetOut])
async def get_job_datasets(
    job_id: str,
    current: CurrentUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    _job(job_id, current)
    return dataset_service.list_datasets(job_id, current.org_id)


@router.post("/stage-runs/{stage_id}/pause", response_model=StageRunOut)
async def pause_stage(stage_id: str, current: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    try:
        return stage_service.request_control(stage_id, current.org_id, "pause")
    except Exception as exc:
        raise _http_error(exc)


@router.post("/stage-runs/{stage_id}/resume", response_model=StageRunOut)
async def resume_stage(stage_id: str, current: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    try:
        stage = stage_service.transition_stage(stage_id, current.org_id, "running")
        _dispatch(stage_id)
        return stage
    except Exception as exc:
        raise _http_error(exc)


@router.post("/stage-runs/{stage_id}/stop", response_model=StageRunOut)
async def stop_stage(stage_id: str, current: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    try:
        stage = stage_service.request_control(stage_id, current.org_id, "stop")
        if stage.get("output_dataset_id"):
            dataset_service.mark_dataset(stage["output_dataset_id"], current.org_id, "partial")
        return stage
    except Exception as exc:
        raise _http_error(exc)


@router.post("/stage-runs/{stage_id}/skip", response_model=StageRunOut)
async def skip_stage(stage_id: str, current: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    try:
        return stage_service.request_control(stage_id, current.org_id, "skip")
    except Exception as exc:
        raise _http_error(exc)


@router.post("/stage-runs/{stage_id}/rerun", response_model=StageRunOut)
async def rerun_stage(
    stage_id: str,
    current: CurrentUser = Depends(get_current_user),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    original = stage_service.get_stage(stage_id, current.org_id)
    if not original:
        raise HTTPException(status_code=404, detail="Stage run not found")
    try:
        stage, created = stage_service.create_stage(
            org_id=current.org_id,
            job_id=original["job_id"],
            stage_type=original["stage_type"],
            input_dataset_ids=original.get("input_dataset_ids") or [],
            config={**(original.get("config") or {}), "rerun_of": stage_id},
            idempotency_key=idempotency_key,
            attempt=int(original.get("attempt") or 1) + 1,
        )
        if created:
            _dispatch(stage["id"])
        return stage
    except Exception as exc:
        raise _http_error(exc)


@router.post("/stage-runs/{stage_id}/continue", response_model=StageRunOut)
async def continue_stage(stage_id: str, current: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    stage = stage_service.get_stage(stage_id, current.org_id)
    if not stage:
        raise HTTPException(status_code=404, detail="Stage run not found")
    if stage["status"] != "awaiting_user":
        raise HTTPException(status_code=409, detail="Stage is not awaiting user confirmation")
    try:
        if stage.get("output_dataset_id"):
            dataset_service.seal_dataset(stage["output_dataset_id"], current.org_id)
        completed = stage_service.transition_stage(stage_id, current.org_id, "completed")
        if stage["stage_type"] == "ai_grade":
            get_supabase().table("jobs").update({"status": "done"}).eq(
                "id", stage["job_id"]
            ).eq("org_id", current.org_id).execute()
        return completed
    except Exception as exc:
        raise _http_error(exc)


@router.post("/datasets/import/preview")
async def preview_dataset_import(
    file: UploadFile = File(...),
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        payloads, manifest = dataset_service.parse_import(await _read_import(file), file.filename or "")
        return {
            "valid": True,
            "row_count": len(payloads),
            "columns": sorted({key for row in payloads[:50] for key in row}),
            "sample": payloads[:5],
            "manifest": manifest,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/datasets/import", response_model=DatasetOut)
async def import_dataset(
    job_id: str = Query(...),
    name: Optional[str] = Query(None),
    kind: str = Query("imported"),
    parent_ids: str = Query("[]"),
    file: UploadFile = File(...),
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    _job(job_id, current)
    try:
        parents = json.loads(parent_ids)
        payloads, manifest = dataset_service.parse_import(await _read_import(file), file.filename or "")
        dataset = dataset_service.create_dataset(
            org_id=current.org_id,
            job_id=job_id,
            name=name or file.filename or "Imported dataset",
            kind=kind,
            parent_ids=parents,
            capabilities=["normalized", "imported"],
            metadata={"import_manifest": manifest, "filename": file.filename},
        )
        dataset_service.append_records(dataset["id"], current.org_id, payloads)
        stage, _ = stage_service.create_stage(
            org_id=current.org_id,
            job_id=job_id,
            stage_type="file_import",
            input_dataset_ids=[],
            config={"filename": file.filename, "row_count": len(payloads)},
            idempotency_key=None,
        )
        stage_service.transition_stage(stage["id"], current.org_id, "running")
        get_supabase().table("stage_runs").update({
            "output_dataset_id": dataset["id"],
            "progress": {"current": len(payloads), "total": len(payloads), "percentage": 100},
        }).eq("id", stage["id"]).eq("org_id", current.org_id).execute()
        stage_service.transition_stage(stage["id"], current.org_id, "awaiting_user")
        return dataset_service.get_dataset(dataset["id"], current.org_id)
    except Exception as exc:
        raise _http_error(exc)


@router.get("/datasets/{dataset_id}", response_model=DatasetOut)
async def get_dataset(dataset_id: str, current: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    dataset = dataset_service.get_dataset(dataset_id, current.org_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


@router.get("/datasets/{dataset_id}/records")
async def get_dataset_records(
    dataset_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = Query(None),
    included: Optional[bool] = Query(None),
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return dataset_service.list_records(
            dataset_id, current.org_id, offset=offset, limit=limit, search=search, included=included
        )
    except Exception as exc:
        raise _http_error(exc)


@router.patch("/datasets/{dataset_id}/records/{record_id}")
async def update_dataset_record(
    dataset_id: str,
    record_id: str,
    payload: CandidateRecordPatch,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return dataset_service.patch_record(
            dataset_id, record_id, current.org_id, payload.model_dump(exclude_none=True)
        )
    except Exception as exc:
        raise _http_error(exc)


@router.delete("/datasets/{dataset_id}/records/{record_id}", response_model=DatasetOut)
async def delete_dataset_record(
    dataset_id: str,
    record_id: str,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return dataset_service.delete_record(dataset_id, record_id, current.org_id)
    except Exception as exc:
        raise _http_error(exc)


@router.post("/datasets/{dataset_id}/seal", response_model=DatasetOut)
async def seal_dataset(dataset_id: str, current: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    try:
        return dataset_service.seal_dataset(dataset_id, current.org_id)
    except Exception as exc:
        raise _http_error(exc)


@router.get("/datasets/{dataset_id}/export")
async def export_dataset(
    dataset_id: str,
    format: str = Query("xlsx", pattern="^(xlsx|csv|json)$"),
    current: CurrentUser = Depends(get_current_user),
) -> Response:
    try:
        content, media_type, filename = dataset_service.export_dataset(dataset_id, current.org_id, format)
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as exc:
        raise _http_error(exc)


async def _agent_call(path: str, body: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    headers = {"X-Browser-Agent-Token": settings.browser_agent_token}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(f"{settings.browser_agent_url}{path}", json=body or {}, headers=headers)
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Browser agent: {response.text}")
    return response.json()


def _browser_session_for_client(session: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not session:
        return session
    separator = "&" if "?" in settings.browser_viewer_url else "?"
    viewer_url = (
        f"{settings.browser_viewer_url}{separator}"
        f"viewer_token={settings.browser_viewer_token}"
    )
    return {**session, "viewer_url": viewer_url}


def _job_filter_plan(job: dict[str, Any]) -> dict[str, Any]:
    title = (job.get("title") or "").lower()
    if "backend" in title or "back end" in title:
        current_title = "Back End Developer"
    elif "frontend" in title or "front end" in title:
        current_title = "Frontend Developer"
    elif "full stack" in title or "fullstack" in title:
        current_title = "Full Stack Engineer"
    elif "devops" in title:
        current_title = "DevOps Engineer"
    elif "data scientist" in title:
        current_title = "Data Scientist"
    else:
        current_title = job.get("title") or ""

    geo = (job.get("geo") or "").lower()
    if "europe" in geo:
        geography = "Europe"
    elif "emea" in geo:
        geography = "EMEA"
    else:
        geography = (job.get("geo") or "").replace(" remote", "").strip()

    return {
        "keywords": " ".join([
            job.get("title") or "",
            *((job.get("skills") or [])[:3]),
        ]).strip(),
        "current_title": current_title,
        "function": "Engineering",
        "geography": geography,
        "seniority": None,
        "notes": [
            "Remote is not a candidate-location filter; geography uses Europe.",
            "Sales Navigator has no reliable Senior individual-contributor option, so seniority stays in keywords.",
        ],
    }


@router.post("/browser-sessions")
async def create_browser_session(
    payload: BrowserSessionCreate,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    _job(payload.job_id, current)
    existing_response = (
        get_supabase().table("browser_sessions").select("*")
        .eq("job_id", payload.job_id).eq("org_id", current.org_id).maybe_single().execute()
    )
    existing = response_data(existing_response)
    if existing:
        session = existing
    else:
        result = get_supabase().table("browser_sessions").insert({
            "org_id": current.org_id,
            "job_id": payload.job_id,
            "state": "starting",
            "viewer_url": settings.browser_viewer_url,
        }).execute()
        session = result.data[0]
    agent = await _agent_call("/sessions/start", {"session_id": session["id"]})
    updated = get_supabase().table("browser_sessions").update({
        "state": agent.get("state", "ready"),
        "current_url": agent.get("current_url"),
        "viewer_url": settings.browser_viewer_url,
    }).eq("id", session["id"]).execute()
    _publish_browser(payload.job_id, session["id"], "browser.status", state=updated.data[0]["state"])
    return _browser_session_for_client(updated.data[0])


@router.get("/browser-sessions/{session_id}")
async def get_browser_session(
    session_id: str,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    response = (
        get_supabase().table("browser_sessions").select("*")
        .eq("id", session_id).eq("org_id", current.org_id).maybe_single().execute()
    )
    session = response_data(response)
    if not session:
        raise HTTPException(status_code=404, detail="Browser session not found")
    return _browser_session_for_client(session)


@router.get("/jobs/{job_id}/browser-session")
async def get_job_browser_session(
    job_id: str,
    current: CurrentUser = Depends(get_current_user),
) -> Optional[dict[str, Any]]:
    _job(job_id, current)
    response = (
        get_supabase().table("browser_sessions").select("*")
        .eq("job_id", job_id).eq("org_id", current.org_id).maybe_single().execute()
    )
    session = response_data(response)
    if not session:
        return None
    try:
        agent = await _agent_call(
            "/sessions/start",
            {"session_id": session["id"], "url": session.get("current_url")},
        )
        state = "awaiting_auth" if agent.get("awaiting_auth") else session.get("state", "ready")
        updated = get_supabase().table("browser_sessions").update({
            "state": state,
            "current_url": agent.get("current_url") or session.get("current_url"),
        }).eq("id", session["id"]).eq("org_id", current.org_id).execute()
        session = updated.data[0]
    except HTTPException:
        session = {**session, "state": "stopped"}
    return _browser_session_for_client(session)


@router.post("/browser-sessions/{session_id}/open-search")
async def open_browser_search(
    session_id: str,
    payload: BrowserOpenSearch,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    session = await get_browser_session(session_id, current)
    job = _job(session["job_id"], current)
    if payload.url:
        agent = await _agent_call(
            "/sessions/open",
            {"session_id": session_id, "url": payload.url},
        )
    else:
        keyword_parts = [
            job.get("title") or "",
            *((job.get("skills") or [])[:3]),
        ]
        keywords = " ".join(part.strip() for part in keyword_parts if part and part.strip())
        agent = await _agent_call(
            "/sessions/search",
            {"session_id": session_id, "text": keywords},
        )
    state = "awaiting_auth" if agent.get("awaiting_auth") else "manual_control"
    result = get_supabase().table("browser_sessions").update({
        "state": state, "current_url": agent.get("current_url", payload.url)
    }).eq("id", session_id).eq("org_id", current.org_id).execute()
    _publish_browser(session["job_id"], session_id, "browser.url_changed", current_url=result.data[0]["current_url"], state=state)
    return result.data[0]


@router.post("/browser-sessions/{session_id}/input")
async def send_browser_input(
    session_id: str,
    payload: BrowserInput,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    session = await get_browser_session(session_id, current)
    if bool(payload.text) == bool(payload.key):
        raise HTTPException(status_code=400, detail="Provide exactly one of text or key")
    result = await _agent_call(
        "/sessions/input",
        {"session_id": session_id, "text": payload.text, "key": payload.key},
    )
    return {
        "state": session["state"],
        "current_url": result.get("current_url", session.get("current_url")),
    }


@router.get("/browser-sessions/{session_id}/filter-plan")
async def get_browser_filter_plan(
    session_id: str,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    session = await get_browser_session(session_id, current)
    return _job_filter_plan(_job(session["job_id"], current))


@router.post("/browser-sessions/{session_id}/apply-filters")
async def apply_browser_filters(
    session_id: str,
    payload: BrowserFilterApply,
    current: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    if not payload.confirmed:
        raise HTTPException(status_code=409, detail="Filter application requires confirmation")
    session = await get_browser_session(session_id, current)
    plan = _job_filter_plan(_job(session["job_id"], current))
    agent = await _agent_call(
        "/sessions/apply-filters",
        {"session_id": session_id, "cursor": plan},
    )
    state = "awaiting_auth" if agent.get("awaiting_auth") else "manual_control"
    result = get_supabase().table("browser_sessions").update({
        "state": state,
        "current_url": agent.get("current_url", session.get("current_url")),
    }).eq("id", session_id).eq("org_id", current.org_id).execute()
    _publish_browser(
        session["job_id"],
        session_id,
        "browser.url_changed",
        current_url=result.data[0]["current_url"],
        state=state,
    )
    return {
        **_browser_session_for_client(result.data[0]),
        "filter_plan": plan,
        "applied": agent.get("applied", []),
    }


@router.post("/browser-sessions/{session_id}/lock-search")
async def lock_browser_search(session_id: str, current: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    session = await get_browser_session(session_id, current)
    agent = await _agent_call("/sessions/lock", {"session_id": session_id})
    result = get_supabase().table("browser_sessions").update({
        "state": "paused", "current_url": agent["current_url"],
        "locked_search_url": agent["current_url"],
    }).eq("id", session_id).eq("org_id", current.org_id).execute()
    _publish_browser(session["job_id"], session_id, "browser.status", state="paused", locked_search_url=agent["current_url"])
    return result.data[0]


@router.post("/browser-sessions/{session_id}/take-control")
async def take_browser_control(session_id: str, current: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    session = await get_browser_session(session_id, current)
    await _agent_call("/sessions/take-control", {"session_id": session_id})
    result = get_supabase().table("browser_sessions").update({"state": "manual_control"}).eq(
        "id", session_id
    ).eq("org_id", current.org_id).execute()
    _publish_browser(session["job_id"], session_id, "browser.status", state="manual_control")
    return result.data[0]


@router.post("/browser-sessions/{session_id}/release-control")
async def release_browser_control(session_id: str, current: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    session = await get_browser_session(session_id, current)
    await _agent_call("/sessions/release-control", {"session_id": session_id})
    result = get_supabase().table("browser_sessions").update({"state": "paused"}).eq(
        "id", session_id
    ).eq("org_id", current.org_id).execute()
    _publish_browser(session["job_id"], session_id, "browser.status", state="paused")
    return result.data[0]
