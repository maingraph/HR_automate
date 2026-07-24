"""Stage-run lifecycle and transition validation."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.core.db import get_supabase, response_data


STAGE_TYPES = {
    "salesnav_extract", "telegram_extract", "apollo_extract", "file_import",
    "merge_dedup", "profile_enrich", "rules_filter", "similarity_analyze", "ai_grade",
}

TRANSITIONS: dict[str, set[str]] = {
    "pending": {"running", "skipped", "stopped"},
    "running": {"pause_requested", "awaiting_auth", "awaiting_user", "completed", "stopped", "failed"},
    "pause_requested": {"paused", "stopped", "failed"},
    "paused": {"running", "stopped"},
    "awaiting_auth": {"running", "stopped", "failed"},
    "awaiting_user": {"running", "completed", "skipped", "stopped"},
    "completed": set(),
    "stopped": set(),
    "failed": set(),
    "skipped": set(),
}

REQUIRED_CAPABILITIES: dict[str, set[str]] = {
    "merge_dedup": {"normalized"},
    "profile_enrich": {"normalized"},
    "rules_filter": {"normalized"},
    "similarity_analyze": {"normalized"},
    "ai_grade": {"normalized"},
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_transition(current: str, target: str) -> None:
    if target not in TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid stage transition: {current} -> {target}")


def get_stage(stage_id: str, org_id: str) -> Optional[dict[str, Any]]:
    result = (
        get_supabase().table("stage_runs").select("*")
        .eq("id", stage_id).eq("org_id", org_id).maybe_single().execute()
    )
    return response_data(result)


def list_stages(job_id: str, org_id: str) -> list[dict[str, Any]]:
    result = (
        get_supabase().table("stage_runs").select("*")
        .eq("job_id", job_id).eq("org_id", org_id)
        .order("created_at").execute()
    )
    return result.data or []


def validate_inputs(input_ids: list[str], org_id: str, stage_type: str) -> None:
    if stage_type.endswith("_extract") or stage_type == "file_import":
        return
    if not input_ids:
        raise ValueError(f"{stage_type} requires at least one input dataset")
    result = (
        get_supabase().table("candidate_datasets").select("id,capabilities,state")
        .in_("id", input_ids).eq("org_id", org_id).execute()
    )
    datasets = result.data or []
    if len(datasets) != len(set(input_ids)):
        raise LookupError("One or more input datasets were not found")
    required = REQUIRED_CAPABILITIES.get(stage_type, set())
    for dataset in datasets:
        if dataset["state"] not in ("sealed", "partial"):
            raise ValueError("Input datasets must be sealed or partial")
        if not required.issubset(set(dataset.get("capabilities") or [])):
            raise ValueError(f"Dataset {dataset['id']} lacks capabilities: {sorted(required)}")


def create_stage(
    *, org_id: str, job_id: str, stage_type: str,
    input_dataset_ids: list[str], config: dict[str, Any],
    idempotency_key: Optional[str], attempt: int = 1,
) -> tuple[dict[str, Any], bool]:
    if stage_type not in STAGE_TYPES:
        raise ValueError("Unknown stage type")
    if idempotency_key:
        response = (
            get_supabase().table("stage_runs").select("*")
            .eq("job_id", job_id).eq("org_id", org_id)
            .eq("idempotency_key", idempotency_key).maybe_single().execute()
        )
        existing = response_data(response)
        if existing:
            return existing, False
    validate_inputs(input_dataset_ids, org_id, stage_type)
    row = {
        "org_id": org_id,
        "job_id": job_id,
        "stage_type": stage_type,
        "input_dataset_ids": input_dataset_ids,
        "config": config,
        "idempotency_key": idempotency_key,
        "attempt": attempt,
    }
    result = get_supabase().table("stage_runs").insert(row).execute()
    if not result.data:
        raise RuntimeError("Failed to create stage run")
    return result.data[0], True


def transition_stage(stage_id: str, org_id: str, target: str, **fields: Any) -> dict[str, Any]:
    stage = get_stage(stage_id, org_id)
    if not stage:
        raise LookupError("Stage run not found")
    validate_transition(stage["status"], target)
    updates = {"status": target, **fields}
    if target == "running" and not stage.get("started_at"):
        updates["started_at"] = now_iso()
    if target in {"completed", "stopped", "failed", "skipped"}:
        updates["ended_at"] = now_iso()
    result = (
        get_supabase().table("stage_runs").update(updates)
        .eq("id", stage_id).eq("org_id", org_id).execute()
    )
    return result.data[0]


def request_control(stage_id: str, org_id: str, action: str) -> dict[str, Any]:
    stage = get_stage(stage_id, org_id)
    if not stage:
        raise LookupError("Stage run not found")
    if action == "pause":
        return transition_stage(stage_id, org_id, "pause_requested")
    if action == "stop":
        if stage["status"] == "pause_requested":
            return transition_stage(stage_id, org_id, "stopped")
        return transition_stage(stage_id, org_id, "stopped")
    if action == "skip":
        return transition_stage(stage_id, org_id, "skipped")
    raise ValueError("Unknown control action")


def set_progress(stage_id: str, org_id: str, current: int, total: int, **checkpoint: Any) -> None:
    progress = {
        "current": current,
        "total": total,
        "percentage": round(current / total * 100, 1) if total else 0,
    }
    get_supabase().table("stage_runs").update({
        "progress": progress,
        "checkpoint": checkpoint,
    }).eq("id", stage_id).eq("org_id", org_id).execute()
