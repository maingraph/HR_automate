"""Celery execution for independently runnable, gated pipeline stages."""
from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.db import get_supabase
from app.core.logging import get_logger
from app.services import datasets as dataset_service
from app.services import stages as stage_service


log = get_logger(__name__)


def _stage(stage_id: str) -> dict[str, Any]:
    result = get_supabase().table("stage_runs").select("*").eq("id", stage_id).maybe_single().execute()
    if not result.data:
        raise RuntimeError(f"Stage {stage_id} not found")
    return result.data


def _job(stage: dict[str, Any]) -> dict[str, Any]:
    result = get_supabase().table("jobs").select("*").eq("id", stage["job_id"]).maybe_single().execute()
    if not result.data:
        raise RuntimeError(f"Job {stage['job_id']} not found")
    return result.data


def _publish(stage: dict[str, Any], event: str, **data: Any) -> None:
    payload = {"type": event, "stage_id": stage["id"], "stage_type": stage["stage_type"], **data}
    try:
        get_supabase()  # Ensure DB errors and pub/sub errors remain independent.
        from app.core.db import get_redis
        get_redis().publish(f"ws:job:{stage['job_id']}", json.dumps(payload, default=str))
    except Exception:
        log.exception("Failed to publish workflow event")


def _set_stage(stage: dict[str, Any], **updates: Any) -> dict[str, Any]:
    result = get_supabase().table("stage_runs").update(updates).eq("id", stage["id"]).eq(
        "org_id", stage["org_id"]
    ).execute()
    return result.data[0]


def _set_browser_state(session_id: str, org_id: str, state: str, **updates: Any) -> None:
    get_supabase().table("browser_sessions").update({"state": state, **updates}).eq(
        "id", session_id
    ).eq("org_id", org_id).execute()


def _ensure_output(
    stage: dict[str, Any], *, name: str, kind: str, capabilities: list[str]
) -> dict[str, Any]:
    if stage.get("output_dataset_id"):
        existing = dataset_service.get_dataset(stage["output_dataset_id"], stage["org_id"])
        if existing:
            return existing
    dataset = dataset_service.create_dataset(
        org_id=stage["org_id"],
        job_id=stage["job_id"],
        name=name,
        kind=kind,
        capabilities=capabilities,
        parent_ids=stage.get("input_dataset_ids") or [],
        state="partial" if stage["stage_type"].endswith("_extract") else "draft",
        metadata={"stage_run_id": stage["id"], "attempt": stage.get("attempt", 1)},
    )
    _set_stage(stage, output_dataset_id=dataset["id"])
    stage["output_dataset_id"] = dataset["id"]
    return dataset


def _input_payloads(stage: dict[str, Any]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for dataset_id in stage.get("input_dataset_ids") or []:
        page = dataset_service.list_records(dataset_id, stage["org_id"], limit=2000, included=True)
        payloads.extend(record.get("payload") or {} for record in page["records"])
    return payloads


def _control(stage: dict[str, Any], dataset_id: str | None = None) -> bool:
    current = _stage(stage["id"])
    if current["status"] == "pause_requested":
        if dataset_id:
            dataset_service.mark_dataset(dataset_id, stage["org_id"], "partial")
        stage_service.transition_stage(stage["id"], stage["org_id"], "paused")
        _publish(stage, "stage.status", status="paused")
        return True
    if current["status"] == "stopped":
        if dataset_id:
            dataset_service.mark_dataset(dataset_id, stage["org_id"], "partial")
        _publish(stage, "stage.status", status="stopped")
        return True
    return False


def _flush(
    stage: dict[str, Any], dataset_id: str, payloads: list[dict[str, Any]],
    current: int, total: int, **checkpoint: Any,
) -> bool:
    if payloads:
        dataset_service.append_records(dataset_id, stage["org_id"], payloads, start_position=current - len(payloads))
        for payload in payloads:
            _publish(stage, "dataset.record_added", dataset_id=dataset_id, candidate=payload)
    stage_service.set_progress(stage["id"], stage["org_id"], current, total, **checkpoint)
    _publish(stage, "stage.progress", current=current, total=total, dataset_id=dataset_id)
    return _control(stage, dataset_id)


def _run_salesnav(stage: dict[str, Any], job: dict[str, Any]) -> str:
    dataset = _ensure_output(
        stage,
        name=f"{job['title']} — Sales Navigator",
        kind="salesnav_raw",
        capabilities=["normalized", "source:salesnav"],
    )
    session_id = (stage.get("config") or {}).get("browser_session_id")
    if not session_id:
        raise ValueError("salesnav_extract requires browser_session_id")
    checkpoint = stage.get("checkpoint") or {}
    config = stage.get("config") or {}
    cursor = checkpoint.get("cursor") or {
        "max_pages": int(config.get("max_pages", 10)),
        "max_profiles": int(config.get("max_profiles", 200)),
    }
    while True:
        if _control(stage, dataset["id"]):
            return "paused"
        with httpx.Client(timeout=120) as client:
            response = client.post(
                f"{settings.browser_agent_url}/sessions/extract/next",
                headers={"X-Browser-Agent-Token": settings.browser_agent_token},
                json={"session_id": session_id, "cursor": cursor},
            )
        response.raise_for_status()
        result = response.json()
        if result.get("auth_required"):
            _set_browser_state(session_id, stage["org_id"], "awaiting_auth", current_url=result.get("current_url"))
            stage_service.transition_stage(stage["id"], stage["org_id"], "awaiting_auth")
            _publish(stage, "browser.auth_required", browser_session_id=session_id)
            return "awaiting_auth"
        cursor = result.get("cursor") or cursor
        profile = result.get("profile")
        current = int(result.get("current") or 0)
        total = int(result.get("total") or 0)
        if profile:
            from app.tasks.pipeline import _salesnav_to_candidate
            profile = _salesnav_to_candidate(profile)
            if _flush(stage, dataset["id"], [profile], current, total, cursor=cursor):
                return "paused"
        if result.get("done"):
            break
    dataset_service.mark_dataset(dataset["id"], stage["org_id"], "draft")
    return "ready"


def _run_telegram(stage: dict[str, Any], job: dict[str, Any]) -> str:
    from app.scrapers.telegram import scrape_channels

    dataset = _ensure_output(
        stage, name=f"{job['title']} — Telegram", kind="telegram_raw",
        capabilities=["normalized", "source:telegram"],
    )
    config = stage.get("config") or {}
    rows = scrape_channels(
        config.get("channels") or job.get("tg_channels") or [],
        config.get("keywords") or job.get("tg_keywords") or [],
        days_back=int(config.get("days_back", 60)),
        per_channel_limit=int(config.get("per_channel_limit", 1000)),
    )
    for index in range(0, len(rows), 25):
        chunk = rows[index:index + 25]
        if _flush(stage, dataset["id"], chunk, index + len(chunk), len(rows), offset=index + len(chunk)):
            return "paused"
    dataset_service.mark_dataset(dataset["id"], stage["org_id"], "draft")
    return "ready"


def _run_apollo(stage: dict[str, Any], job: dict[str, Any]) -> str:
    from app.scrapers.apollo import scrape_apollo

    dataset = _ensure_output(
        stage, name=f"{job['title']} — Apollo", kind="apollo_raw",
        capabilities=["normalized", "source:apollo"],
    )
    config = stage.get("config") or {}
    rows = scrape_apollo(
        keywords=config.get("keywords") or " ".join([job.get("title") or ""] + (job.get("skills") or [])[:5]),
        titles=config.get("titles") or ([job.get("title")] if job.get("title") else None),
        geo=config.get("geo") or job.get("geo"),
        max_results=int(config.get("max_results", 50)),
    )
    for index in range(0, len(rows), 25):
        chunk = rows[index:index + 25]
        if _flush(stage, dataset["id"], chunk, index + len(chunk), len(rows), offset=index + len(chunk)):
            return "paused"
    dataset_service.mark_dataset(dataset["id"], stage["org_id"], "draft")
    return "ready"


def _run_merge(stage: dict[str, Any], job: dict[str, Any]) -> str:
    from app.services.dedup import dedup

    rows = dedup(_input_payloads(stage))
    dataset = _ensure_output(
        stage, name=f"{job['title']} — merged", kind="merged",
        capabilities=["normalized", "merged", "deduplicated"],
    )
    _flush(stage, dataset["id"], rows, len(rows), len(rows), complete=True)
    return "ready"


def _run_enrich(stage: dict[str, Any], job: dict[str, Any]) -> str:
    rows = _input_payloads(stage)
    dataset = _ensure_output(
        stage, name=f"{job['title']} — enriched", kind="enriched",
        capabilities=["normalized", "enriched"],
    )
    config = stage.get("config") or {}
    provider = config.get("provider", "apify")
    if provider == "local":
        session_id = config.get("browser_session_id")
        if not session_id:
            raise ValueError("Local enrichment requires browser_session_id")
        start = int((stage.get("checkpoint") or {}).get("offset", 0))
        with httpx.Client(timeout=120) as client:
            for index in range(start, len(rows)):
                row = rows[index]
                url = row.get("linkedin_url")
                if _control(stage, dataset["id"]):
                    return "paused"
                if not url:
                    if _flush(stage, dataset["id"], [row], index + 1, len(rows), offset=index + 1):
                        return "paused"
                    continue
                response = client.post(
                    f"{settings.browser_agent_url}/sessions/profile",
                    headers={"X-Browser-Agent-Token": settings.browser_agent_token},
                    json={"session_id": session_id, "url": url},
                )
                response.raise_for_status()
                mapped = response.json()
                if mapped.get("auth_required"):
                    _set_browser_state(session_id, stage["org_id"], "awaiting_auth", current_url=mapped.get("current_url"))
                    stage_service.transition_stage(stage["id"], stage["org_id"], "awaiting_auth")
                    _publish(stage, "browser.auth_required", browser_session_id=session_id)
                    return "awaiting_auth"
                match = mapped.get("profile") or {}
                output = {**row, **match, "scan_depth": 2 if match else row.get("scan_depth", 1)}
                if _flush(stage, dataset["id"], [output], index + 1, len(rows), offset=index + 1, url=url):
                    return "paused"
        return "ready"
    else:
        from app.scrapers.linkedin_deep import scrape_profiles_deep
        urls = [row["linkedin_url"] for row in rows if row.get("linkedin_url")]
        enriched = scrape_profiles_deep(urls)
    by_url = {(row.get("linkedin_url") or "").rstrip("/").lower(): row for row in enriched}
    output = []
    for row in rows:
        match = by_url.get((row.get("linkedin_url") or "").rstrip("/").lower())
        output.append({**row, **(match or {}), "scan_depth": 2 if match else row.get("scan_depth", 1)})
    _flush(stage, dataset["id"], output, len(output), len(output), complete=True)
    return "ready"


def _run_rules(stage: dict[str, Any], job: dict[str, Any]) -> str:
    from app.utils.geo_filter import is_geo_excluded

    rows = _input_payloads(stage)
    exclusions = (stage.get("config") or {}).get("geo_exclude") or job.get("geo_exclude") or []
    output = []
    for row in rows:
        excluded, reason = is_geo_excluded(row, exclusions)
        output.append({
            **row,
            "included": not excluded,
            "red_flags": list({*(row.get("red_flags") or []), *([reason] if reason else [])}),
        })
    dataset = _ensure_output(
        stage, name=f"{job['title']} — rule filtered", kind="filtered",
        capabilities=["normalized", "rules_filtered"],
    )
    _flush(stage, dataset["id"], output, len(output), len(output), complete=True)
    return "ready"


def _run_similarity(stage: dict[str, Any], job: dict[str, Any]) -> str:
    from app.scoring.pipeline import stage1_embed_filter

    rows = stage1_embed_filter(job, _input_payloads(stage), drop_bottom_pct=0.0)
    for row in rows:
        row.pop("embedding", None)
    dataset = _ensure_output(
        stage, name=f"{job['title']} — similarity", kind="similarity",
        capabilities=["normalized", "similarity"],
    )
    _flush(stage, dataset["id"], rows, len(rows), len(rows), complete=True)
    return "ready"


def _run_grade(stage: dict[str, Any], job: dict[str, Any]) -> str:
    from app.scoring.pipeline import stage2_gemini_score

    rows = _input_payloads(stage)
    dataset = _ensure_output(
        stage, name=f"{job['title']} — graded", kind="graded",
        capabilities=["normalized", "graded"],
    )

    start = int((stage.get("checkpoint") or {}).get("scored", 0))
    remaining = rows[start:]
    flushed = 0

    def checkpoint(current: int, total: int) -> None:
        nonlocal flushed
        completed = remaining[flushed:current]
        if completed:
            dataset_service.append_records(dataset["id"], stage["org_id"], completed, start_position=start + flushed)
            flushed = current
        overall = start + current
        stage_service.set_progress(stage["id"], stage["org_id"], overall, len(rows), scored=overall)
        _publish(stage, "stage.progress", current=overall, total=len(rows), dataset_id=dataset["id"])
        if _control(stage, dataset["id"]):
            raise InterruptedError("Stage paused")

    graded = stage2_gemini_score(
        job, job.get("rubric") or {}, remaining,
        batch_size=int((stage.get("config") or {}).get("batch_size", 5)),
        checkpoint_callback=checkpoint,
    )
    if flushed < len(graded):
        checkpoint(len(graded), len(graded))
    return "ready"


RUNNERS = {
    "salesnav_extract": _run_salesnav,
    "telegram_extract": _run_telegram,
    "apollo_extract": _run_apollo,
    "merge_dedup": _run_merge,
    "profile_enrich": _run_enrich,
    "rules_filter": _run_rules,
    "similarity_analyze": _run_similarity,
    "ai_grade": _run_grade,
}


@celery_app.task(name="sourcer.run_stage", bind=True, time_limit=60 * 120, soft_time_limit=60 * 110)
def run_stage(self, stage_id: str) -> dict[str, Any]:
    stage = _stage(stage_id)
    if stage["status"] == "pending":
        stage = stage_service.transition_stage(stage_id, stage["org_id"], "running")
    elif stage["status"] != "running":
        return {"ok": False, "status": stage["status"]}
    _publish(stage, "stage.status", status="running")
    runner = RUNNERS.get(stage["stage_type"])
    if not runner:
        stage_service.transition_stage(stage_id, stage["org_id"], "awaiting_user")
        return {"ok": True, "status": "awaiting_user"}
    try:
        outcome = runner(stage, _job(stage))
        current = _stage(stage_id)
        if outcome == "ready" and current["status"] == "running":
            stage_service.transition_stage(stage_id, stage["org_id"], "awaiting_user")
            _publish(
                stage, "dataset.ready", dataset_id=_stage(stage_id).get("output_dataset_id"),
                status="awaiting_user",
            )
        return {"ok": True, "status": outcome, "dataset_id": _stage(stage_id).get("output_dataset_id")}
    except InterruptedError:
        return {"ok": True, "status": _stage(stage_id)["status"]}
    except Exception as exc:
        log.exception("Stage %s failed", stage_id)
        current = _stage(stage_id)
        if current["status"] in {"running", "pause_requested", "awaiting_auth"}:
            if current["status"] != "running":
                _set_stage(current, status="running")
            stage_service.transition_stage(stage_id, stage["org_id"], "failed", error=str(exc)[:1000])
        if current.get("output_dataset_id"):
            dataset_service.mark_dataset(current["output_dataset_id"], stage["org_id"], "failed")
        _publish(stage, "stage.status", status="failed", error=str(exc))
        raise
